"""Dashboard generation interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from core.data import SimulationLog


class DashboardGenerator(ABC):
    """Dashboard generation interface.

    This abstract base class defines the interface for generating interactive dashboards
    from simulation logs. Implementations should generate HTML dashboards that
    can be viewed in a web browser.
    """

    @abstractmethod
    def generate(
        self,
        log: SimulationLog,
        output_path: Path,
        osm_path: Path | None = None,
    ) -> None:
        """Generate interactive dashboard from simulation log.

        Args:
            log: Simulation log containing trajectory and metadata
            output_path: Path where the generated HTML dashboard will be saved
            osm_path: Optional path to OSM map file for map visualization

        Raises:
            FileNotFoundError: If template or required files are not found
            ValueError: If log data is invalid or incomplete
        """
