"""Configuration loader for module/system/experiment layers."""

import logging
from pathlib import Path
from typing import Any, TypeVar

from core.data import VehicleParameters
from core.data.experiment.config import (
    ExperimentFile,
    ExperimentLayerConfig,
    ExperimentMetadata,
    ModuleConfig,
    ModuleFile,
    NodeConfig,
    ResolvedExperimentConfig,
    SystemConfig,
    SystemFile,
)
from core.interfaces.node import Node
from core.utils import get_project_root
from core.utils.config import load_yaml as core_load_yaml
from core.utils.node_factory import NodeFactory
from core.validation.node_graph import validate_node_graph
from experiment.structures import Experiment

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _resolve_defaults(
    user_params: dict[str, Any], default_params: dict[str, Any]
) -> dict[str, Any]:
    """Resolve 'default' values in user parameters using default parameters.

    Args:
        user_params: User-provided parameters.
        default_params: Default parameters.

    Returns:
        Resolved parameters.
    """
    resolved = user_params.copy()
    for key, value in resolved.items():
        if (
            isinstance(value, dict)
            and key in default_params
            and isinstance(default_params[key], dict)
        ):
            resolved[key] = _resolve_defaults(value, default_params[key])
        elif value == "default":
            if key in default_params:
                resolved[key] = default_params[key]
            else:
                raise ValueError(f"Parameter '{key}' set to 'default' but no default value found.")
    return resolved


def _resolve_nested_reference(ref_path: str, context: dict[str, Any]) -> Any:
    """Resolve nested reference path (e.g., 'vehicle.config_path').

    Args:
        ref_path: Dot-separated reference path.
        context: Context dictionary to resolve from.

    Returns:
        Resolved value.

    Raises:
        ValueError: If reference path is not found.
    """
    keys = ref_path.split(".")
    value = context

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            available_keys = list(context.keys()) if isinstance(context, dict) else []
            raise ValueError(
                f"System reference '${{system.{ref_path}}}' not found. "
                f"Available top-level keys: {available_keys}"
            )

    return value


