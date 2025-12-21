"""MCAP logger for simulation data."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from mcap.writer import Writer

from core.data import SimulationStep


class MCAPLogger:
    """MCAP format logger for simulation data."""

    def __init__(self, output_path: str | Path) -> None:
        """Initialize MCAP logger.

        Args:
            output_path: Output file path (.mcap)
        """
        self.output_path = Path(output_path)
        self.file: Any = None
        self.writer: Writer | None = None
        self.schema_id: int | None = None
        self.channel_id: int | None = None

    def __enter__(self) -> "MCAPLogger":
        """Open MCAP file for writing."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(self.output_path, "wb")
        self.writer = Writer(self.file)
        self.writer.start()

        # Register schema with detailed field definitions
        # Note: Foxglove doesn't support array-style type definitions like ["number", "null"]
        # so we use simple "number" type for nullable fields
        self.schema_id = self.writer.register_schema(
            name="SimulationStep",
            encoding="jsonschema",
            data=json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "timestamp": {
                            "type": "number",
                            "description": "Simulation timestamp in seconds",
                        },
                        "vehicle_state": {
                            "type": "object",
                            "description": "Current vehicle state",
                            "properties": {
                                "x": {"type": "number", "description": "X position [m]"},
                                "y": {"type": "number", "description": "Y position [m]"},
                                "yaw": {"type": "number", "description": "Yaw angle [rad]"},
                                "velocity": {"type": "number", "description": "Velocity [m/s]"},
                                "acceleration": {
                                    "type": "number",
                                    "description": "Acceleration [m/s^2]",
                                },
                                "steering": {
                                    "type": "number",
                                    "description": "Steering angle [rad]",
                                },
                                "timestamp": {
                                    "type": "number",
                                    "description": "State timestamp [s]",
                                },
                                "off_track": {
                                    "type": "boolean",
                                    "description": "Off-track flag",
                                },
                                "collision": {
                                    "type": "boolean",
                                    "description": "Collision flag",
                                },
                            },
                        },
                        "action": {
                            "type": "object",
                            "description": "Control action",
                            "properties": {
                                "steering": {
                                    "type": "number",
                                    "description": "Steering command [rad]",
                                },
                                "acceleration": {
                                    "type": "number",
                                    "description": "Acceleration command [m/s^2]",
                                },
                                "timestamp": {
                                    "type": "number",
                                    "description": "Action timestamp [s]",
                                },
                            },
                        },
                        "ad_component_log": {
                            "type": "object",
                            "description": "AD component log data",
                            "properties": {
                                "component_type": {
                                    "type": "string",
                                    "description": "Component type (planner/controller/e2e)",
                                },
                                "data": {
                                    "type": "object",
                                    "description": "Component-specific log data",
                                },
                            },
                        },
                        "info": {
                            "type": "object",
                            "description": "Additional simulation info",
                            "properties": {
                                "goal_count": {
                                    "type": "number",
                                    "description": "Reached goal count",
                                },
                                "obstacle_states": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "x": {"type": "number"},
                                            "y": {"type": "number"},
                                            "yaw": {"type": "number"},
                                            "timestamp": {"type": "number"},
                                        },
                                    },
                                    "description": "Obstacle states at timestamp",
                                },
                            },
                        },
                    },
                }
            ).encode(),
        )

        # Register channel
        self.channel_id = self.writer.register_channel(
            topic="/simulation/step",
            message_encoding="json",
            schema_id=self.schema_id,
        )

        # Register Foxglove LaserScan schema
        self.lidar_schema_id = self.writer.register_schema(
            name="foxglove.LaserScan",
            encoding="jsonschema",
            data=json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "timestamp": {
                            "type": "object",
                            "properties": {
                                "sec": {"type": "integer"},
                                "nsec": {"type": "integer"},
                            },
                        },
                        "frame_id": {"type": "string"},
                        "pose": {
                            "type": "object",
                            "properties": {
                                "position": {
                                    "type": "object",
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"},
                                        "z": {"type": "number"},
                                    },
                                },
                                "orientation": {
                                    "type": "object",
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"},
                                        "z": {"type": "number"},
                                        "w": {"type": "number"},
                                    },
                                },
                            },
                        },
                        "start_angle": {"type": "number"},
                        "end_angle": {"type": "number"},
                        "ranges": {"type": "array", "items": {"type": "number"}},
                        "intensities": {"type": "array", "items": {"type": "number"}},
                    },
                }
            ).encode(),
        )

        # Register LiDAR channel
        self.lidar_channel_id = self.writer.register_channel(
            topic="/sensors/lidar",
            message_encoding="json",
            schema_id=self.lidar_schema_id,
        )

        return self

    def log_step(self, step: SimulationStep) -> bool:
        """Log a simulation step.

        Args:
            step: Simulation step to log

        Returns:
            bool: True if logging was successful
        """
        if self.writer is None or self.channel_id is None:
            msg = "Logger not initialized. Use 'with MCAPLogger(...) as logger:'"
            raise RuntimeError(msg)

        data = {
            "timestamp": step.timestamp,
            "vehicle_state": asdict(step.vehicle_state),
            "action": asdict(step.action),
            "ad_component_log": asdict(step.ad_component_log) if step.ad_component_log else None,
            "info": step.info,
        }

        self.writer.add_message(
            channel_id=self.channel_id,
            log_time=int(step.timestamp * 1e9),  # nanoseconds
            data=json.dumps(data).encode(),
            publish_time=int(step.timestamp * 1e9),
        )

        # Publish LiDAR data if available
        if (
            self.lidar_channel_id is not None
            and "lidar_scan" in step.info
            and step.info["lidar_scan"]
        ):
            self._log_lidar(step, step.info["lidar_scan"])

        return True

    def _log_lidar(self, step: SimulationStep, scan_data: dict[str, Any]) -> None:
        """Log LiDAR data to separate channel."""
        import math

        timestamp = step.timestamp
        # Helper to convert timestamp
        sec = int(timestamp)
        nsec = int((timestamp - sec) * 1e9)

        config = scan_data["config"]
        fov = math.radians(config["fov"])
        # Assuming FOV is centered around 0 (front)
        start_angle = -fov / 2
        end_angle = fov / 2

        # Compute Global Pose
        # Lidar Pose = Vehicle Pose * Mounting Offset
        # We need vehicle state
        v_state = step.vehicle_state

        # Mounting config
        mx = config.get("x", 0.0)
        my = config.get("y", 0.0)
        mz = config.get("z", 0.0)
        myaw = config.get("yaw", 0.0)

        # Vehicle state
        vx = v_state.x
        vy = v_state.y
        vyaw = v_state.yaw

        # Transform mounting offset to global frame
        # GlobalX = VX + (MX * cos(VYaw) - MY * sin(VYaw))
        # globally = VY + (MX * sin(VYaw) + MY * cos(VYaw))
        cos_vy = math.cos(vyaw)
        sin_vy = math.sin(vyaw)

        global_x = vx + (mx * cos_vy - my * sin_vy)
        global_y = vy + (mx * sin_vy + my * cos_vy)
        global_z = mz  # Assuming flat ground for vehicle, so just Z offset.
        global_yaw = vyaw + myaw

        # Convert Global Yaw to Quaternion
        cz = math.cos(global_yaw * 0.5)
        sz = math.sin(global_yaw * 0.5)

        # Handle Infinity in ranges
        ranges = scan_data["ranges"]
        range_max = config.get("range_max", 100.0)
        safe_ranges = [r if r != float("inf") and not math.isnan(r) else range_max for r in ranges]

        message = {
            "timestamp": {"sec": sec, "nsec": nsec},
            "frame_id": "map",  # Use map frame for visualization without TFs
            "pose": {
                "position": {
                    "x": global_x,
                    "y": global_y,
                    "z": global_z,
                },
                "orientation": {"x": 0, "y": 0, "z": sz, "w": cz},
            },
            "start_angle": start_angle,
            "end_angle": end_angle,
            "ranges": safe_ranges,
            "intensities": scan_data.get("intensities") or [],
        }

        self.writer.add_message(
            channel_id=self.lidar_channel_id,
            log_time=int(timestamp * 1e9),
            data=json.dumps(message).encode(),
            publish_time=int(timestamp * 1e9),
        )

    def __exit__(self, *args: object) -> None:
        """Close MCAP file."""
        if self.writer:
            self.writer.finish()
        if self.file:
            self.file.close()
