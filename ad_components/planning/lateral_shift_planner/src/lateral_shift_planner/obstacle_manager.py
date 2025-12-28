import math
from dataclasses import dataclass

from core.data.ad_components import VehicleState
from core.data.environment.obstacle import Obstacle

from lateral_shift_planner.frenet_converter import FrenetConverter


@dataclass
class TargetObstacle:
    """Obstacle filtered for avoidance."""

    id: str
    s: float
    lat: float
    length: float
    width: float
    left_boundary_dist: float  # Distance from obstacle to left road boundary [m]
    right_boundary_dist: float  # Distance from obstacle to right road boundary [m]
    raw: Obstacle | None = None


class ObstacleManager:
    """Manages obstacle filtering and projection."""

    def __init__(
        self,
        converter: FrenetConverter,
        road_map,  # RoadWidthMap instance
        lookahead_distance: float = 30.0,
        road_width: float = 6.0,
        vehicle_width: float = 2.0,
        safe_margin: float = 0.5,
    ):
        """Initialize ObstacleManager.

        Args:
            converter: FrenetConverter instance
            road_map: RoadWidthMap instance for boundary calculations
            lookahead_distance: Max distance to consider obstacles [m]
            road_width: Total road width [m]
            vehicle_width: Ego vehicle width [m]
            safe_margin: Safety margin [m]
        """
        self.converter = converter
        self.road_map = road_map
        self.lookahead = lookahead_distance
        self.road_width = road_width
        self.vehicle_width = vehicle_width
        self.safe_margin = safe_margin

    def get_target_obstacles(
        self, ego_state: VehicleState, obstacles: list[Obstacle], _road_width: float = 6.0
    ) -> list[TargetObstacle]:
        """Convert obstacles to Frenet frame and filter.

        Args:
            ego_state: Current vehicle state
            obstacles: List of detected obstacles
            _road_width: Current road width [m] (unused)

        Returns:
            List of TargetObstacle
        """
        targets = []

        # Ego position in Frenet
        s_ego, _ = self.converter.global_to_frenet(ego_state.x, ego_state.y)

        for obs in obstacles:
            # Convert to Frenet
            s_obj, _ = self.converter.global_to_frenet(obs.x, obs.y)

            # 1. Forward check
            # TODO: Handle wrap-around scenarios properly.
            # For now simple check. If s_obj < s_ego, it might be behind
            # or very far ahead in looped track (but s usually increases monotonically).
            # Assuming s represents linear distance on current lap.
            if s_obj <= s_ego:
                continue

            # 2. Distance check
            dist = s_obj - s_ego
            if dist > self.lookahead:
                continue

            # Map dimensions with YAW consideration
            # Calculate Frenet Bounding Box
            # 1. Get 4 corners in Global Frame
            # Obstacle has width (lateral) and height (longitudinal)
            # Local frame: x-axis is forward (height/length), y-axis is lateral (width)
            half_length = obs.height / 2.0
            half_width = obs.width / 2.0

            corners_local = [
                (half_length, half_width),
                (half_length, -half_width),
                (-half_length, -half_width),
                (-half_length, half_width),
            ]

            ct = math.cos(obs.yaw)
            st = math.sin(obs.yaw)

            s_vals = []
            l_vals = []

            for cx, cy in corners_local:
                # Rotate
                gx = cx * ct - cy * st + obs.x
                gy = cx * st + cy * ct + obs.y

                # Convert to Frenet
                cs, cl = self.converter.global_to_frenet(gx, gy)
                s_vals.append(cs)
                l_vals.append(cl)

            # 4. Determine Frenet Bounding Box
            s_min = min(s_vals)
            s_max = max(s_vals)
            l_min = min(l_vals)
            l_max = max(l_vals)

            # 5. Calculate effective dimensions in Frenet
            length_frenet = s_max - s_min
            width_frenet = l_max - l_min
            s_center_frenet = (s_min + s_max) / 2.0
            l_center_frenet = (l_min + l_max) / 2.0

            # Get road boundaries at obstacle position
            # Use obstacle's global position and yaw from centerline
            # Get position at obstacle's s position from centerline
            obs_global_x, obs_global_y = self.converter.frenet_to_global(
                s_center_frenet, l_center_frenet
            )

            boundaries = self.road_map.get_lateral_boundaries(obs_global_x, obs_global_y)
            if boundaries is not None:
                left_boundary_dist, right_boundary_dist = boundaries
            else:
                # Fallback: use symmetric road width
                left_boundary_dist = self.road_width / 2.0
                right_boundary_dist = self.road_width / 2.0

            targets.append(
                TargetObstacle(
                    id=obs.id,
                    s=s_center_frenet,
                    lat=l_center_frenet,
                    length=length_frenet,
                    width=width_frenet,
                    left_boundary_dist=left_boundary_dist,
                    right_boundary_dist=right_boundary_dist,
                    raw=obs,
                )
            )

        # Sort by distance (s)
        targets.sort(key=lambda o: o.s)

        if len(targets) > 0:
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"[ObstacleManager] Found {len(targets)} targets:")
            for t in targets:
                logger.info(
                    f"  ID={t.id} s={t.s:.2f} l={t.lat:.2f} w={t.width:.2f} l_raw={t.raw.x:.1f},{t.raw.y:.1f}"
                )

        return targets
