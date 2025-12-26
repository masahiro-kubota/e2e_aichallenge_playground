import numpy as np

from core.data import (
    SimulatorObstacle,
    Trajectory,
    TrajectoryPoint,
    VehicleParameters,
    VehicleState,
)


class MPPIController:
    """Model Predictive Path Integral Controller for path tracking and obstacle avoidance."""

    def __init__(
        self,
        vehicle_params: VehicleParameters,
        horizon: int = 30,
        dt: float = 0.1,
        num_samples: int = 200,
        temperature: float = 1.0,
        noise_sigma_steering: float = 0.5,
        u_min_steering: float = -0.8,
        u_max_steering: float = 0.8,
    ):
        self.vp = vehicle_params
        self.K = num_samples
        self.T = horizon
        self.dt = dt
        self.lambda_ = temperature

        # Steering only optimization
        self.sigma = np.array([noise_sigma_steering])  # (1,)
        self.inv_sigma = 1.0 / self.sigma

        # Control limits
        self.u_min = np.array([u_min_steering])
        self.u_max = np.array([u_max_steering])

        # Initialize control sequence (steering)
        self.U = np.zeros((self.T, 1))

        # Previous control for smoothing (optional)
        self.prev_u = np.zeros(1)

    def solve(
        self,
        initial_state: VehicleState,
        reference_trajectory: Trajectory,
        obstacles: list[SimulatorObstacle],
    ) -> tuple[Trajectory, np.ndarray]:
        """
        Solve optimization problem.
        Returns:
            optimal_trajectory: Trajectory
            optimal_controls: np.ndarray (T, 2)
        """
        # 0. Shift control sequence
        self.U[:-1] = self.U[1:]
        self.U[-1] = np.zeros(1)  # Initialize last step with zero

        # 1. Sample Controls: u_k = U + noise
        noise = np.random.normal(loc=0.0, scale=self.sigma, size=(self.K, self.T, 1))

        # Apply noise to base control sequence
        u_samples = self.U + noise

        # Clip controls
        u_samples[:, :, 0] = np.clip(u_samples[:, :, 0], self.u_min[0], self.u_max[0])

        # epsilon = u_samples - U (broadcasting U)
        epsilon = u_samples - self.U

        # 2. Rollout
        # Define target velocity for P-control
        target_v = 5.0
        if len(reference_trajectory.points) > 0:
            target_v = max(5.0, reference_trajectory.points[0].velocity)

        trajectories = self._rollout(initial_state, u_samples, target_v)

        # 3. Calculate Cost
        costs = self._compute_costs(
            trajectories, u_samples, epsilon, reference_trajectory, obstacles
        )

        # 4. Update Control Sequence
        # weights = softmax(-cost / lambda)
        min_cost = np.min(costs)
        exp_costs = np.exp(-(costs - min_cost) / self.lambda_)
        sum_exp = np.sum(exp_costs) + 1e-10
        weights = exp_costs / sum_exp

        # Debug Print for Unit Test
        max_cost = np.max(costs)
        best_idx = np.argmin(costs)
        print(
            f"DEBUG: MinCost={min_cost:.2f}, MaxCost={max_cost:.2f}, Spread={max_cost-min_cost:.2f}"
        )
        print(f"DEBUG: MaxWeight={np.max(weights):.4f}")
        print(f"DEBUG: BestIdx={best_idx}, BestCost={costs[best_idx]:.2f}")

        # weighted average of epsilon
        # weights shape: (K,) -> (K, 1, 1) to broadcast to (K, T, 1)
        weighted_epsilon = np.sum(weights[:, None, None] * epsilon, axis=0)

        # Update U
        self.U = self.U + weighted_epsilon

        # Clip updated U just in case
        self.U[:, 0] = np.clip(self.U[:, 0], self.u_min[0], self.u_max[0])

        # 5. Generate Optimal Trajectory (by rolling out updated U)
        optimal_states = self._rollout_single(initial_state, self.U, target_v)

        # Compute accel profile for return (to match (T, 2) output)
        # Using P-control on optimal states
        kp = 1.0  # Must match internal P control
        opt_v = optimal_states[:-1, 3]
        opt_accel = np.clip(kp * (target_v - opt_v), -3.0, 3.0)

        u_2d = np.hstack([self.U, opt_accel[:, None]])

        return self._to_trajectory(optimal_states, u_2d), u_2d, trajectories

    def _rollout(
        self, initial_state: VehicleState, u_samples: np.ndarray, target_v: float
    ) -> np.ndarray:
        """
        Vectorized Kinematic Bicycle Model Rollout.
        args:
            U_samples: (K, T, 1) [steering]
            target_v: Target velocity for P-control
        Returns:
            states: (K, T+1, 4) array of [x, y, yaw, v]
        """
        num_samples, horizon, _ = u_samples.shape
        states = np.zeros((num_samples, horizon + 1, 4))

        # Initial state
        states[:, 0, 0] = initial_state.x
        states[:, 0, 1] = initial_state.y
        states[:, 0, 2] = initial_state.yaw
        states[:, 0, 3] = initial_state.velocity

        wheelbase = self.vp.wheelbase
        kp = 1.0  # P-gain

        for t in range(horizon):
            x = states[:, t, 0]
            y = states[:, t, 1]
            yaw = states[:, t, 2]
            v = states[:, t, 3]

            delta = u_samples[:, t, 0]

            # P-Control for Acceleration
            accel = kp * (target_v - v)
            accel = np.clip(accel, -3.0, 3.0)  # Clip acceleration

            x_next = x + v * np.cos(yaw) * self.dt
            y_next = y + v * np.sin(yaw) * self.dt
            yaw_next = yaw + (v / wheelbase) * np.tan(delta) * self.dt
            v_next = v + accel * self.dt
            # Prevent reversing
            v_next = np.maximum(0.0, v_next)

            states[:, t + 1, 0] = x_next
            states[:, t + 1, 1] = y_next
            states[:, t + 1, 2] = yaw_next
            states[:, t + 1, 3] = v_next

        return states

    def _rollout_single(
        self, initial_state: VehicleState, u: np.ndarray, target_v: float
    ) -> np.ndarray:
        """Rollout for a single sequence."""
        u_expanded = u[None, :, :]  # (1, T, 1)
        # target_v needs to be valid float
        states = self._rollout(initial_state, u_expanded, target_v)
        return states[0]  # (T+1, 4)

    def _compute_costs(
        self,
        trajectories: np.ndarray,
        controls: np.ndarray,
        _epsilon: np.ndarray,
        reference_trajectory: Trajectory,
        obstacles: list[SimulatorObstacle],
    ) -> np.ndarray:
        """
        Compute cost for each sample.
        Args:
            trajectories: (K, T+1, 4)
            controls: (K, T, 2)
            epsilon: (K, T, 2)
            reference: Trajectory
            obstacles: list
        Returns:
            costs: (K,)
        """
        num_samples, _t_plus_1, _ = trajectories.shape
        costs = np.zeros(num_samples)

        # Optimize reference processing:
        # Convert to numpy once and find local window
        ref_points = np.array([[p.x, p.y, p.velocity, p.yaw] for p in reference_trajectory.points])
        if len(ref_points) == 0:
            return costs

        # Find nearest point index for the initial position
        # Use mean of initial trajectory pos for robustness, or just initial_state?
        # Using trajectories[:, 0, :2] is just multiple copies of initial_state.
        current_pos = trajectories[0, 0, :2]
        dists = np.sum((ref_points[:, :2] - current_pos) ** 2, axis=1)
        start_idx = np.argmin(dists)

        # Take a window of points (horizon * 2 seems reasonable)
        window_size = self.T * 2
        # Handle wrap-around or end of track? For now, clamp.
        end_idx = min(start_idx + window_size, len(ref_points))
        if start_idx >= end_idx:  # End of track
            local_ref = ref_points[start_idx : start_idx + 1]
        else:
            local_ref = ref_points[start_idx:end_idx]

        # Reference states
        local_ref_xy = local_ref[:, :2]
        local_ref_yaw = local_ref[:, 3]

        # 1. Tracking Cost (Vectorized)
        traj_xy = trajectories[:, 1:, :2]  # (K, T, 2)
        traj_yaw = trajectories[:, 1:, 2]  # (K, T)

        # Broadcast subtract: (K, T, 1, 2) - (1, 1, M, 2) -> (K, T, M, 2)
        diff = traj_xy[:, :, np.newaxis, :] - local_ref_xy[np.newaxis, np.newaxis, :, :]
        sq_dists = np.sum(diff**2, axis=-1)  # (K, T, M)
        min_sq_dists = np.min(sq_dists, axis=-1)  # (K, T)

        costs += np.sum(min_sq_dists * 20.0, axis=1)  # Position Weight (Increased)

        # Heading & Velocity Cost
        # Find index of nearest point
        nearest_idx = np.argmin(sq_dists, axis=-1)  # (K, T)

        # Extract ref params for each point
        ref_yaw_matched = local_ref_yaw[nearest_idx]

        # Heading Cost
        yaw_diff = traj_yaw - ref_yaw_matched
        yaw_diff = (yaw_diff + np.pi) % (2 * np.pi) - np.pi
        costs += np.sum(yaw_diff**2, axis=1) * 0.0  # Heading Weight (Disabled)

        # 2. Obstacle Cost
        # Disabled for raceline tracking
        _ = obstacles  # Unused for now

        # 3. Input Cost (Smoothness/Effort)
        costs += np.sum(controls[:, :, 0] ** 2, axis=1) * 0.1  # Steering penalty (Reduced)

        return costs

    def _to_trajectory(self, states: np.ndarray, controls: np.ndarray) -> Trajectory:
        """Convert state sequence to Trajectory."""
        points = []
        for i in range(len(controls)):  # T
            # states[i+1] is result state
            s = states[i + 1]
            p = TrajectoryPoint(x=s[0], y=s[1], yaw=s[2], velocity=s[3])
            points.append(p)
        return Trajectory(points=points)
