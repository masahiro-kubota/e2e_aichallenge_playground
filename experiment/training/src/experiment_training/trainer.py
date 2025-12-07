"""Trainer implementation."""

from pathlib import Path
from typing import Any

from core.data import Trajectory


class Trainer:
    """Trainer for Neural Controller (Disabled)."""

    def __init__(
        self,
        config: dict[str, Any],
        reference_trajectory: Trajectory,
        workspace_root: Path,
    ) -> None:
        """Initialize trainer.

        Args:
            config: Training configuration
            reference_trajectory: Reference trajectory for feature calculation
            workspace_root: Root directory of the workspace
        """
        raise NotImplementedError("NeuralController has been removed. Training is disabled.")

    def train(self, data_paths: list[str | Path]) -> None:
        """Execute training loop."""
        pass
