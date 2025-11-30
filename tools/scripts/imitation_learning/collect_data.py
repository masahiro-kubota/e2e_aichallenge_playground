"""Data collection script for imitation learning."""

from pathlib import Path

from experiment_runner.config import ExperimentConfig
from experiment_runner.runner import ExperimentRunner


def main() -> None:
    """Collect data using Pure Pursuit."""
    # Paths
    workspace_root = Path(__file__).parent.parent.parent.parent

    # Use Pure Pursuit config but override for data collection
    config_path = workspace_root / "experiments/configs/pure_pursuit.yaml"
    config = ExperimentConfig.from_yaml(config_path)

    # Override settings for data collection
    config.experiment.name = "data_collection"
    config.execution.max_steps = 2000

    # Enable MCAP and JSON logging (JSON is needed for training script currently)
    # Note: ExperimentRunner currently logs to MCAP.
    # The training script reads JSON via SimulationLog.load().
    # SimulationLog.load() supports JSON.
    # ExperimentRunner uses SimulationLog which can save to JSON?
    # ExperimentRunner logs to MCAP via MCAPLogger.
    # It also keeps 'log' object which is SimulationLog.
    # We need to save that 'log' object to JSON.

    # We can use ExperimentRunner but we need to extract the log and save it as JSON.
    # Or we can modify ExperimentRunner to support JSON output.
    # Or we can just run it here and save it.

    runner = ExperimentRunner(config)
    runner._setup_components()
    runner._setup_mlflow()

    # We need to access the log after run.
    # runner.run() doesn't return the log.
    # Let's use _run_inference logic but capture the log.

    # Actually, let's just use runner.run() and then if we need JSON, we might need to convert MCAP to JSON
    # or modify runner to save JSON.
    # But wait, train.py loads from 'log_pure_pursuit.json'.
    # SimulationLog.load() reads JSON.

    # Let's modify ExperimentRunner to allow saving as JSON or just do it here manually.
    # Since I cannot easily modify runner.run() return value without changing interface,
    # I will copy the run logic here or rely on MCAP.
    # But train.py uses SimulationLog.load(raw_data_path).
    # Does SimulationLog.load support MCAP? No, it uses json.load.

    # So I need JSON.
    # I will manually run the simulation here using components.

    # Setup
    runner._setup_components()
    simulator = runner.simulator
    planner = runner.planner
    controller = runner.controller

    if not simulator or not planner or not controller:
        print("Error: Components not initialized.")
        return

    from core.data import SimulationLog, SimulationStep

    # Initialize log
    params = {
        "planner": config.components.planning.type,
        "controller": config.components.control.type,
        "track": str(runner.track_path) if runner.track_path else "",
    }
    log = SimulationLog(metadata=params)

    print("Starting data collection...")

    for step in range(config.execution.max_steps):
        current_state = simulator.current_state

        # Plan
        target_trajectory = planner.plan(None, current_state)  # type: ignore

        # Control
        action = controller.control(target_trajectory, current_state)

        # Simulate
        simulator.step(action)

        # Log
        sim_step = SimulationStep(
            timestamp=step * simulator.dt,  # type: ignore
            vehicle_state=current_state,
            action=action,
        )
        log.add_step(sim_step)

        if step % 100 == 0:
            print(f"Step {step}: v={current_state.velocity:.2f}")

        # Check end
        if hasattr(planner, "reference_trajectory") and planner.reference_trajectory:  # type: ignore
            ref = planner.reference_trajectory  # type: ignore
            dist = ((current_state.x - ref[-1].x) ** 2 + (current_state.y - ref[-1].y) ** 2) ** 0.5
            if dist < 2.0 and step > 100:
                print("Reached goal!")
                break

    # Save to JSON
    output_path = workspace_root / "data/training/raw/log_pure_pursuit.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log.save(output_path)
    print(f"Saved log to {output_path}")


if __name__ == "__main__":
    main()
