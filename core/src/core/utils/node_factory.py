import importlib
import inspect
from typing import Any

from core.data import VehicleParameters
from core.interfaces.node import Node
from core.utils.paths import get_project_root


def create_node(
    node_type: str,
    rate_hz: float,
    params: dict[str, Any],
    vehicle_params: VehicleParameters | None = None,
) -> Node:
    """Create a Node instance dynamically.

    Args:
        node_type: Class path (e.g., "package.module.ClassName") or short name alias
        rate_hz: Execution frequency in Hz
        params: Node configuration parameters
        vehicle_params: Vehicle parameters to inject if required by Node

    Returns:
        Instantiated Node
    """
    # Map short names to full module paths
    node_type_aliases = {
        "KinematicSimulator": "simulator.simulator.Simulator",
        "SupervisorNode": "supervisor.supervisor_node.SupervisorNode",
        "LoggerNode": "logger.logger_node.LoggerNode",
    }

    # Resolve alias if present
    resolved_type = node_type_aliases.get(node_type, node_type)

    # Resolve path parameters
    path_keys = {"track_path", "model_path", "scaler_path"}
    workspace_root = get_project_root()

    # Copy params to avoid mutation
    node_params = params.copy()

    for key, value in node_params.items():
        if key in path_keys and isinstance(value, str):
            # Resolve relative paths against workspace root
            node_params[key] = str(workspace_root / value)

    # Import class
    try:
        module_name, class_name = resolved_type.rsplit(".", 1)
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
    except (ValueError, ImportError, AttributeError) as e:
        raise ValueError(
            f"Invalid node type: {node_type} (resolved to: {resolved_type}). "
            f"Must be in 'module.ClassName' format and importable. Error: {e}"
        ) from e

    if not issubclass(cls, Node):
        raise TypeError(f"Class {cls} is not a subclass of Node")

    # Get the config model from the class
    # The Node class is Generic[T], we need to extract T
    # We can look at __orig_bases__ to find the config type
    config_class = None
    if hasattr(cls, "__orig_bases__"):
        for base in cls.__orig_bases__:
            if (
                hasattr(base, "__origin__")
                and base.__origin__ is Node
                and hasattr(base, "__args__")
                and base.__args__
            ):
                config_class = base.__args__[0]
                break

    if config_class is None:
        raise ValueError(f"Could not determine config class for {cls}")

    # Check if the class accepts vehicle_params
    sig = inspect.signature(cls.__init__)
    kwargs = {}

    if "vehicle_params" in sig.parameters and vehicle_params is not None:
        kwargs["vehicle_params"] = vehicle_params

    # Use from_dict to create the node
    return cls.from_dict(
        rate_hz=rate_hz,
        config_class=config_class,
        config_dict=node_params,
        **kwargs,
    )
