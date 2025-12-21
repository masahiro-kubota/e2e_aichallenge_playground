#!/usr/bin/env python3
"""Data collection script using Hydra."""

import logging
import random
import uuid
from pathlib import Path

import hydra
import numpy as np
from omegaconf import DictConfig, OmegaConf

from core.data.experiment.config import (
    ExecutionConfig,
    ExperimentMetadata,
    NodeConfig,
    ResolvedExperimentConfig,
)
from core.interfaces.node import Node
from core.utils.node_factory import NodeFactory
from experiment.interfaces import Experiment
from experiment.runner.evaluation_runner import EvaluationRunner
from experiment.structures import Experiment as ExperimentStructure

logger = logging.getLogger(__name__)


def create_experiment_instance(cfg: DictConfig, output_dir: Path, episode_idx: int) -> Experiment:
    """Create an experiment instance from Hydra config."""

    # 1. Convert Hydra config to Pydantic models (ResolvedExperimentConfig)
    # Convert to container to avoid OmegaConf types
    cfg_dict = OmegaConf.to_container(cfg, resolve=True)

    experiment_data = cfg_dict["experiment"]
    execution_data = cfg_dict["execution"]
    postprocess_data = cfg_dict["postprocess"]
    system_data = cfg_dict["system"]

    # Update MCAP output directory for this episode
    # Use a subdirectory per episode to avoid filename collisions if Logger uses fixed names
    # Or rely on LoggerNode params update.
    # The LoggerNode in collect_data.yaml has params: output_mcap_path: ...
    # But wait, in the yaml strings reference ${hydra:runtime.output_dir}.
    # We want to change the output path per episode.

    episode_dir = output_dir / f"episode_{episode_idx:04d}"
    episode_dir.mkdir(parents=True, exist_ok=True)

    # Update Logger params in nodes list
    nodes_data = system_data["nodes"]

    # Merge agent nodes into nodes_data
    # Agent config usually sits under 'agent' key due to Hydra structure,
    # unless flattened with @package _global_.
    # We check both locations.
    agent_nodes_data = []
    if "agent" in cfg_dict and "nodes" in cfg_dict["agent"]:
        agent_nodes_data = cfg_dict["agent"]["nodes"]
    elif "nodes" in cfg_dict:
        agent_nodes_data = cfg_dict["nodes"]

    if agent_nodes_data:
        insert_idx = len(nodes_data)  # Default at end
        for i, node in enumerate(nodes_data):
            if node["name"] == "Supervisor":
                insert_idx = i
                break

        # Insert
        for node in reversed(agent_nodes_data):
            nodes_data.insert(insert_idx, node)

    for node in nodes_data:
        if node["name"] == "Logger":
            # LoggerNode uses 'output_mcap_path' from config
            node["params"]["output_mcap_path"] = str(episode_dir)

    # Create NodeConfig objects
    resolved_nodes = [NodeConfig(**node) for node in nodes_data]

    # Create ResolvedExperimentConfig
    resolved_config = ResolvedExperimentConfig(
        experiment=ExperimentMetadata(**experiment_data),
        nodes=resolved_nodes,
        execution=ExecutionConfig(**execution_data),
        postprocess=postprocess_data,  # Validated by Pydantic
    )

    # 2. Instantiate Nodes
    factory = NodeFactory()
    nodes: list[Node] = []

    for node_config in resolved_nodes:
        node = factory.create(
            node_type=node_config.type,
            rate_hz=node_config.rate_hz,
            params=node_config.params,
        )
        nodes.append(node)

    # 3. Create Experiment Structure
    experiment_id = str(uuid.uuid4())

    return ExperimentStructure(
        id=experiment_id,
        type=resolved_config.experiment.type,
        config=resolved_config,
        nodes=nodes,
    )


def randomize_simulation_config(cfg: DictConfig, rng: np.random.Generator) -> None:
    """Randomize the simulation configuration (vehicle pose, obstacles)."""
    # Find Simulator node
    nodes = cfg.system.nodes
    sim_node = None
    for node in nodes:
        if node.name == "Simulator":
            sim_node = node
            break

    if not sim_node:
        logger.warning("Simulator node not found, skipping randomization.")
        return

    # Randomize Initial State
    # Example: x in [89620, 89640], y in [43120, 43140], yaw in [0, 2pi]
    # Adjust range as appropriate for the map
    initial_state = sim_node.params.initial_state

    # Simple jitter around the default
    initial_state.x += rng.uniform(-2.0, 2.0)
    initial_state.y += rng.uniform(-2.0, 2.0)
    initial_state.yaw += rng.uniform(-0.5, 0.5)

    # Randomize Obstacles
    obstacles = sim_node.params.obstacles
    for obs in obstacles:
        # Jitter position
        obs["position"]["x"] += rng.uniform(-1.0, 1.0)
        obs["position"]["y"] += rng.uniform(-1.0, 1.0)
        # Randomize yaw
        obs["position"]["yaw"] = rng.uniform(0, 6.28)


@hydra.main(version_base=None, config_path="../experiment/conf", config_name="collect_data")
def main(cfg: DictConfig) -> None:
    """Main execution entry point."""
    # print(OmegaConf.to_yaml(cfg))

    # Get runtime arguments
    # Hydra allows adding arbitrary args via +arg=value
    # We expect: +split=train/val +seed=123

    seed = cfg.get("seed", 42)
    num_episodes = cfg.execution.num_episodes
    split = cfg.get("split", "train")

    output_dir = Path(hydra.core.hydra_config.HydraConfig.get().run.dir) / split / "raw_data"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting data collection: {num_episodes} episodes, seed={seed}, split={split}")

    for i in range(num_episodes):
        episode_seed = seed + i
        logger.info(f"--- Episode {i+1}/{num_episodes} (Seed: {episode_seed}) ---")

        # Seed everything
        random.seed(episode_seed)
        np.random.seed(episode_seed)
        rng = np.random.default_rng(episode_seed)

        # Copy config to modify it
        episode_cfg = cfg.copy()

        # Randomize
        randomize_simulation_config(episode_cfg, rng)

        # Create Experiment
        experiment = create_experiment_instance(episode_cfg, output_dir, i)

        # Run
        runner = EvaluationRunner()
        result = runner.run(experiment)

        if result.success:
            logger.info("Episode successful.")
        else:
            logger.warning(f"Episode failed: {result.reason}")

    logger.info(f"Data collection completed. Output: {output_dir}")


if __name__ == "__main__":
    main()
