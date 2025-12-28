import logging
import math
from pathlib import Path

from core.data import ComponentConfig, VehicleState
from core.data.ad_components import Trajectory
from core.data.node_io import NodeIO

# ROS Data Imports
from core.data.ros import (
    ColorRGBA,
    Header,
    Marker,
    MarkerArray,
    Point,
    Pose,
    Quaternion,
    Vector3,
)
from core.interfaces.node import Node, NodeExecutionResult
from core.utils.ros_message_builder import to_ros_time
from planning_utils import load_track_csv
from pydantic import Field

from static_avoidance_planner.avoidance_planner import AvoidancePlanner, AvoidancePlannerConfig

logger = logging.getLogger(__name__)


class AvoidancePlannerNodeConfig(ComponentConfig):
    """Configuration for AvoidancePlannerNode."""

    track_path: Path = Field(..., description="Path to reference trajectory CSV")
    map_path: Path = Field(..., description="Path to Lanelet2 map file")

    # Avoidance params
    lookahead_distance: float = Field(..., description="Lookahead distance [m]")
    avoidance_maneuver_length: float = Field(
        ..., description="Obstacle avoidance activation distance [m]"
    )
    longitudinal_margin_front: float = Field(..., description="Front margin distance [m]")
    longitudinal_margin_rear: float = Field(..., description="Rear margin distance [m]")
    road_width: float = Field(..., description="Road width [m]")
    vehicle_width: float = Field(..., description="Vehicle width [m]")
    safe_margin: float = Field(..., description="Safety margin [m]")
    trajectory_resolution: float = Field(..., description="Trajectory output resolution [m]")

    # Visualization
    trajectory_color: str = Field("#00FF00CC", description="Trajectory color")


