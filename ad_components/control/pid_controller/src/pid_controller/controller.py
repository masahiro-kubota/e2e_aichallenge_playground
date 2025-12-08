"""PID Controller implementation."""

import math
from typing import Any

from core.data import Action, VehicleParameters, VehicleState
from core.data.ad_components import Trajectory
from core.utils.geometry import distance, normalize_angle


class PIDController:
    """PID Controller for velocity and Pure Pursuit for steering."""

    def __init__(
        self,
        kp: float,
        ki: float,
        kd: float,
        vehicle_params: VehicleParameters | None = None,
    ) -> None:
        """Initialize PID controller.

        Args:
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
            vehicle_params: Vehicle parameters
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.vehicle_params = vehicle_params or VehicleParameters()
        self.wheelbase = self.vehicle_params.wheelbase

        self.integral_error = 0.0
        self.prev_error = 0.0

    def process(
        self,
        trajectory: Trajectory,
        vehicle_state: VehicleState,
        **_kwargs: Any,
    ) -> Action:
        """Compute control action.

        Args:
            trajectory: Target trajectory (expected to contain at least one point as target)
            vehicle_state: Current vehicle state
            **_kwargs: Other inputs (ignored)

        Returns:
            Control action (steering, acceleration)
        """
        if not trajectory:
            return Action(steering=0.0, acceleration=0.0)

        # 1. Steering Control (Pure Pursuit logic)
        # Assuming the first point in trajectory is the target point from Pure Pursuit Planner
        target_point = trajectory[0]

        target_angle = math.atan2(
            target_point.y - vehicle_state.y, target_point.x - vehicle_state.x
        )
        alpha = normalize_angle(target_angle - vehicle_state.yaw)
        ld = distance(vehicle_state.x, vehicle_state.y, target_point.x, target_point.y)

        if ld < 1e-3:
            steering = 0.0
        else:
            steering = math.atan2(2 * self.wheelbase * math.sin(alpha), ld)

        # 2. Velocity Control (PID)
        target_velocity = target_point.velocity
        current_velocity = vehicle_state.velocity

        error = target_velocity - current_velocity
        self.integral_error += error  # Note: Should multiply by dt, but assuming constant call rate for now or simplified
        derivative_error = error - self.prev_error

        acceleration = self.kp * error + self.ki * self.integral_error + self.kd * derivative_error

        self.prev_error = error

        return Action(steering=steering, acceleration=acceleration)

    def reset(self) -> bool:
        """Reset controller state.

        Returns:
            bool: True if reset was successful
        """
        self.integral_error = 0.0
        self.prev_error = 0.0
        return True
