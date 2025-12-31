"""MPC Lateral Controller Node with PID Longitudinal Control."""

import logging
import math
import time
from collections import deque

import numpy as np
from core.data import ComponentConfig, MPCCostDebug, VehicleParameters, VehicleState
from core.data.autoware import (
    AckermannControlCommand,
    AckermannLateralCommand,
    LongitudinalCommand,
    Trajectory,
)
from core.data.node_io import NodeIO
from core.data.ros import ColorRGBA, Marker, MarkerArray, Point
from core.interfaces.node import Node, NodeExecutionResult
from core.utils.geometry import distance, normalize_angle
from core.utils.ros_message_builder import to_ros_time
from pydantic import Field

from mpc_lateral_controller.mpc_solver import LinearMPCLateralSolver, MPCConfig

logger = logging.getLogger(__name__)


class MPCLateralParams(ComponentConfig):
    """MPC lateral control parameters."""

    prediction_horizon: int = Field(..., description="Prediction horizon [steps]")
    control_horizon: int = Field(..., description="Control horizon [steps]")
    dt: float = Field(..., description="Discretization time step [s]")
    weight_lateral_error: float = Field(..., description="Weight for lateral error")
    weight_heading_error: float = Field(..., description="Weight for heading error")
    weight_steering: float = Field(..., description="Weight for steering input")
    weight_steering_rate: float = Field(..., description="Weight for steering rate")
    max_steering_angle: float = Field(..., description="Maximum steering angle [rad]")
    max_steering_rate: float = Field(..., description="Maximum steering rate [rad/s]")
    steer_delay_time: float = Field(..., description="Steering delay time [s]")
    steer_gain: float = Field(..., description="Steering gain")
    steer_zeta: float = Field(..., description="Steering damping ratio")
    steer_omega_n: float = Field(..., description="Steering natural frequency [rad/s]")
    prediction_velocity: float = Field(..., description="Velocity used for MPC prediction [m/s]")
    solver_max_iter: int = Field(10000, description="Maximum number of iterations for the solver")
    solver_verbose: bool = Field(False, description="Whether to show solver output")
    solver_eps_abs: float = Field(1e-3, description="Absolute tolerance for the solver")
    solver_eps_rel: float = Field(1e-3, description="Relative tolerance for the solver")


class LongitudinalControlParams(ComponentConfig):
    """Longitudinal control parameters (PID)."""

    kp: float = Field(..., description="Proportional gain for velocity control")
    ki: float = Field(..., description="Integral gain for velocity control")
    kd: float = Field(..., description="Derivative gain for velocity control")
    u_min: float = Field(..., description="Minimum acceleration [m/s^2]")
    u_max: float = Field(..., description="Maximum acceleration [m/s^2]")


class MPCLateralControllerConfig(ComponentConfig):
    """Configuration for MPCLateralControllerNode."""

    vehicle_params: VehicleParameters = Field(..., description="Vehicle parameters")
    mpc_lateral: MPCLateralParams = Field(..., description="MPC lateral control parameters")
    longitudinal: LongitudinalControlParams = Field(
        ..., description="Longitudinal control parameters"
    )


