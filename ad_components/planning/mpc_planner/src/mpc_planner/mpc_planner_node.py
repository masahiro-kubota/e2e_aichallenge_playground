"""MPC-based trajectory planner with obstacle avoidance."""

import math
from pathlib import Path

import casadi as ca
import numpy as np
from pydantic import Field

from core.data import ComponentConfig, SimulatorObstacle, VehicleParameters, VehicleState
from core.data.ad_components import Trajectory, TrajectoryPoint
from core.data.node_io import NodeIO
from core.interfaces.node import Node, NodeExecutionResult
from core.utils.geometry import distance
from simulator.obstacle import get_obstacle_state

from .collision_checker import CollisionChecker
from .vehicle_model import KinematicBicycleModel


class MPCPlannerConfig(ComponentConfig):
    """Configuration for MPCPlannerNode."""

    track_path: Path = Field(..., description="Path to reference trajectory CSV")
    vehicle_params: VehicleParameters = Field(..., description="Vehicle parameters")
    
    # Horizon parameters
    horizon_distance: float = Field(..., description="Planning horizon distance [m]")
    horizon_num_points: int = Field(..., description="Number of discretization points")
    
    # Update trigger
    trigger_distance: float = Field(..., description="Re-plan when traveled this distance [m]")
    
    # Optimization parameters
    max_iterations: int = Field(..., description="Maximum solver iterations")
    solver_timeout: float = Field(..., description="Solver timeout [s]")
    
    # Collision avoidance
    collision_method: str = Field(..., description="Collision avoidance method")
    safety_margin: float = Field(..., description="Safety margin for obstacles [m]")
    
    # Objective weights
    weight_progress: float = Field(..., description="Weight for forward progress")
    weight_deviation: float = Field(..., description="Weight for deviation from reference")
    weight_smoothness: float = Field(..., description="Weight for trajectory smoothness")


