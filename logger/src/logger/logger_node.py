"""Logger node for recording FrameData."""

import json
import math
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from core.data import ComponentConfig, SimulationLog, SimulationStep
from core.data.node_io import NodeIO
from core.data.ros import (
    ColorRGBA,
    Header,
    LaserScan,
    Marker,
    MarkerArray,
    Odometry,
    Point,
    Pose,
    PoseWithCovariance,
    Quaternion,
    String,
    TFMessage,
    Time,
    Transform,
    TransformStamped,
    Twist,
    TwistWithCovariance,
    Vector3,
)
from core.interfaces.node import Node, NodeExecutionResult
from logger.mcap_logger import MCAPLogger


class LoggerConfig(ComponentConfig):
    """Configuration for LoggerNode."""

    output_mcap_path: str | None = None
    map_path: str | None = None  # Path to lanelet2 map (.osm)
    vehicle_params: Any = None  # Vehicle parameters for visualization (dict or VehicleParameters)


class LoggerNode(Node[LoggerConfig]):
    """Node responsible for recording FrameData to simulation log."""

    def __init__(self, config: LoggerConfig = LoggerConfig(), rate_hz: float = 10.0):
        """Initialize LoggerNode."""
        super().__init__("Logger", rate_hz, config)
        self.current_time = 0.0
        self.mcap_logger: MCAPLogger | None = None
        self.log = SimulationLog(steps=[], metadata={})
        self.map_published = False

    def on_init(self) -> None:
        """Initialize resources."""
        if self.config.output_mcap_path:
            from datetime import datetime

            mcap_path = Path(self.config.output_mcap_path)

            if mcap_path.is_dir() or (not mcap_path.exists() and not mcap_path.suffix):
                mcap_path.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                mcap_path = mcap_path / f"simulation_{timestamp}.mcap"

            self.mcap_logger = MCAPLogger(mcap_path)
            self.mcap_logger.__enter__()

            # Publish map immediately after MCAP initialization (once)
            if self.config.map_path:
                self._publish_map()
                self.map_published = True

    def on_shutdown(self) -> None:
        """Cleanup resources."""
        if self.mcap_logger:
            self.mcap_logger.__exit__(None, None, None)

    def get_node_io(self) -> NodeIO:
        """Define node IO."""
        return NodeIO(inputs={}, outputs={})

    def on_run(self, current_time: float) -> NodeExecutionResult:
        """Record current FrameData to log."""
        if self.frame_data is None:
            return NodeExecutionResult.SUCCESS

        self.current_time = current_time

        # --- Reconstruct SimulationStep for legacy EvaluationRunner ---
        # NOTE: This creates a partial step object just enough for evaluation metrics (collision, goal)
        # In a full refactor, evaluation should assume standard metrics, but for now we bridge it.
        # We only need to store minimal info for metrics if we wanted to save memory,
        # but to be safe we store what we can.
        from core.data import Action, VehicleState

        # Get vehicle state
        sim_state = getattr(self.frame_data, "sim_state", None)
        if sim_state is None:
            sim_state = VehicleState(x=0.0, y=0.0, yaw=0.0, velocity=0.0, timestamp=current_time)

        # Get action
        action = getattr(self.frame_data, "action", None)
        if action is None:
            action = Action(steering=0.0, acceleration=0.0)

        # Get info
        simulation_info = {
            "goal_count": getattr(self.frame_data, "goal_count", 0),
        }

        step = SimulationStep(
            timestamp=current_time,
            vehicle_state=sim_state,
            action=action,
            ad_component_log=None,  # Save memory
            info=simulation_info,
        )
        self.log.steps.append(step)

        if self.mcap_logger is None:
            return NodeExecutionResult.SUCCESS

        # --- ROS 2 Logging (MCAP) ---
        ros_time = self._to_ros_time(current_time)

        # 1. Vehicle State
        v_state = sim_state
        if v_state:
            q = self._quaternion_from_yaw(v_state.yaw)

            # TF: map -> base_link
            tf_msg = TFMessage(
                transforms=[
                    TransformStamped(
                        header=Header(stamp=ros_time, frame_id="map"),
                        child_frame_id="base_link",
                        transform=Transform(
                            translation=Vector3(x=v_state.x, y=v_state.y, z=0.0),
                            rotation=q,
                        ),
                    )
                ]
            )
            self.mcap_logger.log("/tf", tf_msg, current_time)

            # Odometry
            odom_msg = Odometry(
                header=Header(stamp=ros_time, frame_id="map"),
                child_frame_id="base_link",
                pose=PoseWithCovariance(
                    pose=Pose(
                        position=Point(x=v_state.x, y=v_state.y, z=0.0),
                        orientation=q,
                    )
                ),
                twist=TwistWithCovariance(
                    twist=Twist(linear=Vector3(x=v_state.velocity, y=0.0, z=0.0))
                ),
            )
            self.mcap_logger.log("/localization/kinematic_state", odom_msg, current_time)

            # Vehicle Marker (for visualization in Foxglove)
            from core.data.ros import Marker, MarkerArray

            # Get vehicle dimensions from config or use defaults
            if self.config.vehicle_params:
                vp = self.config.vehicle_params
                # Handle both dict and VehicleParameters object
                if hasattr(vp, "wheelbase"):
                    vehicle_length = vp.wheelbase + vp.front_overhang + vp.rear_overhang
                    vehicle_width = vp.width
                else:
                    vehicle_length = (
                        vp.get("wheelbase", 1.087)
                        + vp.get("front_overhang", 0.467)
                        + vp.get("rear_overhang", 0.51)
                    )
                    vehicle_width = vp.get("width", 1.3)
            else:
                vehicle_length = 2.5  # Default
                vehicle_width = 1.3
            vehicle_height = 1.5

            vehicle_marker = Marker(
                header=Header(stamp=ros_time, frame_id="map"),
                ns="vehicle",
                id=0,
                type=1,  # CUBE
                action=0,
                pose=Pose(
                    position=Point(x=v_state.x, y=v_state.y, z=vehicle_height / 2),
                    orientation=q,
                ),
                scale=Vector3(x=vehicle_length, y=vehicle_width, z=vehicle_height),
                color=ColorRGBA(r=0.0, g=0.5, b=1.0, a=0.8),
                frame_locked=True,
            )

            vehicle_marker_array = MarkerArray(markers=[vehicle_marker])
            self.mcap_logger.log("/vehicle/marker", vehicle_marker_array, current_time)

        # Obstacle Markers (for visualization in Foxglove)
        obstacles = getattr(self.frame_data, "obstacles", None)
        if obstacles and self.mcap_logger:
            obstacle_markers = []

            for idx, obs in enumerate(obstacles):
                # Get obstacle state at current time
                from simulator.obstacle import get_obstacle_state

                obs_state = get_obstacle_state(obs, current_time)

                # Create quaternion from yaw
                obs_q = self._quaternion_from_yaw(obs_state.yaw)

                # Determine marker type and scale based on obstacle shape
                if obs.shape.type == "rectangle":
                    marker_type = 1  # CUBE
                    scale = Vector3(
                        x=obs.shape.length,
                        y=obs.shape.width,
                        z=1.5,  # Default height
                    )
                elif obs.shape.type == "circle":
                    marker_type = 2  # SPHERE
                    scale = Vector3(
                        x=obs.shape.radius * 2, y=obs.shape.radius * 2, z=obs.shape.radius * 2
                    )
                else:
                    continue  # Skip unknown shapes

                obstacle_marker = Marker(
                    header=Header(stamp=ros_time, frame_id="map"),
                    ns="obstacles",
                    id=idx,
                    type=marker_type,
                    action=0,
                    pose=Pose(
                        position=Point(x=obs_state.x, y=obs_state.y, z=scale.z / 2),
                        orientation=obs_q,
                    ),
                    scale=scale,
                    color=ColorRGBA(r=1.0, g=0.0, b=0.0, a=0.7),  # Red for obstacles
                    frame_locked=True,
                )
                obstacle_markers.append(obstacle_marker)

            if obstacle_markers:
                obstacle_marker_array = MarkerArray(markers=obstacle_markers)
                self.mcap_logger.log("/obstacles/marker", obstacle_marker_array, current_time)

        # 2. LiDAR
        lidar_scan = getattr(self.frame_data, "lidar_scan", None)
        if lidar_scan:
            config = lidar_scan.config
            q_lidar = self._quaternion_from_yaw(config.yaw)

            # TF: base_link -> lidar_link
            tf_lidar = TFMessage(
                transforms=[
                    TransformStamped(
                        header=Header(stamp=ros_time, frame_id="base_link"),
                        child_frame_id="lidar_link",
                        transform=Transform(
                            translation=Vector3(x=config.x, y=config.y, z=config.z),
                            rotation=q_lidar,
                        ),
                    )
                ]
            )
            self.mcap_logger.log("/tf", tf_lidar, current_time)

            # LaserScan
            scan_msg = LaserScan(
                header=Header(stamp=self._to_ros_time(lidar_scan.timestamp), frame_id="lidar_link"),
                angle_min=-math.radians(config.fov) / 2,
                angle_max=math.radians(config.fov) / 2,
                angle_increment=math.radians(config.fov) / config.num_beams
                if config.num_beams > 0
                else 0.0,
                range_min=config.range_min,
                range_max=config.range_max,
                ranges=[
                    r if r != float("inf") and not math.isnan(r) else float("inf")
                    for r in lidar_scan.ranges
                ],
                intensities=lidar_scan.intensities or [],
            )
            self.mcap_logger.log("/perception/lidar/scan", scan_msg, lidar_scan.timestamp)

        # 3. Control Command
        if step.action:
            from core.data.ros import AckermannDrive, AckermannDriveStamped

            cmd_msg = AckermannDriveStamped(
                header=Header(stamp=ros_time, frame_id="base_link"),
                drive=AckermannDrive(
                    steering_angle=step.action.steering,
                    acceleration=step.action.acceleration,
                    speed=step.action.acceleration * 0.1,  # Dummy speed if not available directly
                ),
            )
            self.mcap_logger.log("/control/command/control_cmd", cmd_msg, current_time)

        # 3. Info (JSON)
        # Can add others here
        if simulation_info:
            self.mcap_logger.log(
                "/simulation/info", String(data=json.dumps(simulation_info)), current_time
            )

        return NodeExecutionResult.SUCCESS

    def get_log(self) -> SimulationLog:
        return self.log

    def _to_ros_time(self, t: float) -> Time:
        sec = int(t)
        nanosec = int((t - sec) * 1e9)

        # Ensure strict constraints for valid ROS time
        if nanosec < 0:
            nanosec = 0
        if nanosec >= 1_000_000_000:
            nanosec = 999_999_999

        return Time(sec=sec, nanosec=nanosec, nsec=nanosec)

    def _quaternion_from_yaw(self, yaw: float) -> Quaternion:
        return Quaternion(x=0.0, y=0.0, z=math.sin(yaw / 2), w=math.cos(yaw / 2))

    def _publish_map(self) -> None:
        """Parse Lanelet2 OSM and publish as Markers."""
        if not self.config.map_path or not Path(self.config.map_path).exists():
            return

        try:
            tree = ElementTree.parse(self.config.map_path)
            root = tree.getroot()

            # Parse nodes
            nodes: dict[str, dict[str, float]] = {}
            for node in root.findall("node"):
                nid = node.get("id")
                if not nid:
                    continue

                local_x = None
                local_y = None

                for tag in node.findall("tag"):
                    k = tag.get("k")
                    v = tag.get("v")
                    if k == "local_x" and v:
                        local_x = float(v)
                    elif k == "local_y" and v:
                        local_y = float(v)

                if local_x is not None and local_y is not None:
                    nodes[nid] = {"x": local_x, "y": local_y}

            # Parse ways (store for relation lookup)
            ways: dict[str, list[str]] = {}
            for way in root.findall("way"):
                way_id = way.get("id")
                if not way_id:
                    continue
                nds = [nd.get("ref") for nd in way.findall("nd") if nd.get("ref")]
                ways[way_id] = nds

            marker_array = MarkerArray()
            marker_id = 0

            # Parse relations (lanelets)
            for relation in root.findall("relation"):
                # Check if this is a lanelet
                is_lanelet = False
                for tag in relation.findall("tag"):
                    if tag.get("k") == "type" and tag.get("v") == "lanelet":
                        is_lanelet = True
                        break

                if not is_lanelet:
                    continue

                # Get left and right boundary ways
                left_way_id = None
                right_way_id = None

                for member in relation.findall("member"):
                    role = member.get("role")
                    ref = member.get("ref")
                    if role == "left" and ref:
                        left_way_id = ref
                    elif role == "right" and ref:
                        right_way_id = ref

                # Create marker for left boundary
                if left_way_id and left_way_id in ways:
                    valid_nds = [n for n in ways[left_way_id] if n in nodes]
                    if len(valid_nds) >= 2:
                        left_marker = Marker(
                            header=Header(
                                stamp=self._to_ros_time(self.current_time), frame_id="map"
                            ),
                            ns="lanelet_left",
                            id=marker_id,
                            type=4,  # LINE_STRIP
                            action=0,
                            scale=Vector3(x=0.15, y=0.0, z=0.0),
                            color=ColorRGBA(r=1.0, g=1.0, b=1.0, a=0.8),
                            pose=Pose(orientation=Quaternion(w=1.0)),
                            frame_locked=True,
                        )
                        for nd in valid_nds:
                            n = nodes[nd]
                            left_marker.points.append(Point(x=n["x"], y=n["y"], z=0.0))
                        marker_array.markers.append(left_marker)
                        marker_id += 1

                # Create marker for right boundary
                if right_way_id and right_way_id in ways:
                    valid_nds = [n for n in ways[right_way_id] if n in nodes]
                    if len(valid_nds) >= 2:
                        right_marker = Marker(
                            header=Header(
                                stamp=self._to_ros_time(self.current_time), frame_id="map"
                            ),
                            ns="lanelet_right",
                            id=marker_id,
                            type=4,  # LINE_STRIP
                            action=0,
                            scale=Vector3(x=0.15, y=0.0, z=0.0),
                            color=ColorRGBA(r=0.8, g=0.8, b=0.8, a=0.8),
                            pose=Pose(orientation=Quaternion(w=1.0)),
                            frame_locked=True,
                        )
                        for nd in valid_nds:
                            n = nodes[nd]
                            right_marker.points.append(Point(x=n["x"], y=n["y"], z=0.0))
                        marker_array.markers.append(right_marker)
                        marker_id += 1

            # Publish
            if self.mcap_logger and marker_array.markers:
                self.mcap_logger.log("/map/vector", marker_array, self.current_time)

        except Exception as e:
            print(f"Failed to load/publish map: {e}")
