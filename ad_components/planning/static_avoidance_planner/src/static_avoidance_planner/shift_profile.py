from dataclasses import dataclass
from enum import Enum

import numpy as np

from static_avoidance_planner.obstacle_manager import TargetObstacle


class AvoidanceDirection(Enum):
    LEFT = 1
    RIGHT = -1


@dataclass
class ProfilePoint:
    s: float
    lat_req: float
    direction: AvoidanceDirection


class ShiftProfile:
    """Generates shift profile for a single obstacle."""

    def __init__(
        self,
        obstacle: TargetObstacle,
        vehicle_width: float,
        safe_margin: float = 0.5,
        avoid_distance: float = 10.0,
        d_front: float = 2.0,
        d_rear: float = 2.0,
    ):
        """Initialize ShiftProfile.

        Args:
            obstacle: Target obstacle
            vehicle_width: Ego width
            safe_margin: Safety margin
            avoid_distance: Longitudinal distance for lane change
        """
        self.obs = obstacle

        # Determine direction
        if obstacle.lat == 0:
            self.sign = 1.0  # Left
        else:
            self.sign = np.sign(-obstacle.lat)

        # Calculate required shift amount
        required_clearance = obstacle.width / 2.0 + vehicle_width / 2.0 + safe_margin
        self.target_lat = obstacle.lat + self.sign * required_clearance

        # Update s range
        self.s_start_action = obstacle.s - d_front - avoid_distance
        self.s_full_avoid = obstacle.s - d_front
        self.s_keep_avoid = obstacle.s + obstacle.length + d_rear
        self.s_end_action = obstacle.s + obstacle.length + d_rear + avoid_distance

    def get_lat(self, s: float) -> float:
        """Get required lat at s."""
        if s < self.s_start_action or s > self.s_end_action:
            return 0.0

        if s < self.s_full_avoid:
            # Rampping up
            ratio = (s - self.s_start_action) / (self.s_full_avoid - self.s_start_action)
            # Smoothstep
            k = ratio * ratio * (3 - 2 * ratio)
            return k * self.target_lat

        if s > self.s_keep_avoid:
            # Rampping down
            ratio = (self.s_end_action - s) / (self.s_end_action - self.s_keep_avoid)
            k = ratio * ratio * (3 - 2 * ratio)
            return k * self.target_lat

        # Constant
        return self.target_lat


def merge_profiles(s_samples: np.ndarray, profiles: list[ShiftProfile]) -> tuple[np.ndarray, bool]:
    """Merge profiles.

    Returns:
        lat_target: Array of target lat values
        collision: Boolean, true if impossible
    """
    lat_target = np.zeros_like(s_samples)

    # We process point-wise
    for i, s in enumerate(s_samples):
        bound_min = -float("inf")  # Needs to be > this
        bound_max = float("inf")  # Needs to be < this

        active_min = False
        active_max = False

        for p in profiles:
            lat_req = p.get_lat(s)

            # Identify if this profile is active at this s
            if abs(lat_req) < 1e-6:
                continue

            if p.sign > 0:  # Left shift (Positive)
                bound_min = max(bound_min, lat_req)
                active_min = True
            else:  # Right shift (Negative)
                bound_max = min(bound_max, lat_req)
                active_max = True

        if active_min and active_max:
            if bound_min > bound_max:
                # Collision
                return lat_target, True  # Or handle partial
            lat_target[i] = (bound_min + bound_max) / 2.0

        elif active_min:
            lat_target[i] = bound_min

        elif active_max:
            lat_target[i] = bound_max

        else:
            lat_target[i] = 0.0

    return lat_target, False
