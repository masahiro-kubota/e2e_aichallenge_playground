"""MCAP logger for simulation data."""

import json
from pathlib import Path
from typing import Any, TypeVar

from mcap.writer import Writer
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class MCAPLogger:
    """MCAP format logger using ROS 2 standard messages."""

    def __init__(self, output_path: str | Path) -> None:
        """Initialize MCAP logger.

        Args:
            output_path: Output file path (.mcap)
        """
        self.output_path = Path(output_path)
        self.file: Any = None
        self.writer: Writer | None = None
        self.channels: dict[str, int] = {}  # topic -> channel_id

    def __enter__(self) -> "MCAPLogger":
        """Open MCAP file for writing."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(self.output_path, "wb")
        self.writer = Writer(self.file)
        self.writer.start()
        return self

    def register_topic(self, topic: str, model_class: type[BaseModel]) -> None:
        """Register a topic with a Pydantic model (ROS 2 compatible).

        Args:
            topic: Topic name (e.g. /tf, /odom)
            model_class: Pydantic model class representing the message
        """
        if self.writer is None:
            raise RuntimeError("Logger not initialized")

        # Determine schema name based on class docstring or name
        # Convention: docstring starts with "package/Message"
        schema_name = (
            model_class.__doc__.strip().splitlines()[0].rstrip(".")
            if model_class.__doc__
            else model_class.__name__
        )

        schema = model_class.model_json_schema()
        expanded_schema = self._expand_refs(schema)

        schema_id = self.writer.register_schema(
            name=schema_name,
            encoding="jsonschema",
            data=json.dumps(expanded_schema).encode(),
        )

        channel_id = self.writer.register_channel(
            topic=topic,
            message_encoding="json",
            schema_id=schema_id,
        )
        self.channels[topic] = channel_id

    def _expand_refs(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Expand JSON schema references ($ref) recursively to flatten structure.

        Foxglove Studio's MCAP support has limited $ref support in jsonschema.
        This helper inlines definitions.

        Args:
            schema: Original JSON schema with $defs

        Returns:
            Expanded JSON schema without root $defs (or minimized)
        """
        # Copy to avoid mutating original if needed, though we will mutate recursive structure
        import copy

        root = copy.deepcopy(schema)
        defs = root.pop("$defs", {})

        def resolve(node: Any) -> Any:
            if isinstance(node, dict):
                if "$ref" in node:
                    ref = node["$ref"]
                    # Assume local ref "#/$defs/Name"
                    if ref.startswith("#/$defs/"):
                        def_name = ref.split("/")[-1]
                        if def_name in defs:
                            # Recursive resolution of the definition
                            resolved_def = resolve(copy.deepcopy(defs[def_name]))
                            # Merge fields if any (usually $ref replaces everything, but description/title might override)
                            # For simplicity, replace strictly.
                            return resolved_def
                    return (
                        node  # Keep as is if external or not found (shouldn't happen in Pydantic)
                    )

                # Recurse for other keys
                return {k: resolve(v) for k, v in node.items()}
            elif isinstance(node, list):
                return [resolve(x) for x in node]
            else:
                return node

        return resolve(root)

    def log(self, topic: str, message: BaseModel, timestamp: float) -> None:
        """Log a message.

        Args:
            topic: Topic name
            message: Pydantic model instance
            timestamp: Log timestamp in seconds
        """
        if self.writer is None:
            raise RuntimeError("Logger not initialized")

        if topic not in self.channels:
            # Auto-register if not registered (convenience)
            self.register_topic(topic, type(message))

        channel_id = self.channels[topic]

        self.writer.add_message(
            channel_id=channel_id,
            log_time=int(timestamp * 1e9),
            data=message.model_dump_json().encode(),
            publish_time=int(timestamp * 1e9),
        )

    def __exit__(self, *args: object) -> None:
        """Close MCAP file."""
        if self.writer:
            self.writer.finish()
        if self.file:
            self.file.close()
