# Lateral Shift Planner

Static avoidance planner that generates lateral shift profiles to avoid obstacles.

## Features

- **Shift Profile Generation**: Calculates required lateral shift for each obstacle based on dimensions and safety margins.
- **Yaw-Aware Projection**: Projects obstacle corners to Frenet frame considering obstacle yaw for accurate bounding box calculation.
- **Profile Merging**: Merges multiple shift profiles (taking maximum shift) to handle multiple obstacles.
- **Output**: Generates a trajectory with target lateral positions.

## Configuration

See `lateral_shift.yaml` and `LateralShiftPlannerConfig` class.
