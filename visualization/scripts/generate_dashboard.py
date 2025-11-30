"""Generate interactive HTML dashboard from SimulationLog using React template."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.data import SimulationLog


def generate_dashboard(
    log: SimulationLog, output_path: str | Path, osm_path: str | Path | None = None
) -> None:
    """Generate interactive HTML dashboard.

    Args:
        log: Simulation log
        output_path: Output HTML file path
        osm_path: Optional path to OSM file for map display
    """
    # 1. Prepare data
    data: dict[str, Any] = {
        "metadata": {
            "controller": log.metadata.get("controller", "Unknown Controller"),
            "execution_time": log.metadata.get("execution_time", "Unknown Time"),
            **log.metadata,
        },
        "steps": [],
    }

    for step in log.steps:
        data["steps"].append(
            {
                "timestamp": step.timestamp,
                "x": step.vehicle_state.x,
                "y": step.vehicle_state.y,
                "z": getattr(step.vehicle_state, "z", 0.0),
                "yaw": step.vehicle_state.yaw,
                "velocity": step.vehicle_state.velocity,
                "acceleration": step.action.acceleration,
                "steering": step.action.steering,
            }
        )

    # 2. Find paths
    script_dir = Path(__file__).parent
    workspace_root = script_dir.parent.parent
    template_path = script_dir.parent / "dashboard" / "dist" / "index.html"
    inject_script = workspace_root / "tools" / "dashboard" / "inject_data.py"

    if not template_path.exists():
        print(f"Error: Dashboard template not found at {template_path}")
        print("Please build the dashboard first: cd tools/dashboard && npm run build")
        return

    if not inject_script.exists():
        print(f"Error: inject_data.py not found at {inject_script}")
        return

    # 3. Write temporary JSON file
    temp_json = Path("/tmp/simulation_log_temp.json")
    with open(temp_json, "w", encoding="utf-8") as f:
        json.dump(data, f)

    # 4. Use inject_data.py to generate dashboard with optional OSM
    try:
        cmd = [
            sys.executable,
            str(inject_script),
            str(template_path),
            str(temp_json),
            str(output_path),
        ]

        # Add OSM path if provided
        if osm_path is not None:
            osm_path = Path(osm_path)
            if osm_path.exists():
                cmd.extend(["--osm-path", str(osm_path)])
            else:
                print(f"Warning: OSM file not found at {osm_path}, skipping map data")

        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        print(f"Dashboard saved to {output_path}")

    except subprocess.CalledProcessError as e:
        print(f"Error generating dashboard: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        raise
    finally:
        # Clean up temp file
        if temp_json.exists():
            temp_json.unlink()


def main() -> None:
    """Generate dashboard from command line."""
    parser = argparse.ArgumentParser(description="Generate interactive HTML dashboard")
    parser.add_argument("log_file", help="Path to SimulationLog JSON file")
    parser.add_argument("-o", "--output", required=True, help="Output HTML file path")
    parser.add_argument("--osm-path", help="Optional path to OSM file for map display")

    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"Error: Log file not found: {log_path}")
        return

    print(f"Loading log from {log_path}...")
    log = SimulationLog.load(log_path)
    print(f"Loaded {len(log.steps)} steps")

    osm_path = Path(args.osm_path) if args.osm_path else None
    generate_dashboard(log, args.output, osm_path)
    print(f"\nOpen {args.output} in a browser to view the dashboard")


if __name__ == "__main__":
    main()
