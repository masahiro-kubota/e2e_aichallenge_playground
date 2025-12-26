from abc import ABC, abstractmethod


class Clock(ABC):
    """Abstract interface for time management."""

    @property
    @abstractmethod
    def now(self) -> float:
        """Get current simulation time.

        Returns:
            float: Current time in seconds.
        """

    @abstractmethod
    def tick(self) -> None:
        """Advance time by one step (if applicable)."""
