#!/usr/bin/env python3
import argparse
import datetime
import logging
import shlex
import subprocess
import sys
from pathlib import Path

"""
MLOps Pipeline Automation Script for Volume 2 (No Obstacle)

This script automates:
1. Data Collection (Random Start, No Obstacle)
2. Aggregation (Collection Summary)
3. Combined Feature Extraction (MCAP -> NumPy)
4. Training (TinyLidarNet)
5. Evaluation (Standard)

Usage:
    uv run python experiment/scripts/run_mlops_pipeline_v2.py \
        --version v2_no_obs \
        --rs-train 500 --rs-val 100 \
        --epochs 10

"""

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mlops_pipeline_v2")


class MLOpsPipeline:
    def __init__(self, args):
        self.args = args
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.project_root = Path.cwd()

        self.dataset_version = args.version

        # Base directory for this entire run
        if args.run_dir:
            self.run_base_dir = Path(args.run_dir).resolve()
        else:
            self.run_base_dir = (
                self.project_root / "outputs" / "mlops" / f"{self.dataset_version}_{self.timestamp}"
            )
        self.collection_base_dir = self.run_base_dir / "collection"

        # Processed data directories (Final destination for training)
        self.processed_data_root = self.project_root / "data" / "processed"
        self.train_data_dir = self.processed_data_root / f"train_{self.dataset_version}"
        self.val_data_dir = self.processed_data_root / f"val_{self.dataset_version}"

        # State tracking
        self.collection_dirs: dict[str, dict[str, Path]] = {"train": {}, "val": {}}
        self.model_path: Path | None = None
        self.pipeline_steps: list[dict] = []

    def run_command(
        self, command: str, description: str = "", capture_output: bool = False
    ) -> str | None:
        """Run a shell command."""
        logger.info(f"Running [{description}]: {command}")

        step_record = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": description,
            "command": command,
            "status": "pending",
        }

        if self.args.dry_run:
            step_record["status"] = "dry_run"
            self.pipeline_steps.append(step_record)
            return None

        try:
            cmd_args = shlex.split(command)
            if capture_output:
                result = subprocess.run(cmd_args, check=True, text=True, capture_output=True)
                step_record["status"] = "success"
                self.pipeline_steps.append(step_record)
                return result.stdout.strip()
            else:
                subprocess.run(cmd_args, check=True)
                step_record["status"] = "success"
                self.pipeline_steps.append(step_record)
                return None
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed with exit code {e.returncode}")
            step_record["status"] = "failed"
            step_record["exit_code"] = e.returncode
            self.pipeline_steps.append(step_record)
            if not self.args.continue_on_error:
                sys.exit(1)
            return None

    def run_collection(self):
        """Step 1: Data Collection (Random Start only for Vol 2)."""
        logger.info("=== Step 1: Data Collection ===")

        # For Vol 2, we mainly use Random Start in No Obstacle environment
        jobs = [
            ("random_start", "train", self.args.rs_train, 0),
            ("random_start", "val", self.args.rs_val, 100000),
        ]

        for exp_type, split, count, base_seed in jobs:
            if count <= 0:
                continue

            logger.info(f"--- Collecting {exp_type} {split} (N={count}) ---")
            job_dir = (self.collection_base_dir / split / exp_type).resolve()

            # Note: Using env=no_obstacle
            cmd = (
                f"uv run experiment-runner -m "
                f"experiment=data_collection_{exp_type} "
                f"execution.total_episodes={count} "
                f"execution.base_seed={base_seed} "
                f"experiment.name=col_{exp_type}_{split}_{self.dataset_version} "
                f"env=no_obstacle "  # Explicitly set no obstacle
                f"hydra.sweep.dir={job_dir}"
            )

            self.run_command(cmd, description=f"Collection {exp_type} {split}")

            if not self.args.dry_run:
                self.collection_dirs[split][exp_type] = job_dir

    def run_aggregation(self):
        """Step 2: Aggregation."""
        logger.info("=== Step 2: Aggregation ===")
        for split in ["train", "val"]:
            for exp_type, path in self.collection_dirs[split].items():
                if path.exists():
                    cmd = f"uv run python experiment/scripts/aggregate_multirun.py {path}"
                    self.run_command(cmd, description=f"Aggregation {exp_type} {split}")

    def run_extraction(self):
        """Step 3: Feature Extraction."""
        logger.info("=== Step 3: Feature Extraction (Combined) ===")
        exclude_reasons = "'[off_track,collision,unknown]'"

        for split in ["train", "val"]:
            output_dir = self.train_data_dir if split == "train" else self.val_data_dir
            input_dir = (self.collection_base_dir / split).resolve()

            if self.args.dry_run:
                input_dir = f"outputs/mlops_v2/collection/{split}"

            cmd = (
                f"uv run experiment-runner "
                f"experiment=extraction "
                f"input_dir={input_dir} "
                f"output_dir={output_dir} "
                f"exclude_failure_reasons={exclude_reasons}"
            )
            self.run_command(cmd, description=f"Combined Extraction {split}")

    def run_training(self):
        """Step 4: Training."""
        logger.info("=== Step 4: Training ===")
        safe_timestamp = self.timestamp.replace("_", "")
        training_out = self.run_base_dir / "training"

        cmd = (
            f"uv run experiment-runner -m "
            f"experiment=training "
            f"train_data={self.train_data_dir} "
            f"val_data={self.val_data_dir} "
            f"experiment.name=train_{self.dataset_version}_{safe_timestamp} "
            f"hydra.sweep.dir={training_out}"
        )

        if self.args.epochs:
            cmd += f" training.num_epochs={self.args.epochs}"

        self.run_command(cmd, description="Model Training")

        if not self.args.dry_run:
            try:
                checkpoints_dirs = list(training_out.glob("**/checkpoints"))
                if checkpoints_dirs:
                    latest_cp_dir = sorted(checkpoints_dirs, key=lambda x: x.stat().st_mtime)[-1]
                    npy_files = list(latest_cp_dir.glob("**/best_model.npy"))
                    if npy_files:
                        self.model_path = npy_files[-1].resolve()
                        logger.info(f"Detected Model: {self.model_path}")
            except Exception as e:
                logger.warning(f"Could not automatically locate model: {e}")

    def run_evaluation(self):
        """Step 5: Evaluation."""
        logger.info("=== Step 5: Evaluation ===")
        model_path = self.args.model_path or self.model_path
        if not model_path:
            logger.error("No model path found for evaluation!")
            return

        eval_out = self.run_base_dir / "evaluation"

        # Standard Evaluation (No Obstacle)
        cmd = (
            f"uv run experiment-runner experiment=evaluation "
            f"ad_components=tiny_lidar_debug "
            f"ad_components.model_path={model_path} "
            f"env=no_obstacle "
            f"execution.num_episodes=5 "  # 5 laps
            f"experiment.name=eval_v2_{self.dataset_version} "
            f"hydra.run.dir={eval_out}"
        )
        self.run_command(cmd, description="Evaluation (No Obstacle)")

        # Aggregate metrics
        if not self.args.dry_run and eval_out.exists():
            cmd = f"uv run python experiment/scripts/aggregate_evaluation.py {eval_out}"
            self.run_command(cmd, description="Aggregate Evaluation")

    def run(self):
        if not self.args.skip_collection:
            self.run_collection()
            self.run_aggregation()

        if not self.args.skip_extraction:
            self.run_extraction()

        if not self.args.skip_training:
            self.run_training()
        elif self.args.model_path:
            self.model_path = Path(self.args.model_path)

        if not self.args.skip_evaluation:
            self.run_evaluation()


def main():
    parser = argparse.ArgumentParser(description="Vol 2 MLOps Pipeline")
    parser.add_argument("--version", type=str, required=True, help="Dataset version")
    parser.add_argument("--rs-train", type=int, default=100, help="Random Start Train episodes")
    parser.add_argument("--rs-val", type=int, default=20, help="Random Start Val episodes")
    parser.add_argument("--epochs", type=int, default=5)

    parser.add_argument("--skip-collection", action="store_true")
    parser.add_argument("--skip-extraction", action="store_true")
    parser.add_argument("--skip-training", action="store_true")
    parser.add_argument("--skip-evaluation", action="store_true")
    parser.add_argument("--model-path", type=str)
    parser.add_argument("--run-dir", type=str)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")

    args = parser.parse_args()
    MLOpsPipeline(args).run()


if __name__ == "__main__":
    main()
