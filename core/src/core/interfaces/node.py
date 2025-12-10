"""Node interface."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict

from core.data.frame_data import FrameData
from core.data.node_io import NodeIO


class NodeExecutionResult(Enum):
    """Result of node execution."""

    SUCCESS = "success"  # 正常実行完了
    SKIPPED = "skipped"  # 入力データ不足等でスキップ
    FAILED = "failed"  # エラー発生


class FrameDataProtocol(Protocol):
    """Protocol for dynamic FrameData types."""

    pass


class NodeConfig(BaseModel):
    """Base configuration for nodes with strict validation."""

    model_config = ConfigDict(extra="forbid")


T = TypeVar("T", bound=NodeConfig)


class Node(ABC, Generic[T]):
    """Base class for schedulable nodes."""

    def __init__(
        self,
        name: str,
        rate_hz: float,
        config: dict[str, Any],
        config_model: type[T],
    ):
        """Initialize node.

        Args:
            name: Node name
            rate_hz: Execution frequency in Hz
            config: Configuration dictionary
            config_model: Pydantic model class for configuration validation
        """
        self.name = name
        self.rate_hz = rate_hz
        self.period = 1.0 / rate_hz
        self.next_time = 0.0
        self.frame_data: FrameDataProtocol | None = None
        self.config: T = config_model(**config)

    @abstractmethod
    def get_node_io(self) -> NodeIO:
        """Get node I/O specification.

        Returns:
            NodeIO specification defining inputs and outputs
        """
        raise NotImplementedError

    def set_frame_data(self, frame_data: FrameData) -> None:
        """Set simulation frame data.

        Args:
            frame_data: Frame data to set
        """
        self.frame_data = frame_data

    def should_run(self, sim_time: float) -> bool:
        """Check if node should run at current time.

        Args:
            sim_time: Current simulation time

        Returns:
            True if node should run
        """
        return sim_time + 1e-9 >= self.next_time

    def update_next_time(self, current_time: float) -> None:
        """Update next execution time.

        Args:
            current_time: Current simulation time
        """
        self.next_time = current_time + self.period

    def on_init(self) -> None:
        """Initialize node resources.

        Called once before the first execution.
        Override to perform initialization tasks.
        """
        pass

    def on_shutdown(self) -> None:
        """Clean up node resources.

        Called once after the last execution.
        Override to perform cleanup tasks.
        """
        pass

    @abstractmethod
    def on_run(self, current_time: float) -> NodeExecutionResult:
        """Execute node logic.

        Args:
            current_time: Current simulation time

        Returns:
            NodeExecutionResult indicating execution status
        """
        raise NotImplementedError
