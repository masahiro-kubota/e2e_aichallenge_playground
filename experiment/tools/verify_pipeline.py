import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout


def main():
    # 0. Set PYTHONPATH (Ensure project root and experiment/src are included)
    os.environ["PYTHONPATH"] = f".:experiment/src:{os.environ.get('PYTHONPATH', '')}"

    # 1. Collection
    print("--- Phase 1: Collection ---")
    run_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "experiment.cli",
            "experiment=data_collection",
            "execution.num_episodes=1",
            "execution.duration_sec=5.0",
        ]
    )

    # 2. Get latest output dir (specifically YYYY-MM-DD/HH-MM-SS)
    all_runs = sorted(
        [
            d
            for d in Path("outputs").glob(
                "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/[0-9][0-9]-[0-9][0-9]-[0-9][0-9]"
            )
            if d.is_dir()
        ]
    )
    if not all_runs:
        print("Error: No runs found in outputs/")
        sys.exit(1)

    latest_run = all_runs[-1]
    # CollectorEngine outputs to <run_dir>/train/raw_data by default
    raw_data_dir = latest_run / "train" / "raw_data"
    processed_data_dir = latest_run / "train" / "processed_data"

    print(f"Detected latest run: {latest_run}")

    # 2. Extraction
    print(f"--- Phase 2: Extraction (using {raw_data_dir}) ---")
    run_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "experiment.cli",
            "experiment=extraction",
            f"input_dir={raw_data_dir}",
        ]
    )

    # 3. Training
    print(f"--- Phase 3: Training (using {processed_data_dir}) ---")
    run_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "experiment.cli",
            "experiment=training",
            "training.num_epochs=1",
            f"train_data={processed_data_dir}",
            f"val_data={processed_data_dir}",
        ]
    )

    # 4. Evaluation
    print("--- Phase 4: Evaluation ---")
    run_command(
        [
            "uv",
            "run",
            "python",
            "-m",
            "experiment.cli",
            "experiment=evaluation",
            "execution.duration_sec=5.0",
        ]
    )

    print("--- All Phases Completed Successfully! ---")


if __name__ == "__main__":
    main()