class MPCPlannerNode(Node[MPCPlannerConfig]):
    """MPC-based trajectory planner with obstacle avoidance."""

    def __init__(
        self,
        config: MPCPlannerConfig,
        rate_hz: float,
    ):
        super().__init__("MPCPlanner", rate_hz, config)
        self.vehicle_params = config.vehicle_params
        self.reference_trajectory: Trajectory | None = None
        
        # Load reference trajectory
        from planning_utils import load_track_csv
        from core.utils import get_project_root

        track_path = self.config.track_path
        if not track_path.is_absolute():
            track_path = get_project_root() / track_path

        self.reference_trajectory = load_track_csv(track_path)
        
        # Initialize components
        self.vehicle_model = KinematicBicycleModel(self.vehicle_params.wheelbase)
        self.collision_checker = CollisionChecker(
            vehicle_width=self.vehicle_params.width,
            vehicle_length=self.vehicle_params.wheelbase 
                + self.vehicle_params.front_overhang 
                + self.vehicle_params.rear_overhang,
            safety_margin=self.config.safety_margin,
        )
        
        # State for re-planning trigger
        self.last_plan_x: float | None = None
        self.last_plan_y: float | None = None
        self.last_planned_trajectory: Trajectory | None = None

    def get_node_io(self) -> NodeIO:
        return NodeIO(
            inputs={"vehicle_state": VehicleState, "obstacles": list},
            outputs={"trajectory": Trajectory},
        )

    def on_run(self, current_time: float) -> NodeExecutionResult:
        if self.frame_data is None:
            return NodeExecutionResult.FAILED

        self.current_time = current_time

        # Get Input
        vehicle_state = getattr(self.frame_data, "vehicle_state", None)
        if vehicle_state is None:
            return NodeExecutionResult.SKIPPED

        # Process
        trajectory = self._plan(vehicle_state)

        # Set Output
        self.frame_data.trajectory = trajectory
        return NodeExecutionResult.SUCCESS

    def _plan(self, vehicle_state: VehicleState) -> Trajectory:
        """Plan trajectory using MPC optimization."""
        if self.reference_trajectory is None or len(self.reference_trajectory) < 2:
            return Trajectory(points=[])

        # Check if we need to re-plan
        if not self._should_replan(vehicle_state):
            # Return cached trajectory
            if self.last_planned_trajectory is not None:
                return self.last_planned_trajectory
        
        # Get obstacles
        obstacles = getattr(self.frame_data, "obstacles", [])
        
        # Optimize trajectory
        try:
            trajectory = self._optimize_trajectory(vehicle_state, obstacles)
            
            # Cache the result
            self.last_plan_x = vehicle_state.x
            self.last_plan_y = vehicle_state.y
            self.last_planned_trajectory = trajectory
            
            return trajectory
        except Exception as e:
            # Fallback: return reference path point
            print(f"MPC optimization failed: {e}, falling back to reference path")
            return self._fallback_plan(vehicle_state)
    
    def _should_replan(self, vehicle_state: VehicleState) -> bool:
        """Check if we should trigger re-planning."""
        if self.last_plan_x is None or self.last_plan_y is None:
            return True
        
        # Check distance traveled since last plan
        dist_traveled = math.sqrt(
            (vehicle_state.x - self.last_plan_x)**2 
            + (vehicle_state.y - self.last_plan_y)**2
        )
        
        return dist_traveled >= self.config.trigger_distance
    
    def _optimize_trajectory(
        self, 
        vehicle_state: VehicleState, 
        obstacles: list[SimulatorObstacle]
    ) -> Trajectory:
        """Solve MPC optimization problem."""
        # Extract reference path segment
        ref_points = self._extract_reference_path(vehicle_state)
        if len(ref_points) < 2:
            return self._fallback_plan(vehicle_state)
        
        # Setup optimization problem
        N = self.config.horizon_num_points
        dt = self.config.horizon_distance / (N * vehicle_state.velocity + 1e-6)
        dt = min(dt, 0.5)  # Cap dt to avoid numerical issues
        
        # Decision variables
        opti = ca.Opti()
        
        # State variables: [x, y, theta, v] for each time step
        X = opti.variable(4, N + 1)
        x = X[0, :]
        y = X[1, :]
        theta = X[2, :]
        v = X[3, :]
        
        # Control variables: [a, delta] for each time step
        U = opti.variable(2, N)
        a = U[0, :]
        delta = U[1, :]
        
        # Initial condition
        opti.subject_to(x[0] == vehicle_state.x)
        opti.subject_to(y[0] == vehicle_state.y)
        opti.subject_to(theta[0] == vehicle_state.yaw)
        opti.subject_to(v[0] == vehicle_state.velocity)
        
        # Dynamics constraints
        for k in range(N):
            x_next, y_next, theta_next, v_next = self.vehicle_model.discretize_euler(
                x[k], y[k], theta[k], v[k], a[k], delta[k], dt
            )
            opti.subject_to(x[k + 1] == x_next)
            opti.subject_to(y[k + 1] == y_next)
            opti.subject_to(theta[k + 1] == theta_next)
            opti.subject_to(v[k + 1] == v_next)
        
        # Control constraints
        for k in range(N):
            opti.subject_to(opti.bounded(
                -self.vehicle_params.max_acceleration,
                a[k],
                self.vehicle_params.max_acceleration
            ))
            opti.subject_to(opti.bounded(
                -self.vehicle_params.max_steering_angle,
                delta[k],
                self.vehicle_params.max_steering_angle
            ))
        
        # State constraints
        for k in range(N + 1):
            opti.subject_to(opti.bounded(0.0, v[k], 5.0))  # Max 5 m/s as requested
        
        # Collision avoidance constraints
        if obstacles:
            for k in range(N + 1):
                for obstacle in obstacles:
                    obs_state = get_obstacle_state(obstacle, self.current_time)
                    
                    if self.config.collision_method == "four_corners":
                        min_dist = self.collision_checker.four_corners_distance(
                            x[k], y[k], theta[k],
                            obs_state.x, obs_state.y, obs_state.yaw,
                            obstacle.shape.width, obstacle.shape.length
                        )
                    elif self.config.collision_method == "multi_circle":
                        min_dist = self.collision_checker.multi_circle_distance(
                            x[k], y[k], theta[k],
                            obs_state.x, obs_state.y, obs_state.yaw,
                            obstacle.shape.width, obstacle.shape.length
                        )
                    else:  # "circle" - single circle approximation
                        min_dist = self.collision_checker.circle_approximation_distance(
                            x[k], y[k],
                            obs_state.x, obs_state.y,
                            obstacle.shape.width, obstacle.shape.length
                        )
                    
                    opti.subject_to(min_dist >= self.config.safety_margin)
        
        # Objective function
        cost = 0
        
        # Progress: maximize distance along reference path
        for k in range(N + 1):
            # Find closest reference point
            ref_x = ref_points[min(k, len(ref_points) - 1)].x
            ref_y = ref_points[min(k, len(ref_points) - 1)].y
            ref_v = ref_points[min(k, len(ref_points) - 1)].velocity
            
            # Deviation cost
            deviation = (x[k] - ref_x)**2 + (y[k] - ref_y)**2
            cost += self.config.weight_deviation * deviation
            
            # Progress reward (negative cost)
            if k < len(ref_points):
                progress = (x[k] - vehicle_state.x) * math.cos(vehicle_state.yaw) \
                         + (y[k] - vehicle_state.y) * math.sin(vehicle_state.yaw)
                cost -= self.config.weight_progress * progress
            
            # Velocity reward: encourage maintaining reference velocity
            velocity_error = (v[k] - ref_v)**2
            cost += 0.1 * velocity_error  # Small weight to encourage velocity tracking
        
        # Smoothness: penalize control changes
        for k in range(N - 1):
            cost += self.config.weight_smoothness * (a[k + 1] - a[k])**2
            cost += self.config.weight_smoothness * (delta[k + 1] - delta[k])**2
        
        opti.minimize(cost)
        
        # Solver options
        opts = {
            "ipopt.print_level": 0,
            "print_time": 0,
            "ipopt.max_iter": self.config.max_iterations,
            "ipopt.max_cpu_time": self.config.solver_timeout,
        }
        opti.solver("ipopt", opts)
        
        # Initial guess: follow reference path
        x_init = [ref_points[min(k, len(ref_points) - 1)].x for k in range(N + 1)]
        y_init = [ref_points[min(k, len(ref_points) - 1)].y for k in range(N + 1)]
        theta_init = [ref_points[min(k, len(ref_points) - 1)].yaw for k in range(N + 1)]
        v_init = [vehicle_state.velocity] * (N + 1)
        
        opti.set_initial(x, x_init)
        opti.set_initial(y, y_init)
        opti.set_initial(theta, theta_init)
        opti.set_initial(v, v_init)
        opti.set_initial(a, [0.0] * N)
        opti.set_initial(delta, [0.0] * N)
        
        # Solve
        sol = opti.solve()
        
        # Extract solution
        x_sol = sol.value(x)
        y_sol = sol.value(y)
        theta_sol = sol.value(theta)
        v_sol = sol.value(v)
        
        # Convert to trajectory
        points = []
        for k in range(N + 1):
            points.append(TrajectoryPoint(
                x=float(x_sol[k]),
                y=float(y_sol[k]),
                yaw=float(theta_sol[k]),
                velocity=float(v_sol[k])
            ))
        
        return Trajectory(points=points)
    
    def _extract_reference_path(self, vehicle_state: VehicleState) -> list[TrajectoryPoint]:
        """Extract reference path segment for optimization."""
        if self.reference_trajectory is None:
            return []
        
        # Find nearest point on reference trajectory
        min_dist = float("inf")
        nearest_idx = 0
        
        for i, point in enumerate(self.reference_trajectory):
            d = distance(vehicle_state.x, vehicle_state.y, point.x, point.y)
            if d < min_dist:
                min_dist = d
                nearest_idx = i
        
        # Extract points ahead
        N = self.config.horizon_num_points
        ref_points = []
        for i in range(N + 1):
            idx = min(nearest_idx + i, len(self.reference_trajectory) - 1)
            ref_points.append(self.reference_trajectory[idx])
        
        return ref_points
    
    def _fallback_plan(self, vehicle_state: VehicleState) -> Trajectory:
        """Fallback plan when optimization fails."""
        if self.reference_trajectory is None:
            return Trajectory(points=[])
        
        # Find nearest point
        min_dist = float("inf")
        nearest_idx = 0
        
        for i, point in enumerate(self.reference_trajectory):
            d = distance(vehicle_state.x, vehicle_state.y, point.x, point.y)
            if d < min_dist:
                min_dist = d
                nearest_idx = i
        
        # Return next point
        target_idx = min(nearest_idx + 1, len(self.reference_trajectory) - 1)
        return Trajectory(points=[self.reference_trajectory[target_idx]])
