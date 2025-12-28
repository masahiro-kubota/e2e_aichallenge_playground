from dataclasses import dataclass

from core.data.ad_components import VehicleState
from core.data.environment.obstacle import Obstacle

from static_avoidance_planner.frenet_converter import FrenetConverter


@dataclass
class TargetObstacle:
    """Obstacle filtered for avoidance."""

    id: str
    s: float
    lat: float
    length: float
    length: float
    width: float
    raw: Obstacle | None = None


class ObstacleManager:
    """Manages obstacle filtering and projection."""

    def __init__(
        self,
        converter: FrenetConverter,
        lookahead_distance: float = 30.0,
        road_width: float = 6.0,
        vehicle_width: float = 2.0,
        safe_margin: float = 0.5,
    ):
        """Initialize ObstacleManager.

        Args:
            converter: FrenetConverter instance
            lookahead_distance: Max distance to consider obstacles [m]
            road_width: Total road width [m]
            vehicle_width: Ego vehicle width [m]
            safe_margin: Safety margin [m]
        """
        self.converter = converter
        self.lookahead = lookahead_distance
        self.road_width = road_width
        self.vehicle_width = vehicle_width
        self.safe_margin = safe_margin

    def get_target_obstacles(
        self, ego_state: VehicleState, obstacles: list[Obstacle], road_width: float = 6.0
    ) -> list[TargetObstacle]:
        """Convert obstacles to Frenet frame and filter.

        Args:
            ego_state: Current vehicle state
            obstacles: List of detected obstacles
            road_width: Current road width [m]

        Returns:
            List of TargetObstacle
        """
        targets = []

        # Ego position in Frenet
        s_ego, _ = self.converter.global_to_frenet(ego_state.x, ego_state.y)

        for obs in obstacles:
            # Convert to Frenet
            s_obj, l_obj = self.converter.global_to_frenet(obs.x, obs.y)

            # 1. Forward check
            # TODO: Handle wrap-around scenarios properly.
            # For now simple check. If s_obj < s_ego, it might be behind
            # or very far ahead in looped track (but s usually increases monotonically).
            # Assuming s represents linear distance on current lap.
            if s_obj <= s_ego:
                continue

            # 2. Distance check
            if s_obj - s_ego > self.lookahead:
                continue

            # 3. Lateral position check
            # Check lateral position (within road width)
            # Utilizing dynamic road_width if provided, otherwise default from self.road_width (if we want to keep it)
            # Actually, let's use the passed road_width.
            # safe_margin is included in ShiftProfile, but for filtering we check if it is ON ROAD.
            # Assuming center of road is l=0, road edges are +/- road_width/2.
            if abs(l_obj) > road_width / 2.0:
                continue

            # Map dimensions
            # Assuming obs.height is length (longitudinal) and obs.width is lateral
            length = obs.height
            width = obs.width

            targets.append(
                TargetObstacle(id=obs.id, s=s_obj, lat=l_obj, length=length, width=width, raw=obs)
            )

        # Sort by distance (s)
        targets.sort(key=lambda o: o.s)

        return targets
