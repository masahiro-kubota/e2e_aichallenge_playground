"""Tiny LiDAR Net node implementation."""

import logging

import numpy as np
from core.data.node_io import NodeIO
from core.data.ros import LaserScan
from core.interfaces.node import Node, NodeExecutionResult

from tiny_lidar_net.config import TinyLidarNetConfig
from tiny_lidar_net.core import TinyLidarNetCore


class TinyLidarNetNode(Node[TinyLidarNetConfig]):
    """Tiny LiDAR Net node for end-to-end autonomous driving control.

    This node subscribes to LiDAR scan data, processes it using the
    TinyLidarNetCore logic, and publishes control commands (AckermannControlCommand).
    """

    def __init__(self, config: TinyLidarNetConfig, rate_hz: float, priority: int) -> None:
        """Initialize Tiny LiDAR Net node.

        Args:
            config: Validated configuration
            rate_hz: Node execution rate [Hz]
            priority: Execution priority
        """
        super().__init__("TinyLidarNet", rate_hz, config, priority)

        self.logger = logging.getLogger(__name__)

        # Initialize core inference engine
        try:
            self.core = TinyLidarNetCore(
                input_dim=config.input_dim,
                output_dim=config.output_dim,
                architecture=config.architecture,
                ckpt_path=config.model_path,
                acceleration=config.fixed_acceleration,
                control_mode=config.control_mode,
                max_range=config.max_range,
            )
            self.logger.info(
                f"TinyLidarNetCore initialized. Architecture: {config.architecture}, "
                f"MaxRange: {config.max_range}"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize TinyLidarNetCore: {e}")
            raise

    def get_node_io(self) -> NodeIO:
        """Define node IO.

        Returns:
            NodeIO specification
        """
        from core.data import VehicleState
        from core.data.autoware import Trajectory

        return NodeIO(
            inputs={"perception_lidar_scan": LaserScan, "vehicle_state": VehicleState},
            outputs={"trajectory": Trajectory},
        )

    def on_run(self, _current_time: float) -> NodeExecutionResult:
        """Execute inference step."""

        # Get LiDAR scan from frame_data (now a LaserScan message)
        lidar_scan = self.subscribe("perception_lidar_scan")
        vehicle_state = self.subscribe("vehicle_state")

        if lidar_scan is None or vehicle_state is None:
            return NodeExecutionResult.SKIPPED

        # Extract ranges from LidarScan
        ranges = np.array(lidar_scan.ranges, dtype=np.float32)

        # Process via Core Logic (returns accel, steer but we only use steer)
        _, steer = self.core.process(ranges)

        # Create trajectory with steering-based lookahead point and fixed target velocity
        from core.data.autoware import Trajectory, TrajectoryPoint
        from core.data.ros import Point, Pose, Quaternion

        # Calculate lookahead point based on steering angle
        # Using simple kinematic model: lookahead distance = 2.0m
        lookahead_distance = 2.0
        target_velocity = 10.0  # Fixed target velocity [m/s]

        # Calculate target point position
        # For small angles: x ≈ lookahead_distance, y ≈ lookahead_distance * tan(steer)
        target_x = vehicle_state.x + lookahead_distance * np.cos(vehicle_state.yaw + steer)
        target_y = vehicle_state.y + lookahead_distance * np.sin(vehicle_state.yaw + steer)

        # Create trajectory with single point
        trajectory_point = TrajectoryPoint(
            pose=Pose(
                position=Point(x=target_x, y=target_y, z=0.0),
                orientation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0),
            ),
            longitudinal_velocity_mps=target_velocity,
            lateral_velocity_mps=0.0,
            acceleration_mps2=0.0,
            heading_rate_rps=0.0,
            front_wheel_angle_rad=steer,
            rear_wheel_angle_rad=0.0,
        )

        self.publish("trajectory", Trajectory(points=[trajectory_point]))

        return NodeExecutionResult.SUCCESS