class MPCLateralControllerNode(Node[MPCLateralControllerConfig]):
    """MPC-based lateral controller with PID longitudinal control.

    This controller uses Model Predictive Control (MPC) for lateral path tracking
    and a simple PID controller for longitudinal speed control.
    """

    def __init__(self, config: MPCLateralControllerConfig, rate_hz: float, priority: int) -> None:
        super().__init__("MPCLateralController", rate_hz, config, priority)

        # Initialize MPC solver
        mpc_config = MPCConfig(
            prediction_horizon=self.config.mpc_lateral.prediction_horizon,
            control_horizon=self.config.mpc_lateral.control_horizon,
            dt=self.config.mpc_lateral.dt,
            weight_lateral_error=self.config.mpc_lateral.weight_lateral_error,
            weight_heading_error=self.config.mpc_lateral.weight_heading_error,
            weight_steering=self.config.mpc_lateral.weight_steering,
            weight_steering_rate=self.config.mpc_lateral.weight_steering_rate,
            max_steering_angle=self.config.mpc_lateral.max_steering_angle,
            max_steering_rate=self.config.mpc_lateral.max_steering_rate,
            steer_delay_time=self.config.mpc_lateral.steer_delay_time,
            steer_gain=self.config.mpc_lateral.steer_gain,
            steer_zeta=self.config.mpc_lateral.steer_zeta,
            steer_omega_n=self.config.mpc_lateral.steer_omega_n,
            prediction_velocity=self.config.mpc_lateral.prediction_velocity,
            solver_max_iter=self.config.mpc_lateral.solver_max_iter,
            solver_verbose=self.config.mpc_lateral.solver_verbose,
            solver_eps_abs=self.config.mpc_lateral.solver_eps_abs,
            solver_eps_rel=self.config.mpc_lateral.solver_eps_rel,
        )
        self.mpc_solver = LinearMPCLateralSolver(
            config=mpc_config, wheelbase=self.config.vehicle_params.wheelbase
        )

        # Steering history for delay modeling
        delay_steps = round(self.config.mpc_lateral.steer_delay_time / self.config.mpc_lateral.dt)
        self.steering_history = deque([0.0] * max(1, delay_steps), maxlen=max(1, delay_steps))

        # PID state for longitudinal control
        self.velocity_error_integral = 0.0
        self.previous_velocity_error = 0.0
        self.previous_time = None

    def get_node_io(self) -> NodeIO:
        return NodeIO(
            inputs={"trajectory": Trajectory, "vehicle_state": VehicleState},
            outputs={
                "control_cmd": AckermannControlCommand,
                "lateral_control_debug": MPCCostDebug,
                "debug_predicted_trajectory": MarkerArray,
            },
        )

    def on_run(self, current_time: float) -> NodeExecutionResult:
        trajectory = self.subscribe("trajectory")
        vehicle_state = self.subscribe("vehicle_state")

        if trajectory is None or vehicle_state is None:
            return NodeExecutionResult.SKIPPED

        if not trajectory or len(trajectory) == 0:
            # Output zero control command
            self.publish(
                "control_cmd",
                AckermannControlCommand(
                    stamp=to_ros_time(current_time),
                    lateral=AckermannLateralCommand(
                        stamp=to_ros_time(current_time), steering_tire_angle=0.0
                    ),
                    longitudinal=LongitudinalCommand(
                        stamp=to_ros_time(current_time), acceleration=0.0, speed=0.0
                    ),
                ),
            )
            return NodeExecutionResult.SUCCESS

        # Compute control commands
        steering_angle, acceleration = self._compute_control(
            trajectory, vehicle_state, current_time
        )

        # Output control command
        self.publish(
            "control_cmd",
            AckermannControlCommand(
                stamp=to_ros_time(current_time),
                lateral=AckermannLateralCommand(
                    stamp=to_ros_time(current_time), steering_tire_angle=steering_angle
                ),
                longitudinal=LongitudinalCommand(
                    stamp=to_ros_time(current_time), acceleration=acceleration, speed=0.0
                ),
            ),
        )

        return NodeExecutionResult.SUCCESS

    def _quaternion_to_yaw(self, quat) -> float:
        """Convert quaternion to yaw angle.

        Args:
            quat: Quaternion object with x, y, z, w fields

        Returns:
            Yaw angle in radians
        """
        # Extract yaw from quaternion using simplified formula
        # yaw = atan2(2*(w*z + x*y), 1 - 2*(y^2 + z^2))
        return math.atan2(
            2.0 * (quat.w * quat.z + quat.x * quat.y),
            1.0 - 2.0 * (quat.y * quat.y + quat.z * quat.z),
        )

    def _compute_control(
        self, trajectory: Trajectory, vehicle_state: VehicleState, current_time: float
    ) -> tuple[float, float]:
        """Compute steering and acceleration using MPC + PID.

        Args:
            trajectory: Reference trajectory
            vehicle_state: Current vehicle state
            current_time: Current simulation time

        Returns:
            tuple: (steering_angle, acceleration)
        """
        # Find closest point on trajectory
        closest_idx, min_dist = self._find_closest_point(trajectory, vehicle_state)

        logger.info(
            f"[MPC] Vehicle: pos=({vehicle_state.x:.2f}, {vehicle_state.y:.2f}), "
            f"yaw={math.degrees(vehicle_state.yaw):.1f}°, v={vehicle_state.velocity:.2f}m/s, "
            f"steering={math.degrees(vehicle_state.steering):.2f}°"
        )
        logger.info(f"[MPC] Closest point: idx={closest_idx}, dist={min_dist:.3f}m")

        # Calculate lateral error (signed distance to path relative to path heading)
        ref_heading = self._quaternion_to_yaw(trajectory.points[closest_idx].pose.orientation)
        lateral_error = self._calculate_lateral_error(
            trajectory.points[closest_idx], vehicle_state, ref_heading
        )

        # Calculate heading error
        heading_error = normalize_angle(vehicle_state.yaw - ref_heading)

        logger.info(
            f"[MPC] Errors: lateral={lateral_error:.3f}m, "
            f"heading={math.degrees(heading_error):.2f}° "
            f"(ref_yaw={math.degrees(ref_heading):.1f}°)"
        )

        # Extract reference curvature for prediction horizon
        reference_curvature = self._extract_reference_curvature(trajectory, closest_idx)
        logger.info(f"[MPC] Reference curvature[0:3]: {reference_curvature[:3]}")

        # Solve MPC for lateral control
        # Use steering_rate from vehicle_state (now available)
        start_time = time.perf_counter()
        steering_angle, predicted_states, _, success, costs = self.mpc_solver.solve(
            lateral_error=lateral_error,
            heading_error=heading_error,
            current_steering=vehicle_state.steering,
            reference_curvature=reference_curvature,
            current_velocity=self.config.mpc_lateral.prediction_velocity,
            steering_history=list(self.steering_history),
            current_steering_rate=vehicle_state.steering_rate,
        )
        solve_time_ms = (time.perf_counter() - start_time) * 1000.0

        if success:
            logger.info("[MPC] ✅ Optimization success")
            # Publish predicted trajectory for debugging
            self._publish_predicted_trajectory(
                predicted_states, trajectory, closest_idx, current_time
            )
            # Publish cost debug info
            self.publish(
                "lateral_control_debug",
                MPCCostDebug(
                    lateral_error_cost=costs["lateral_error_cost"],
                    heading_error_cost=costs["heading_error_cost"],
                    steering_cost=costs["steering_cost"],
                    steering_rate_cost=costs["steering_rate_cost"],
                    total_cost=costs["total_cost"],
                ),
            )
            logger.info(
                f"[MPC] Costs: lat={costs['lateral_error_cost']:.2f}, "
                f"head={costs['heading_error_cost']:.2f}, "
                f"steer={costs['steering_cost']:.2f}, "
                f"rate={costs['steering_rate_cost']:.2f}, "
                f"total={costs['total_cost']:.2f}"
            )
            logger.info(f"[MPC] ⏱️ Solve time: {solve_time_ms:.2f} ms")
        else:
            logger.warning(
                f"[MPC] ❌ Optimization failed, using current steering (Time: {solve_time_ms:.2f} ms)"
            )
            steering_angle = vehicle_state.steering

        # Update steering history with the command we are about to send
        self.steering_history.append(steering_angle)

        # Note: self.previous_time is shared with PID, so we must not update it
        # BEFORE calling _compute_longitudinal_control.

        logger.info(f"[MPC] Steering angle: {math.degrees(steering_angle):.3f}°")

        # Clamp steering angle to limits
        steering_angle = np.clip(
            steering_angle,
            -self.config.mpc_lateral.max_steering_angle,
            self.config.mpc_lateral.max_steering_angle,
        )

        logger.info(
            f"[MPC] Final steering command: {math.degrees(steering_angle):.3f}° "
            f"(limits: ±{math.degrees(self.config.mpc_lateral.max_steering_angle):.1f}°)"
        )

        # PID longitudinal control。。。
        current_velocity = vehicle_state.velocity
        target_velocity = trajectory.points[closest_idx].longitudinal_velocity_mps
        acceleration = self._compute_longitudinal_control(
            target_velocity, current_velocity, current_time
        )

        logger.info(
            f"[MPC] Longitudinal: target_v={target_velocity:.2f}m/s, accel={acceleration:.2f}m/s²"
        )
        logger.info("[MPC] " + "=" * 80)

        return float(steering_angle), float(acceleration)

    def _find_closest_point(
        self, trajectory: Trajectory, vehicle_state: VehicleState
    ) -> tuple[int, float]:
        """Find the closest point on the trajectory.

        Returns:
            tuple: (index of closest point, distance to closest point)
        """
        min_dist = float("inf")
        closest_idx = 0

        # Find closest point
        for i, point in enumerate(trajectory.points):
            dist = distance(
                vehicle_state.x,
                vehicle_state.y,
                point.pose.position.x,
                point.pose.position.y,
            )
            if dist < min_dist:
                min_dist = dist
                closest_idx = i

        return closest_idx, min_dist

    def _calculate_lateral_error(
        self, target_point, vehicle_state: VehicleState, ref_heading: float
    ) -> float:
        """Calculate signed lateral error to target point relative to ref_heading.

        Positive error means vehicle is to the LEFT of the path.
        """
        # Vector from target point TO vehicle
        dx = vehicle_state.x - target_point.pose.position.x
        dy = vehicle_state.y - target_point.pose.position.y

        # Lateral error is the perpendicular distance relative to the PATH heading
        # Normal vector to path (Left of path): (-sin(ref), cos(ref))
        # lateral_error = dot(pos_diff, left_normal)
        lateral_error = -dx * math.sin(ref_heading) + dy * math.cos(ref_heading)

        return lateral_error

    def _extract_reference_curvature(self, trajectory: Trajectory, start_idx: int) -> np.ndarray:
        """Extract reference path curvature by numerically differentiating interpolated yaws (Vectorized)."""
        n_horizon = self.config.mpc_lateral.prediction_horizon
        dt = self.config.mpc_lateral.dt
        v = max(self.config.mpc_lateral.prediction_velocity, 0.1)

        # 1. Collect points data into arrays for fast access
        points = trajectory.points
        n_points = len(points)
        path_x = np.array([p.pose.position.x for p in points])
        path_y = np.array([p.pose.position.y for p in points])
        path_yaw = np.array([self._quaternion_to_yaw(p.pose.orientation) for p in points])

        # Calculate distances along the path (cumulative sum)
        dx = np.diff(path_x)
        dy = np.diff(path_y)
        dists = np.sqrt(dx**2 + dy**2)
        s_path = np.zeros(n_points)
        s_path[1:] = np.cumsum(dists)

        # 2. Define target s for prediction horizon
        # s_target[i] = relative_s + s_start
        s_start = s_path[min(start_idx, n_points - 1)]
        s_targets = s_start + np.arange(n_horizon) * v * dt

        # 3. Interpolate yaw at s_targets and (s_targets + tiny_ds)
        tiny_ds = 0.1

        # Handle wrapping for yaw interpolation: Unwrap before interpolation
        path_yaw_unwrapped = np.unwrap(path_yaw)

        # Interpolate
        # We need to clamp s_targets to be within [0, s_path[-1]]
        # But we assume the path is long enough or we extend the last value
        y_i = np.interp(s_targets, s_path, path_yaw_unwrapped)
        y_i_plus = np.interp(s_targets + tiny_ds, s_path, path_yaw_unwrapped)

        # Calculate curvature: (y(s+ds) - y(s)) / ds
        # Normalize angle just in case, though unwrap handles most
        curvatures = (y_i_plus - y_i) / tiny_ds

        # Normalize result to be safe (though curvature is a rate, so -pi/pi wrapping applies to the diff)
        # However, for small steps, simple diff is usually fine on unwrapped data.

        return curvatures

    def _compute_longitudinal_control(
        self, target_velocity: float, current_velocity: float, current_time: float
    ) -> float:
        """Compute longitudinal acceleration using PID control.

        Args:
            target_velocity: Target velocity [m/s]
            current_velocity: Current velocity [m/s]
            current_time: Current time [s]

        Returns:
            Acceleration command [m/s^2]
        """
        # Calculate velocity error
        velocity_error = target_velocity - current_velocity

        # Calculate time step
        if self.previous_time is None:
            dt = 0.02  # Default dt
        else:
            dt = current_time - self.previous_time
            dt = max(dt, 1e-6)  # Avoid division by zero

        # Update integral term
        self.velocity_error_integral += velocity_error * dt

        # Calculate derivative term
        if self.previous_velocity_error is not None:
            velocity_error_derivative = (velocity_error - self.previous_velocity_error) / dt
        else:
            velocity_error_derivative = 0.0

        # PID control law
        acceleration = (
            self.config.longitudinal.kp * velocity_error
            + self.config.longitudinal.ki * self.velocity_error_integral
            + self.config.longitudinal.kd * velocity_error_derivative
        )

        # Clamp acceleration
        acceleration = np.clip(
            acceleration, self.config.longitudinal.u_min, self.config.longitudinal.u_max
        )

        # Update state at the VERY END of the longitudinal control calculation
        self.previous_velocity_error = velocity_error
        self.previous_time = current_time

        return acceleration

    def _publish_predicted_trajectory(
        self,
        predicted_states: np.ndarray,
        reference_trajectory: Trajectory,
        start_idx: int,
        current_time: float,
    ) -> None:
        """Publish predicted trajectory as MarkerArray (Vectorized calculation)."""
        if predicted_states is None:
            return

        marker_array = MarkerArray()

        # 1. Trajectory Line Strip Marker
        marker = Marker()
        marker.header.frame_id = "map"
        marker.header.stamp = to_ros_time(current_time)
        marker.ns = "predicted_trajectory"
        marker.id = 0
        marker.type = 4  # LINE_STRIP
        marker.action = 0  # ADD
        marker.scale.x = 0.2  # Line width
        marker.color = ColorRGBA(r=1.0, g=0.5, b=0.0, a=0.8)  # Orange

        n_horizon = predicted_states.shape[1]
        dt = self.config.mpc_lateral.dt
        v = max(self.config.mpc_lateral.prediction_velocity, 0.1)

        # Vectorized calculation of global positions
        # 1. Get reference path data
        points = reference_trajectory.points
        n_points = len(points)
        path_x = np.array([p.pose.position.x for p in points])
        path_y = np.array([p.pose.position.y for p in points])
        path_yaw = np.array([self._quaternion_to_yaw(p.pose.orientation) for p in points])

        # 2. Calculate path distance s
        dx = np.diff(path_x)
        dy = np.diff(path_y)
        dists = np.sqrt(dx**2 + dy**2)
        s_path = np.zeros(n_points)
        s_path[1:] = np.cumsum(dists)

        # 3. Target s for each prediction step
        s_start = s_path[min(start_idx, n_points - 1)]
        s_targets = s_start + np.arange(n_horizon) * v * dt

        # 4. Interpolate reference x, y, yaw at s_targets
        # Clamp s_targets to valid range
        s_targets = np.clip(s_targets, 0, s_path[-1])

        ref_x_interp = np.interp(s_targets, s_path, path_x)
        ref_y_interp = np.interp(s_targets, s_path, path_y)

        path_yaw_unwrapped = np.unwrap(path_yaw)
        ref_yaw_interp = np.interp(s_targets, s_path, path_yaw_unwrapped)

        # 5. Transform predicted lateral error to global position
        # pred_x = ref_x - e_y * sin(ref_yaw)
        # pred_y = ref_y + e_y * cos(ref_yaw)
        # e_y = predicted_states[0, :]
        # Actually solve returned x of shape (4, N+1). Loop in original code was range(N).
        # We should use N points.

        # Adjust size if needed (e.g. if N vs N+1 mismatch)
        # predicted_states includes x0 (initial state).
        # Usually we visualize x1...xN.
        # Original code used i in range(N) and predicted_states[0, i].
        # So it visualized x0...x(N-1). Let's stick to that for consistency, or visualize all.
        # Let's visualize all N+1 points?
        # Original code: range(N). target_dist = i * v * dt. i=0 is current state.

        e_y_vec = predicted_states[0, :n_horizon]
        pred_x_vec = ref_x_interp - e_y_vec * np.sin(ref_yaw_interp)
        pred_y_vec = ref_y_interp + e_y_vec * np.cos(ref_yaw_interp)

        # 6. Populate markers
        # Converting numpy array to list of Points is still a loop, but lightweight
        for x, y in zip(pred_x_vec, pred_y_vec):
            marker.points.append(Point(x=x, y=y, z=0.0))

        marker_array.markers.append(marker)

        # 7. Text Markers (every 5 steps)
        # We can optimize this by reducing calls, but creating Marker objects is inevitable
        for i in range(0, n_horizon, 5):
            text_marker = Marker()
            text_marker.header = marker.header
            text_marker.ns = "predicted_steering"
            text_marker.id = i
            text_marker.type = 9  # TEXT_VIEW_FACING
            text_marker.action = 0  # ADD
            text_marker.pose.position.x = pred_x_vec[i]
            text_marker.pose.position.y = pred_y_vec[i]
            text_marker.pose.position.z = 0.5
            text_marker.pose.orientation.w = 1.0
            text_marker.scale.z = 0.3
            text_marker.color = ColorRGBA(r=1.0, g=1.0, b=1.0, a=1.0)

            steer_rad = predicted_states[2, i]
            text_marker.text = f"{steer_rad:.3f}"
            marker_array.markers.append(text_marker)

        self.publish("debug_predicted_trajectory", marker_array)
