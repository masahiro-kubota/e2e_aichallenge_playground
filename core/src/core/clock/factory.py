from core.clock.stepped import SteppedClock
from core.interfaces import Clock


def create_clock(start_time: float, rate_hz: float, clock_type: str = "stepped") -> Clock:
    """Create a clock instance.

    Args:
        start_time: Simulation start time.
        rate_hz: Simulation rate in Hz.
        clock_type: Type of clock to create ("stepped").

    Returns:
        Clock instance.

    Raises:
        ValueError: If clock_type is not supported.
    """
    if clock_type == "stepped":
        return SteppedClock(start_time=start_time, dt=1.0 / rate_hz)
    else:
        raise ValueError(f"Unsupported clock type: {clock_type}")
