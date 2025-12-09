from core.interfaces.clock import Clock


class SteppedClock(Clock):
    """Clock that advances time by fixed steps.

    Used for deterministic simulation (single process).
    """

    def __init__(self, start_time: float = 0.0, dt: float = 0.01):
        self._current_time = start_time
        self.dt = dt

    @property
    def now(self) -> float:
        return self._current_time

    def tick(self) -> None:
        """Advance time by dt."""
        self._current_time += self.dt
