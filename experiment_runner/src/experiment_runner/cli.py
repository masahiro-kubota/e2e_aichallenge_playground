#!/usr/bin/env python3
"""Run experiment from YAML configuration."""

import argparse
from pathlib import Path

from .config import ExperimentConfig
from .runner import ExperimentRunner


def main() -> None:
    """Run experiment."""
    parser = argparse.ArgumentParser(description="Run experiment from YAML configuration")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/current_experiment.yaml",
        help="Path to experiment configuration YAML file",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        print("\nAvailable templates:")
        templates_dir = Path("configs/experiments")
        if templates_dir.exists():
            for template in templates_dir.glob("*.yaml"):
                print(f"  - {template}")
        print("\nUsage:")
        print(f"  1. Copy a template: cp configs/experiments/pure_pursuit.yaml {args.config}")
        print(f"  2. Edit the config: vim {args.config}")
        print(f"  3. Run: uv run experiment-runner --config {args.config}")
        return

    print(f"Loading configuration from {config_path}...")
    config = ExperimentConfig.from_yaml(config_path)

    print(f"Running experiment: {config.experiment.name}")
    if config.experiment.description:
        print(f"Description: {config.experiment.description}")

    runner = ExperimentRunner(config)
    runner.run()


if __name__ == "__main__":
    main()
