#!/usr/bin/env python3
import math
import subprocess
import time


def main():
    print("Benchmarking Parallel Simulation Throughput...")

    # Configuration
    total_episodes = 96
    n_jobs = 16  # Adjust based on CPU cores

    # We use 'evaluation' mode which has joblib launcher enabled by default (via defaults)
    # But we override components to pure_pursuit to avoid model dependencies
    episodes_per_job = math.ceil(total_episodes / n_jobs)
    total_swept_episodes = episodes_per_job * n_jobs
    duration_sim_time = 30.0

    cmd = [
        "uv",
        "run",
        "experiment-runner",
        "-m",  # Multirun mode
        "experiment=data_collection",  # Use data_collection mode
        "env=no_obstacle",  # Use no_obstacle environment
        "ad_components=pure_pursuit",  # Use lightweight logical component
        f"execution.duration_sec={duration_sim_time}",
        f"execution.total_episodes={total_episodes}",  # Total episodes to run
        f"execution.num_jobs={n_jobs}",  # Number of parallel jobs
        # Sweep base seed for each chunk: range(0, total, step)
        f"+env.initial_state_sampling.seed=range(0,{total_swept_episodes},{episodes_per_job})",
        "execution.enable_progress_bar=False",  # Reduce output noise
        "postprocess.foxglove.auto_open=false",  # Disable Foxglove auto-open
        "+postprocess.foxglove.enabled=false",  # Disable Foxglove server completely (using + to append)
        "hydra.sweep.dir=outputs/benchmark_parallel",  # Isolated output
        "hydra.sweep.subdir=${hydra.job.num}",
    ]

    print(f"Command: {' '.join(cmd)}")
    print(f"Running {total_episodes} episodes with {n_jobs} parallel jobs...")

    start_time = time.time()

    # Run the command
    result = subprocess.run(cmd, capture_output=True, text=True)

    end_time = time.time()
    duration = end_time - start_time

    if result.returncode != 0:
        print("Error occurred during benchmark execution!")
        print(result.stderr)
        return

    # Calculate metrics
    throughput = total_episodes / duration
    # Assuming each episode is 200s (default simulation duration)
    # Real-Time Factor = (Total Simulated Time) / (Total Wall Time)
    # But here we ran N episodes in parallel.
    # Aggregate Simulated Time = total_episodes * 200s
    total_simulated_time = total_episodes * duration_sim_time  # Default duration
    real_time_factor = total_simulated_time / duration

    print("-" * 60)
    print("Benchmark Results")
    print("-" * 60)
    print(f"Total Wall Time:  {duration:.2f} s")
    print(f"Total Episodes:   {total_episodes}")
    print(f"Throughput:       {throughput:.2f} episodes/s")
    print(f"Simulated Time:   {total_simulated_time:.1f} s (Aggregate)")
    print(f"Real-Time Factor: {real_time_factor:.2f}x (Aggregate Speedup)")
    print("-" * 60)

    # Extract some hydra output stats if needed
    # (Hydra usually prints job info to stderr)


if __name__ == "__main__":
    main()
