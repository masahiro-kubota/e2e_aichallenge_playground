"""Log repository interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from core.data import SimulationLog


class SimulationLogRepository(ABC):
    """Interface for simulation log persistence.

    This interface abstracts the storage and retrieval of simulation logs,
    allowing different implementations (JSON, MCAP, database, etc.) without
    affecting the code that uses simulation logs.
    """

    @abstractmethod
    def save(self, log: SimulationLog, file_path: Path) -> Path:
        """Save simulation log to file.

        Args:
            log: Simulation log to save
            file_path: Output file path

        Returns:
            Path to the saved log file
        """

    @abstractmethod
    def load(self, file_path: Path) -> SimulationLog:
        """Load simulation log from file.

        Args:
            file_path: Input file path

        Returns:
            SimulationLog object
        """
