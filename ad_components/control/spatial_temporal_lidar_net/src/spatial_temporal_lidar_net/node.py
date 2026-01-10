import logging
from collections import deque

import numpy as np
import torch
from core.data.node_io import NodeIO
from core.data.ros import LaserScan
from core.interfaces.node import Node, NodeExecutionResult

from spatial_temporal_lidar_net.config import SpatialTemporalLidarNetConfig
from spatial_temporal_lidar_net.model import SpatialTemporalLidarNet


class SpatialTemporalLidarNetNode(Node[SpatialTemporalLidarNetConfig]):
    """Spatial-Temporal LiDAR Net node/agent."""

    def __init__(
        self, config: SpatialTemporalLidarNetConfig, rate_hz: float, priority: int
    ) -> None:
        super().__init__("SpatialTemporalLidarNet", rate_hz, config, priority)

        self.logger = logging.getLogger(__name__)

        self.model_path = config.model_path
        self.num_frames = config.num_frames
        self.max_range = config.max_range
        self.target_velocity = config.target_velocity

        # Device
        device_str = config.device
        self.device = torch.device(
            device_str if torch.cuda.is_available() and device_str == "cuda" else "cpu"
        )

        # Load Model
        self.model = SpatialTemporalLidarNet(num_frames=self.num_frames)
        try:
            state_dict = torch.load(self.model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.model.to(self.device)
            self.model.eval()
            self.logger.info(f"Loaded model from {self.model_path} to {self.device}")
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            raise

        # Buffer
        self.scan_buffer = deque(maxlen=self.num_frames)

    def get_node_io(self) -> NodeIO:
        from core.data import VehicleState
        from core.data.autoware import AckermannControlCommand

        return NodeIO(
            inputs={"perception_lidar_scan": LaserScan, "vehicle_state": VehicleState},
            outputs={"control_cmd": AckermannControlCommand},
        )

    def on_run(self, _current_time: float) -> NodeExecutionResult:
        # Inputs
        lidar_scan = self.subscribe("perception_lidar_scan")
        vehicle_state = self.subscribe("vehicle_state")

        if lidar_scan is None or vehicle_state is None:
            return NodeExecutionResult.SKIPPED

        # Preprocess Scan
        # ranges = np.array(lidar_scan.ranges, dtype=np.float32)
        # Handle Inf/Nan and clip
        ranges = np.nan_to_num(np.array(lidar_scan.ranges), posinf=self.max_range, neginf=0.0)
        ranges = np.clip(ranges, 0.0, self.max_range)
        normalized_ranges = (ranges / self.max_range).astype(np.float32)

        # Buffer Update
        self.scan_buffer.append(normalized_ranges)

        # Prepare Input
        current_buffer = list(self.scan_buffer)
        while len(current_buffer) < self.num_frames:
            # Padding with oldest available
            current_buffer.insert(0, current_buffer[0])

        input_np = np.array(current_buffer, dtype=np.float32)  # (K, W)
        input_tensor = (
            torch.from_numpy(input_np).unsqueeze(0).unsqueeze(0).to(self.device)
        )  # (1, 1, K, W)

        # Inference
        with torch.no_grad():
            output = self.model(input_tensor)
            steer = output.item()

        # Velocity Control (P-Control)
        current_velocity = vehicle_state.velocity
        velocity_error = self.target_velocity - current_velocity
        kp_velocity = 1.0
        acceleration = kp_velocity * velocity_error
        acceleration = max(-3.0, min(3.0, acceleration))  # Clip

        # Output Command
        from core.data.autoware import (
            AckermannControlCommand,
            AckermannLateralCommand,
            LongitudinalCommand,
        )
        from core.utils.ros_message_builder import to_ros_time

        self.publish(
            "control_cmd",
            AckermannControlCommand(
                stamp=to_ros_time(_current_time),
                lateral=AckermannLateralCommand(
                    stamp=to_ros_time(_current_time), steering_tire_angle=steer
                ),
                longitudinal=LongitudinalCommand(
                    stamp=to_ros_time(_current_time),
                    acceleration=acceleration,
                    speed=self.target_velocity,
                ),
            ),
        )

        return NodeExecutionResult.SUCCESS
