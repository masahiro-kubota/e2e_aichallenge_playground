"""Linear MPC solver for lateral control using kinematic bicycle model."""

import logging
import time
from dataclasses import dataclass

import cvxpy as cp
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MPCConfig:
    """Configuration for MPC solver."""

    prediction_horizon: int  # Prediction horizon [steps]
    control_horizon: int  # Control horizon [steps]
    dt: float  # Discretization time step [s]

    # Weights
    weight_lateral_error: float  # Weight for lateral error
    weight_heading_error: float  # Weight for heading error
    weight_steering: float  # Weight for steering input
    weight_steering_rate: float  # Weight for steering rate

    # Constraints
    max_steering_angle: float  # Maximum steering angle [rad]
    max_steering_rate: float  # Maximum steering rate [rad/s]
    steer_delay_time: float  # Steering delay time [s]
    steer_gain: float  # Steering gain
    steer_zeta: float  # Steering damping ratio
    steer_omega_n: float  # Steering natural frequency [rad/s]
    prediction_velocity: float  # Velocity used for MPC prediction [m/s]

    # Solver Settings
    solver_max_iter: int = 10000
    solver_verbose: bool = False
    solver_eps_abs: float = 1e-3
    solver_eps_rel: float = 1e-3


class LinearMPCLateralSolver:
    """Linear MPC solver for lateral path tracking using Vectorized CVXPY with Slack Variables."""

    SLACK_PENALTY_WEIGHT = 1000.0

    def __init__(self, config: MPCConfig, wheelbase: float):
        # ... (lines 41-169 unchanged)
        self.config = config
        self.wheelbase = wheelbase

        # 1. Define Parameters
        self.p_lateral_error = cp.Parameter()
        self.p_heading_error = cp.Parameter()
        self.p_current_steering = cp.Parameter()
        self.p_current_steering_rate = cp.Parameter()  # New: Initial steering rate
        self.p_velocity = cp.Parameter(nonneg=True)
        self.p_kappa = cp.Parameter(self.config.prediction_horizon)
        
        self.delay_steps = int(round(self.config.steer_delay_time / self.config.dt))
        self.p_u_history = cp.Parameter(max(1, self.delay_steps))

        N = self.config.prediction_horizon
        M = self.config.control_horizon
        dt = self.config.dt

        # 2. Decision Variables
        self.x = cp.Variable((4, N + 1))  # [e_y, e_psi, delta, delta_dot]
        self.u = cp.Variable((1, M))      # [delta_cmd]
        self.slack_rate = cp.Variable((1, N), nonneg=True)     # Slack for steering rate
        self.slack_steering = cp.Variable((1, N + 1), nonneg=True)  # Slack for steering angle

        # 3. Vectorized Cost Function
        # We store cost expressions side by side to return them after solving
        self.cost_lateral_expr = self.config.weight_lateral_error * cp.sum_squares(self.x[0, :N])
        self.cost_heading_expr = self.config.weight_heading_error * cp.sum_squares(self.x[1, :N])
        self.cost_steering_expr = self.config.weight_steering * (cp.sum_squares(self.x[2, :N]) + cp.sum_squares(self.u))
        
        if M > 1:
            self.cost_steering_rate_expr = self.config.weight_steering_rate * cp.sum_squares(self.u[0, 1:] - self.u[0, :-1])
        else:
            self.cost_steering_rate_expr = cp.Constant(0.0)
        
        cost = self.cost_lateral_expr + self.cost_heading_expr + self.cost_steering_expr + self.cost_steering_rate_expr
        
        # Slack penalties for robustness
        cost += self.SLACK_PENALTY_WEIGHT * cp.sum_squares(self.slack_rate)
        cost += self.SLACK_PENALTY_WEIGHT * cp.sum_squares(self.slack_steering)

        # 4. Vectorized Constraints
        constraints = []
        # Initial State
        constraints.append(self.x[:, 0] == cp.vstack([
            self.p_lateral_error, 
            self.p_heading_error, 
            self.p_current_steering, 
            self.p_current_steering_rate
        ])[:, 0])

        # Construct U sequence considering delay
        u_seq_list = []
        if self.delay_steps > 0:
            u_seq_list.append(self.p_u_history[:self.delay_steps])
        
        remaining_steps = N - self.delay_steps
        if remaining_steps > 0:
            if remaining_steps <= M:
                u_seq_list.append(self.u[0, :remaining_steps])
            else:
                u_seq_list.append(self.u[0, :M])
                # Pad with final control value
                u_seq_list.append(cp.reshape(cp.hstack([self.u[0, M-1]] * (remaining_steps - M)), (remaining_steps - M,)))
        
        u_horizon = cp.hstack(u_seq_list)

        # 5. Vectorized Dynamics (Semi-Implicit Euler)
        G = self.config.steer_gain
        zeta = self.config.steer_zeta
        wn = self.config.steer_omega_n
        
        constraints.append(
            self.x[3, 1:] == self.x[3, :-1] + dt * (wn**2 * G * u_horizon - wn**2 * self.x[2, :-1] - 2 * zeta * wn * self.x[3, :-1])
        )
        constraints.append(self.x[2, 1:] == self.x[2, :-1] + dt * self.x[3, 1:])

        constraints.append(
            self.x[1, 1:] == self.x[1, :-1] + dt * (self.p_velocity * self.x[2, 1:] / self.wheelbase - self.p_velocity * self.p_kappa)
        )
        constraints.append(self.x[0, 1:] == self.x[0, :-1] + dt * self.p_velocity * self.x[1, 1:])

        # Soft steering rate constraints
        constraints.append(self.x[3, 1:] <= self.config.max_steering_rate + self.slack_rate)
        constraints.append(self.x[3, 1:] >= -self.config.max_steering_rate - self.slack_rate)

        # Soft steering angle constraints (ON THE STATE)
        constraints.append(self.x[2, :] <= self.config.max_steering_angle + self.slack_steering)
        constraints.append(self.x[2, :] >= -self.config.max_steering_angle - self.slack_steering)

        # Hard output limits
        constraints.append(self.u <= self.config.max_steering_angle)
        constraints.append(self.u >= -self.config.max_steering_angle)

        self.problem = cp.Problem(cp.Minimize(cost), constraints)
        
        # Internal state for Warm Start (Shifted Initial Guess)
        self.prev_x = None
        self.prev_u = None
        self.prev_slack_rate = None
        self.prev_slack_steering = None

    def solve(
        self,
        lateral_error: float,
        heading_error: float,
        current_steering: float,
        reference_curvature: np.ndarray,
        current_velocity: float,
        steering_history: list[float] = None,
        current_steering_rate: float = 0.0,
    ) -> tuple[float, np.ndarray, np.ndarray, bool, dict[str, float]]:
        """Solve Optimized Vectorized MPC with Robust Settings."""
        """Solve Optimized Vectorized MPC with Robust Settings."""
        
        self.p_lateral_error.value = lateral_error
        self.p_heading_error.value = heading_error
        self.p_current_steering.value = current_steering
        self.p_current_steering_rate.value = current_steering_rate
        self.p_velocity.value = max(abs(current_velocity), 0.1)
        
        N = self.config.prediction_horizon
        if len(reference_curvature) < N:
            self.p_kappa.value = np.concatenate([reference_curvature, np.full(N - len(reference_curvature), reference_curvature[-1])])
        else:
            self.p_kappa.value = reference_curvature[:N]
            
        if self.delay_steps > 0:
            if steering_history and len(steering_history) >= self.delay_steps:
                self.p_u_history.value = np.array(steering_history[:self.delay_steps])
            else:
                self.p_u_history.value = np.full(self.delay_steps, current_steering)
        else:
            self.p_u_history.value = np.array([0.0])

        # Apply Shifted Initial Guess (Warm Start)
        self._apply_warm_start_shift()

        try:
            # OSQP + Warm Start + Vectorized Structure + Parameterized Settings
            self.problem.solve(
                solver=cp.OSQP, 
                warm_start=True, 
                verbose=self.config.solver_verbose,
                max_iter=self.config.solver_max_iter,
                eps_abs=self.config.solver_eps_abs,
                eps_rel=self.config.solver_eps_rel,
                eps_prim_inf=1e-4,
                eps_dual_inf=1e-4,
                adaptive_rho=True
            )
            # Extract weighted costs
            costs = {
                "lateral_error_cost": float(self.cost_lateral_expr.value),
                "heading_error_cost": float(self.cost_heading_expr.value),
                "steering_cost": float(self.cost_steering_expr.value),
                "steering_rate_cost": float(self.cost_steering_rate_expr.value),
                "total_cost": float(self.problem.value)
            }

            # Save solution for next iteration's warm start
            self.prev_x = self.x.value
            self.prev_u = self.u.value
            self.prev_slack_rate = self.slack_rate.value
            self.prev_slack_steering = self.slack_steering.value

            return float(self.u[0, 0].value), self.x.value, self.u.value, True, costs

        except Exception as e:
            logger.error(f"[MPC Solver] Optimization error: {e}")
            return current_steering, None, None, False, {}

    def _apply_warm_start_shift(self):
        """Shift previous solution to use as initial guess for current cycle."""
        if self.prev_u is None or self.prev_x is None:
            return

        N = self.config.prediction_horizon
        M = self.config.control_horizon

        # Shift Control Inputs (1xM)
        # [u1, u2, ..., uM-1, uM-1]
        new_u = np.zeros((1, M))
        new_u[0, :-1] = self.prev_u[0, 1:]
        new_u[0, -1] = self.prev_u[0, -1]
        self.u.value = new_u

        # Shift Predicted States (4xN+1)
        # [x1, x2, ..., xN, xN]
        new_x = np.zeros((4, N + 1))
        new_x[:, :-1] = self.prev_x[:, 1:]
        new_x[:, -1] = self.prev_x[:, -1]
        self.x.value = new_x

        # Shift Slack Variables
        if self.prev_slack_rate is not None:
            new_slack_rate = np.zeros((1, N))
            new_slack_rate[0, :-1] = self.prev_slack_rate[0, 1:]
            new_slack_rate[0, -1] = self.prev_slack_rate[0, -1]
            self.slack_rate.value = new_slack_rate

        if self.prev_slack_steering is not None:
            new_slack_steering = np.zeros((1, N + 1))
            new_slack_steering[0, :-1] = self.prev_slack_steering[0, 1:]
            new_slack_steering[0, -1] = self.prev_slack_steering[0, -1]
            self.slack_steering.value = new_slack_steering