class AvoidancePlannerNode(Node[AvoidancePlannerNodeConfig]):
    """ROS 2 Node for static avoidance planning."""

    def __init__(self, config: AvoidancePlannerNodeConfig, rate_hz: float):
        super().__init__("AvoidancePlanner", rate_hz, config)

        # Load map
        from core.utils import get_project_root

        track_path = self.config.track_path
        if not track_path.is_absolute():
            track_path = get_project_root() / track_path

        map_path = self.config.map_path
        if not map_path.is_absolute():
            map_path = get_project_root() / map_path

        ref_path = load_track_csv(track_path)

        # Init map utils
        from static_avoidance_planner.map_utils import RoadWidthMap

        logger.info(f"Initializing AvoidancePlanner with map: {map_path}")
        self.road_map = RoadWidthMap(map_path)

        # Init planner
        planner_config = AvoidancePlannerConfig(
            lookahead_distance=self.config.lookahead_distance,
            avoidance_maneuver_length=self.config.avoidance_maneuver_length,
            longitudinal_margin_front=self.config.longitudinal_margin_front,
            longitudinal_margin_rear=self.config.longitudinal_margin_rear,
            road_width=self.config.road_width,
            vehicle_width=self.config.vehicle_width,
            safe_margin=self.config.safe_margin,
            trajectory_resolution=self.config.trajectory_resolution,
        )
        self.planner = AvoidancePlanner(ref_path, planner_config)

    def get_node_io(self) -> NodeIO:
        # from core.data.environment.obstacle import Obstacle
        # We need generic inputs to accept list of diverse types potentially,
        # or use Any if SimulatorObstacle is not easily typed in NodeIO without importing it.
        # But Simulator outputs 'obstacles' as list[SimulatorObstacle].
        # Let's use Any for obstacles input to avoid import issues or strict type checking failures at runtime.
        from typing import Any

        from core.data.ros import MarkerArray

        return NodeIO(
            inputs={
                "vehicle_state": VehicleState,
                "obstacles": Any,  # list[SimulatorObstacle]
                "obstacle_states": Any,  # list[ObstacleState]
            },
            outputs={"trajectory": Trajectory, "planning_marker": MarkerArray},
        )

    def on_run(self, _current_time: float) -> NodeExecutionResult:
        if self.frame_data is None:
            return NodeExecutionResult.FAILED

        vehicle_state = getattr(self.frame_data, "vehicle_state", None)
        # raw_obstacles is list[SimulatorObstacle]
        raw_obstacles = getattr(self.frame_data, "obstacles", None)
        # raw_obstacle_states is list[ObstacleState]
        raw_obstacle_states = getattr(self.frame_data, "obstacle_states", None)

        if vehicle_state is None:
            return NodeExecutionResult.SKIPPED

        # Convert to Sensing-like Obstacle list
        from core.data.environment.obstacle import Obstacle, ObstacleType

        converted_obstacles = []
        if raw_obstacles and raw_obstacle_states and len(raw_obstacles) == len(raw_obstacle_states):
            for i, (sim_obs, state) in enumerate(zip(raw_obstacles, raw_obstacle_states)):
                # Parse shape
                width = 1.0
                height = 1.0
                if hasattr(sim_obs, "shape"):
                    if sim_obs.shape.type == "rectangle":
                        width = sim_obs.shape.width if sim_obs.shape.width else 1.0
                        height = sim_obs.shape.length if sim_obs.shape.length else 1.0
                    elif sim_obs.shape.type == "circle":
                        r = sim_obs.shape.radius if sim_obs.shape.radius else 0.5
                        width = r * 2
                        height = r * 2

                # Create Obstacle
                # Use "static" as default type for now if not present, but SimulatorObstacle has type.
                obs_type = ObstacleType.STATIC
                if hasattr(sim_obs, "type") and sim_obs.type == "dynamic":
                    obs_type = ObstacleType.DYNAMIC

                converted_obstacles.append(
                    Obstacle(
                        id=str(
                            i
                        ),  # Use index as ID since SimulatorObstacle might not have it or it's complex
                        type=obs_type,
                        x=state.x,
                        y=state.y,
                        width=width,
                        height=height,  # Interpreted as length (longitudinal)
                        yaw=state.yaw,
                        velocity=0.0,  # Simulator doesn't provide vel directly in State?
                    )
                )

        # Dynamic road width
        road_width = self.config.road_width  # Fallback

        width = self.road_map.get_lateral_width(vehicle_state.x, vehicle_state.y, vehicle_state.yaw)
        if width is not None:
            road_width = width

        # DEBUG LOGGING
        logger.info(
            f"[AvoidancePlanner] Pos: ({vehicle_state.x:.2f}, {vehicle_state.y:.2f}), Road Width: {road_width:.2f}"
        )

        # Plan
        debug_data = self.planner.plan(vehicle_state, converted_obstacles, road_width)
        trajectory = debug_data.trajectory

        logger.info(f"[AvoidancePlanner] Generated Trajectory Points: {len(trajectory.points)}")
        if len(trajectory.points) > 0:
            p0 = trajectory.points[0]
            logger.info(f"  Start Point: ({p0.x:.2f}, {p0.y:.2f})")

        # Output
        self.frame_data.trajectory = trajectory

        # Visualize
        ros_time = to_ros_time(_current_time)
        markers = []

        # 0. Clear previous markers (DELETEALL)
        for ns in ["trajectory", "target_obstacles", "shift_points", "shift_profiles"]:
            markers.append(
                Marker(
                    header=Header(stamp=ros_time, frame_id="map"),
                    ns=ns,
                    id=0,
                    type=0,  # ARROW (dummy)
                    action=3,  # DELETEALL
                )
            )

        # 1. Trajectory Marker
        points = [Point(x=p.x, y=p.y, z=0.0) for p in trajectory.points]
        markers.append(
            Marker(
                header=Header(stamp=ros_time, frame_id="map"),
                ns="trajectory",
                id=0,
                type=4,  # LINE_STRIP
                action=0,
                scale=Vector3(x=0.2, y=0.0, z=0.0),
                color=ColorRGBA.from_hex(self.config.trajectory_color),
                points=points,
                frame_locked=True,
            )
        )

        # 2. Debug Markers (Shift Profiles & Targets)
        # Using planner's converter to map s,l back to global
        converter = self.planner.converter

        for i, profile in enumerate(debug_data.shift_profiles):
            # Target Obstacle Marker
            obs = profile.obs

            corner_points = []

            if obs.raw:
                # Use raw obstacle data for accurate visualization (Global State)
                # Raw obs has x, y (center), width, height (dims), yaw

                # Corners in local frame (unrotated)
                # length is height (longitudinal), width is width (lateral) relative to yaw
                # Wait, Obstacle definition:
                # width: lateral, height: longitudinal? Or standard?
                # Usually: length (x-axis in local), width (y-axis in local).
                # Obstacle dataclass has width/height.
                # Let's assume height=length (longitudinal/forward-backward), width=width.

                l_half = obs.raw.width / 2.0
                s_half = obs.raw.height / 2.0

                # Local corners
                local_corners = [
                    (s_half, l_half),
                    (s_half, -l_half),
                    (-s_half, -l_half),
                    (-s_half, l_half),
                    (s_half, l_half),
                ]

                ct = math.cos(obs.raw.yaw)
                st = math.sin(obs.raw.yaw)

                for lx, ly in local_corners:
                    # Rotate and translate
                    gx = lx * ct - ly * st + obs.raw.x
                    gy = lx * st + ly * ct + obs.raw.y
                    corner_points.append(Point(x=gx, y=gy, z=0.0))

            else:
                # Fallback to Frenet reconstruction (less accurate orientation)
                l_half = obs.width / 2.0
                s_half = obs.length / 2.0

                corners_sl = [
                    (obs.s - s_half, obs.l - l_half),
                    (obs.s + s_half, obs.l - l_half),
                    (obs.s + s_half, obs.l + l_half),
                    (obs.s - s_half, obs.l + l_half),
                    (obs.s - s_half, obs.l - l_half),
                ]

                for cs, cl in corners_sl:
                    gx, gy = converter.frenet_to_global(cs, cl)
                    corner_points.append(Point(x=gx, y=gy, z=0.0))

            markers.append(
                Marker(
                    header=Header(stamp=ros_time, frame_id="map"),
                    ns="target_obstacles",
                    id=i,
                    type=4,  # LINE_STRIP
                    action=0,
                    scale=Vector3(x=0.1, y=0.0, z=0.0),
                    color=ColorRGBA.from_hex("#FF0000CC"),  # Red for targets
                    points=corner_points,
                    frame_locked=True,
                )
            )

            # Shift Profile Markers: REMOVED per user feedback (too cluttered)
            # Instead, we visualize the MERGED profile below.

            # --- Restoration of Shift Point Text Markers (per user request) ---
            # We visualize key points (S, L) for each profile to aid debugging.
            # Define point types and their corresponding s values
            point_defs = [
                ("Start", profile.s_start_action),
                ("Full", profile.s_full_avoid),
                ("Keep", profile.s_keep_avoid),
                ("End", profile.s_end_action),
            ]

            for label, s_sample in point_defs:
                l_req = profile.get_lat(s_sample)
                gx, gy = converter.frenet_to_global(s_sample, l_req)

                # Text Marker for each point
                markers.append(
                    Marker(
                        header=Header(stamp=ros_time, frame_id="map"),
                        ns="shift_points",
                        id=i * 100 + int(s_sample),  # Value-based ID
                        type=9,  # TEXT_VIEW_FACING
                        action=0,
                        scale=Vector3(x=0.0, y=0.0, z=0.5),  # Height of text
                        color=ColorRGBA.from_hex("#FFFF00CC"),
                        pose=Pose(
                            position=Point(x=gx, y=gy, z=1.0),
                            orientation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0),
                        ),
                        points=[],
                        text=f"{label}\nS:{s_sample:.1f}\nL:{l_req:.1f}",
                    )
                )

        # B. Merged Shift Profile (Single Line)
        if debug_data.s_samples is not None and debug_data.merged_lat is not None:
            merged_points = []
            for s, lat in zip(debug_data.s_samples, debug_data.merged_lat):
                # Visualize the "Required Lateral Position" (Centerline + L)
                gx, gy = converter.frenet_to_global(s, lat)
                merged_points.append(Point(x=gx, y=gy, z=0.0))

            markers.append(
                Marker(
                    header=Header(stamp=ros_time, frame_id="map"),
                    ns="shift_profiles",  # Reusing ns to look like the main plan
                    id=0,  # One single line
                    type=4,  # LINE_STRIP
                    action=0,
                    scale=Vector3(x=0.15, y=0.0, z=0.0),  # Slightly thicker and distinct
                    color=ColorRGBA.from_hex("#FFFF00CC"),  # Yellow
                    points=merged_points,
                    frame_locked=True,
                )
            )

        # Assign to planning_marker to match NodeIO output
        self.frame_data.planning_marker = MarkerArray(markers=markers)

        return NodeExecutionResult.SUCCESS
