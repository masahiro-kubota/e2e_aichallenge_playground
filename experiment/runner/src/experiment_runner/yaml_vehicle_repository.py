"""YAML-based implementation of VehicleParametersRepository."""

from pathlib import Path

import yaml

from core.data.vehicle import VehicleParameters
from core.interfaces.vehicle import VehicleParametersRepository


class YamlVehicleParametersRepository(VehicleParametersRepository):
    """YAML-based implementation of vehicle parameters repository.

    This implementation loads vehicle parameters from YAML files.
    """

    def load(self, path: Path) -> VehicleParameters:
        """Load vehicle parameters from YAML file.

        Args:
            path: YAML file path

        Returns:
            VehicleParameters object
        """
        with path.open() as f:
            data = yaml.safe_load(f)
        return VehicleParameters(**data)
