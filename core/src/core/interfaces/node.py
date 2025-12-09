"""Node interface."""

from abc import ABC, abstractmethod
from typing import Any

from core.data.frame_data import FrameData
from core.data.node_io import NodeIO


class Node(ABC):
    """Base class for schedulable nodes."""

    def __init__(self, name: str, rate_hz: float):
        self.name = name
        self.rate_hz = rate_hz
        self.period = 1.0 / rate_hz
        self.next_time = 0.0
        self.next_time = 0.0
        self.frame_data: Any | None = None  # FrameData type is dynamic now

    def get_node_io(self) -> NodeIO:
        """Get node I/O specification."""
        return NodeIO(inputs={}, outputs={})

    def set_frame_data(self, frame_data: FrameData) -> None:
        """Set simulation frame data."""
        self.frame_data = frame_data

    def should_run(self, sim_time: float) -> bool:
        """Check if node should run at current time."""
        return sim_time + 1e-9 >= self.next_time

    @abstractmethod
    def on_run(self, current_time: float) -> bool:
        """Execute node logic.

        Args:
            current_time: Current simulation time

        Returns:
            bool: True if execution was successful
        """
        raise NotImplementedError
