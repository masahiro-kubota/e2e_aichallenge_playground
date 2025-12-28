import math
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

            # Map dimensions with YAW consideration
            # Calculate Frenet Bounding Box
            # 1. Get 4 corners in Global Frame
            # length (longitudinal dim), width (lateral dim)
            half_l = obs.height / 2.0  # length
            half_w = obs.width / 2.0  # width

            corners_local = [
                (half_l, half_w),
                (half_l, -half_w),
                (-half_l, -half_w),
                (-half_l, half_w),
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

            # 2. Compute effective dimensions in Frenet Frame
            s_min = min(s_vals)
            s_max = max(s_vals)
            l_min = min(l_vals)
            l_max = max(l_vals)

            # Effective width and length in Frenet Frame
            width_frenet = l_max - l_min
            length_frenet = s_max - s_min

            # Use Frenet Center for checks or keep center?
            # ShiftProfile uses obstacle.lat as center.
            # Ideally use (l_min + l_max) / 2 as the effective center in Frenet.
            l_center_frenet = (l_min + l_max) / 2.0
            s_center_frenet = (s_min + s_max) / 2.0

            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"O({obs.id}): Yaw={obs.yaw:.2f}, L_range=[{l_min:.2f}, {l_max:.2f}], W_eff={width_frenet:.2f}, L_center={l_center_frenet:.2f}"
            )

            targets.append(
                TargetObstacle(
                    id=obs.id,
                    s=s_center_frenet,
                    lat=l_center_frenet,
                    length=length_frenet,
                    width=width_frenet,
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
