#!/usr/bin/env python3
"""Run experiment from Hydra configuration."""

from pathlib import Path

import hydra
from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf

from experiment.core.orchestrator import ExperimentOrchestrator


@hydra.main(
    version_base=None,
    config_path=str(Path(__file__).parent.parent.parent / "conf"),
    config_name="config",
)
def main(cfg: DictConfig) -> None:
    """Run experiment with Hydra configuration.

    Args:
        cfg: Hydra configuration object
    """
    load_dotenv()  # Load environment variables from .env file

    # Configure logging level from config
    import logging

    try:
        log_level_str = cfg.execution.get("log_level", "INFO")
        log_level = getattr(logging, log_level_str.upper())
        logging.getLogger().setLevel(log_level)
        # Also set for specific loggers if needed, but root should cover it
        # Hydra's own handlers might need adjustment, but setLevel on root affects propagation
    except Exception as e:
        print(f"Warning: Failed to set log level: {e}")

    # Update outputs/latest symlink
    try:
        from hydra.core.hydra_config import HydraConfig

        hydra_cfg = HydraConfig.get()
        run_dir = Path(hydra_cfg.run.dir).resolve()

        # Assuming run_dir is inside an 'outputs' directory or equivalent root
        # We try to find the 'outputs' directory
        # Standard structure: outputs/YYYY-MM-DD/HH-MM-SS
        output_base = run_dir.parent.parent

        if output_base.exists():
            latest_link = output_base / "latest"
            if latest_link.is_symlink() or latest_link.exists():
                latest_link.unlink()

            # Create relative symlink
            relative_target = run_dir.relative_to(output_base)
            latest_link.symlink_to(relative_target)
            print(f"Updated symlink: {latest_link} -> {relative_target}")
    except Exception as e:
        print(f"Warning: Could not update 'latest' symlink: {e}")

    print("=" * 80)
    print("Running experiment with Hydra configuration")
    print("=" * 80)
    print(OmegaConf.to_yaml(cfg))
    print("=" * 80)

    orchestrator = ExperimentOrchestrator()
    orchestrator.run_from_hydra(cfg)

    print("Experiment completed successfully.")


if __name__ == "__main__":
    main()
