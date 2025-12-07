"""Parameter loading utilities."""

import importlib.resources
from typing import Any

import yaml


def load_component_defaults(package_name: str) -> dict[str, Any]:
    """Load default parameters from a package's default.param.yaml.

    Args:
        package_name: The name of the package containing the resource.

    Returns:
        A dictionary of default parameters, or an empty dict if the file is not found.
    """
    try:
        # Check if the resource exists using files() traversal which is the modern API
        resource_path = importlib.resources.files(package_name).joinpath("default.param.yaml")
        if resource_path.is_file():
            content = resource_path.read_text(encoding="utf-8")
            return yaml.safe_load(content) or {}
    except (ImportError, TypeError, OSError):
        # Package might not exist or file system error
        pass

    return {}
