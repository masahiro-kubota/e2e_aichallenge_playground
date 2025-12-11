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
        return True

    def __exit__(self, *args: object) -> None:
        """Close MCAP file."""
        if self.writer:
            self.writer.finish()
        if self.file:
            self.file.close()
