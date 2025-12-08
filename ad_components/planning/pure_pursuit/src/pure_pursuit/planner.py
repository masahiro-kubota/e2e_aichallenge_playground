"""Pure Pursuit Planner implementation."""

from typing import Any

from core.data import VehicleParameters, VehicleState
from core.data.ad_components import Trajectory, TrajectoryPoint
from core.utils.geometry import distance


class PurePursuitPlanner:
    """Pure Pursuit path tracking algorithm."""

    def __init__(
        self,
        lookahead_distance: float,
        vehicle_params: VehicleParameters | None = None,
        track_path: str | None = None,
    ) -> None:
        """Initialize Pure Pursuit planner.

        Args:
            lookahead_distance: Distance to look ahead for target point [m]
            vehicle_params: Vehicle parameters (optional)
            track_path: Path to reference trajectory CSV (optional)
        """
        self.lookahead_distance = lookahead_distance
        self.vehicle_params = vehicle_params or VehicleParameters()
        self.reference_trajectory: Trajectory | None = None

        if track_path:
            from planning_utils import load_track_csv

            self.reference_trajectory = load_track_csv(track_path)

    def set_reference_trajectory(self, trajectory: Trajectory) -> None:
        """Set the reference trajectory to track.

        Args:
            trajectory: Reference trajectory
        """
        self.reference_trajectory = trajectory

    def process(self, vehicle_state: VehicleState, **_kwargs: Any) -> Trajectory:
        """Plan a trajectory using Pure Pursuit.

        Args:
            vehicle_state: Current vehicle state
            **_kwargs: Other inputs (ignored)

        Returns:
            Planned trajectory (single point with target steering)
        """
        if self.reference_trajectory is None or len(self.reference_trajectory) < 2:
            return Trajectory(points=[])

        # 1. Find nearest point on reference trajectory
        min_dist = float("inf")
        nearest_idx = 0

        for i, point in enumerate(self.reference_trajectory):
            d = distance(vehicle_state.x, vehicle_state.y, point.x, point.y)
            if d < min_dist:
                min_dist = d
                nearest_idx = i

        # 2. Find lookahead point
        target_point = self.reference_trajectory[nearest_idx]
        accumulated_dist = 0.0

        current_idx = nearest_idx
        while accumulated_dist < self.lookahead_distance:
            if current_idx >= len(self.reference_trajectory) - 1:
                target_point = self.reference_trajectory[-1]
                break

            p1 = self.reference_trajectory[current_idx]
            p2 = self.reference_trajectory[current_idx + 1]
            d = distance(p1.x, p1.y, p2.x, p2.y)

            if accumulated_dist + d >= self.lookahead_distance:
                remaining = self.lookahead_distance - accumulated_dist
                ratio = remaining / d
                target_x = p1.x + (p2.x - p1.x) * ratio
                target_y = p1.y + (p2.y - p1.y) * ratio
                target_v = p1.velocity + (p2.velocity - p1.velocity) * ratio
                target_point = TrajectoryPoint(x=target_x, y=target_y, yaw=0.0, velocity=target_v)
                break

            accumulated_dist += d
            current_idx += 1
            target_point = self.reference_trajectory[current_idx]

        # Return a trajectory containing the target point
        return Trajectory(points=[target_point])

    def reset(self) -> bool:
        """Reset planner state.

        Returns:
            bool: True if reset was successful
        """
        return True
