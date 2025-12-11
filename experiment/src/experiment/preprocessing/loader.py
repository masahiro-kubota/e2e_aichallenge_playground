"""Configuration loader for module/system/experiment layers."""

import logging
from pathlib import Path
from typing import Any, TypeVar

from core.data import VehicleParameters, VehicleState
from core.utils import get_project_root
from core.utils.config import load_yaml as core_load_yaml
from core.utils.config import merge_configs
from core.utils.node_factory import create_node
from core.validation.node_graph import validate_node_graph
from experiment.preprocessing.schemas import (
    ExperimentLayerConfig,
    ExperimentMetadata,
    ModuleConfig,
    NodeConfig,
    ResolvedExperimentConfig,
    SystemConfig,
)
from experiment.structures import Experiment
from logger import LoggerNode
from supervisor import SupervisorNode

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _recursive_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge two dictionaries.

    Args:
        base: The base dictionary.
        overrides: The dictionary with overrides.

    Returns:
        Merged dictionary.

    Note:
        This is a wrapper around core.utils.config.merge_configs for backward compatibility.
    """
    return merge_configs(base, overrides)


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
    # Load Experiment Layer
    exp_data = load_yaml(path)
    if "experiment" not in exp_data:
        raise ValueError(f"Missing 'experiment' key in {path}")
    experiment_layer = ExperimentLayerConfig(**exp_data["experiment"])

    # Load System Layer
    system_data = load_yaml(experiment_layer.system)
    if "system" not in system_data:
        raise ValueError(f"Missing 'system' key in {experiment_layer.system}")
    system_layer = SystemConfig(**system_data["system"])

    # Load Module Layer
    module_data = load_yaml(system_layer.module)
    if "module" not in module_data:
        raise ValueError(f"Missing 'module' key in {system_layer.module}")
    module_layer = ModuleConfig(**module_data["module"])

    return experiment_layer, system_layer, module_layer


def _resolve_node_configs(
    module_nodes: list[NodeConfig],
    system_layer: SystemConfig,
) -> list[NodeConfig]:
    """Resolve all node configurations.

    Args:
        module_nodes: Node configurations from module layer.
        system_layer: System configuration for special injections.

    Returns:
        List of resolved node configurations.
    """
    from core.utils.param_loader import load_component_defaults

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

        # 3. Special injections for Simulator
        if node_name == "Simulator":
            if system_layer.map_path:
                params["map_path"] = str(get_project_root() / system_layer.map_path)

            if system_layer.vehicle:
                v_path = get_project_root() / system_layer.vehicle["config_path"]
                params["vehicle_params"] = VehicleParameters(**load_yaml(v_path))

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

    # 2. Resolve all nodes
    resolved_nodes = _resolve_node_configs(
        module_nodes=module_layer.nodes,
        system_layer=system_layer,
    )

    # 3. Build final config
    return ResolvedExperimentConfig(
        experiment=ExperimentMetadata(
            name=experiment_layer.name,
            type=experiment_layer.type,
            description=experiment_layer.description,
        ),
        nodes=resolved_nodes,
        execution=experiment_layer.execution,
        postprocess=experiment_layer.postprocess or {},
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
        config = self.load_config(config_path)

        # 2. Create nodes from resolved config
        nodes = self._create_nodes(config)

        # 3. Create Experiment instance
        experiment_id = str(uuid.uuid4())

        return Experiment(
            id=experiment_id,
            type=config.experiment.type,
            config=config,
            nodes=nodes,
        )

    def load_config(self, config_path: Path) -> ResolvedExperimentConfig:
        """YAML設定を読み込み、階層マージしてスキーマに変換"""
        return load_experiment_config(config_path)

    def _create_nodes(self, config: ResolvedExperimentConfig) -> list[Any]:
        """Create experiment nodes from resolved configuration."""
        from simulator.simulator import Simulator, SimulatorConfig

        nodes = []

        for node_config in config.nodes:
            node_name = node_config.name
            node_type = node_config.type
            rate_hz = node_config.rate_hz
            params = node_config.params.copy()

            # Create node based on type
            if node_name == "Simulator":
                # Special handling for Simulator
                initial_state = VehicleState(x=0.0, y=0.0, yaw=0.0, velocity=0.0, timestamp=0.0)
                if "initial_state" in params:
                    initial_state_dict = params.pop("initial_state")
                    if isinstance(initial_state_dict, dict):
                        initial_state = VehicleState(**initial_state_dict, timestamp=0.0)

                # vehicle_params is already a VehicleParameters object from resolution
                vehicle_params = params.get("vehicle_params")
                if vehicle_params is None:
                    raise ValueError("Simulator requires vehicle_params to be configured")

                simulator_config_dict = {
                    "vehicle_params": vehicle_params,
                    "initial_state": initial_state,
                }

                if "map_path" in params:
                    simulator_config_dict["map_path"] = params["map_path"]

                if "obstacles" in params:
                    simulator_config_dict["obstacles"] = params["obstacles"]

                simulator_config_model = SimulatorConfig(**simulator_config_dict)
                node = Simulator(config=simulator_config_model, rate_hz=rate_hz)

            elif node_name == "Supervisor":
                # Special handling for Supervisor
                from supervisor import SupervisorConfig

                supervisor_config_model = SupervisorConfig(**params)
                node = SupervisorNode(config=supervisor_config_model, rate_hz=rate_hz)

            elif node_name == "Logger":
                # Special handling for Logger
                node = LoggerNode(rate_hz=rate_hz)

            else:
                # Generic AD component node
                # Get vehicle params from Simulator node if available
                vehicle_params = None
                for n in config.nodes:
                    if n.name == "Simulator" and "vehicle_params" in n.params:
                        vehicle_params = n.params["vehicle_params"]
                        break

                node = create_node(
                    node_type=node_type,
                    rate_hz=rate_hz,
                    params=params,
                    vehicle_params=vehicle_params,
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