def _resolve_system_references(
    params: dict[str, Any],
    system_context: dict[str, Any],
) -> dict[str, Any]:
    """Resolve ${system.*} references in parameters.

    Args:
        params: Parameters that may contain ${system.*} references.
        system_context: System context dictionary.

    Returns:
        Parameters with resolved references.

    Examples:
        >>> context = {"map_path": "/path/to/map.osm", "vehicle": {"config_path": "/path/to/vehicle.yaml"}}
        >>> params = {"map_path": "${system.map_path}", "vehicle_config": "${system.vehicle.config_path}"}
        >>> _resolve_system_references(params, context)
        {"map_path": "/path/to/map.osm", "vehicle_config": "/path/to/vehicle.yaml"}
    """
    resolved = {}

    for key, value in params.items():
        if isinstance(value, str) and value.startswith("${system."):
            # Extract reference path: ${system.map_path} -> "map_path"
            ref_path = value.replace("${system.", "").rstrip("}")
            resolved[key] = _resolve_nested_reference(ref_path, system_context)
        elif isinstance(value, dict):
            # Recursively resolve nested dictionaries
            resolved[key] = _resolve_system_references(value, system_context)
        elif isinstance(value, list):
            # Resolve references in list items
            resolved[key] = [
                _resolve_system_references(item, system_context) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            resolved[key] = value

    return resolved


def _build_system_context(system_layer: SystemConfig) -> dict[str, Any]:
    """Build system context dictionary from SystemConfig.

    Args:
        system_layer: System configuration.

    Returns:
        Context dictionary with resolved system-level settings.

    Note:
        This function resolves:
        - map_path: Converted to absolute path string
        - vehicle_params: Loaded as VehicleParameters object
        - vehicle: Dictionary with config_path and params for nested references
    """
    context = {}

    # Resolve map_path to absolute path
    context["map_path"] = str(get_project_root() / system_layer.map_path)

    # Resolve vehicle configuration
    if system_layer.vehicle:
        v_path = get_project_root() / system_layer.vehicle["config_path"]
        vehicle_params = VehicleParameters(**load_yaml(v_path))

        # Store both the resolved object and the nested structure
        context["vehicle_params"] = vehicle_params
        context["vehicle"] = {
            "config_path": str(v_path),
            "params": vehicle_params,
        }

    return context


def load_yaml(path: Path | str) -> dict[str, Any]:
    """Load YAML file relative to project root.

    Args:
        path: Path to YAML file (relative to project root).

    Returns:
        Loaded dictionary.

    Note:
        This is a convenience wrapper that automatically prepends the project root path.
    """
    full_path = get_project_root() / path
    return core_load_yaml(full_path)


def _load_layer_configs(
    path: Path | str,
) -> tuple[ExperimentLayerConfig, SystemConfig, ModuleConfig]:
    """Load and validate all 3 configuration layers.

    Args:
        path: Path to the experiment layer configuration file.

    Returns:
        Tuple of (experiment_layer, system_layer, module_layer).
    """
    # Load Experiment Layer with Pydantic validation
    exp_data = load_yaml(path)
    exp_file = ExperimentFile(**exp_data)
    experiment_layer = exp_file.experiment

    # Load System Layer with Pydantic validation
    system_data = load_yaml(experiment_layer.system)
    system_file = SystemFile(**system_data)
    system_layer = system_file.system

    # Load Module Layer with Pydantic validation
    module_data = load_yaml(system_layer.module)
    module_file = ModuleFile(**module_data)
    module_layer = module_file.module

    return experiment_layer, system_layer, module_layer


def _resolve_node_configs(
    module_nodes: list[NodeConfig],
    system_layer: SystemConfig,
) -> list[NodeConfig]:
    """Resolve all node configurations.

    Args:
        module_nodes: Node configurations from module layer.
        system_layer: System configuration.

    Returns:
        List of resolved node configurations.
    """
    from core.utils.param_loader import load_component_defaults

    # Build system context once for all nodes
    system_context = _build_system_context(system_layer)

    resolved_nodes = []

    for node_config in module_nodes:
        node_name = node_config.name
        node_type = node_config.type

        # 1. Load defaults for this node type
        try:
            defaults = load_component_defaults(node_type)
        except Exception:
            defaults = {}

        # 2. Resolve defaults in module params
        params = _resolve_defaults(node_config.params, defaults)

        # 3. Resolve system references (${system.*})
        params = _resolve_system_references(params, system_context)

        resolved_nodes.append(
            NodeConfig(
                name=node_name,
                type=node_type,
                rate_hz=node_config.rate_hz,
                params=params,
            )
        )

    return resolved_nodes


def load_experiment_config(path: Path | str) -> ResolvedExperimentConfig:
    """Load and merge experiment configuration layers.

    Args:
        path: Path to the experiment layer content file (ExperimentLayerConfig).

    Returns:
        Resolved experiment configuration (ResolvedExperimentConfig).
    """
    # 1. Load all layers
    experiment_layer, system_layer, module_layer = _load_layer_configs(path)

    # 2. Build system context for reference resolution
    system_context = _build_system_context(system_layer)

    # 3. Resolve all nodes
    resolved_nodes = _resolve_node_configs(
        module_nodes=module_layer.nodes,
        system_layer=system_layer,
    )

    # 4. Resolve postprocess configuration references
    postprocess_dict = experiment_layer.postprocess.model_dump()
    resolved_postprocess_dict = _resolve_system_references(postprocess_dict, system_context)

    # 5. Inject MCAP path into Logger node
    # Note: We pass the directory path, and LoggerNode will generate timestamped filename
    if resolved_postprocess_dict["mcap"]["enabled"]:
        output_dir = resolved_postprocess_dict["mcap"]["output_dir"]
        logger_mcap_path = output_dir  # Pass directory, not full path

        for node in resolved_nodes:
            if node.name == "Logger":
                node.params["output_mcap_path"] = logger_mcap_path
                break

    # 5. Build final config
    return ResolvedExperimentConfig(
        experiment=ExperimentMetadata(
            name=experiment_layer.name,
            type=experiment_layer.type,
            description=experiment_layer.description,
        ),
        nodes=resolved_nodes,
        execution=experiment_layer.execution,
        postprocess=resolved_postprocess_dict,
    )


class DefaultPreprocessor:
    """前処理の具体的な実装

    インターフェースではなく、具体的なクラスとして実装。
    全実験タイプで共通の処理を行う。
    """

    def __init__(self) -> None:
        from experiment.preprocessing.factory import ComponentFactory

        self.component_factory = ComponentFactory()

    def create_experiment(self, config_path: Path) -> Experiment:
        """Create experiment instance from configuration file.

        Args:
            config_path: Path to the experiment configuration file.

        Returns:
            Executable Experiment instance.
        """
        import uuid

        # 1. Load configuration
        config = load_experiment_config(config_path)

        # 2. Create nodes from resolved config
        nodes = self.build_experiment_nodes(config)

        # 3. Create Experiment instance
        experiment_id = str(uuid.uuid4())

        return Experiment(
            id=experiment_id,
            type=config.experiment.type,
            config=config,
            nodes=nodes,
        )

    def build_experiment_nodes(self, config: ResolvedExperimentConfig) -> list[Node]:
        """Create experiment nodes from resolved configuration."""
        nodes: list[Node] = []
        factory = NodeFactory()

        # Create all nodes using unified approach
        for node_config in config.nodes:
            node = factory.create(
                node_type=node_config.type,
                rate_hz=node_config.rate_hz,
                params=node_config.params,
            )
            nodes.append(node)

        # Validate AD nodes (exclude Simulator, Supervisor, Logger)
        ad_nodes = [
            n
            for n, cfg in zip(nodes, config.nodes)
            if cfg.name not in ["Simulator", "Supervisor", "Logger"]
        ]
        if ad_nodes:
            validate_node_graph(ad_nodes)

        return nodes
