"""Data structures for the visualization dashboard."""

from typing import Any, TypedDict


class DashboardData(TypedDict):
    """
    Column-oriented dashboard data structure.
    All list fields must have the same length as timestamps, except metadata/vehicle_params.
    """

    timestamps: list[float]
    vehicle: dict[str, list[float]]  # x, y, yaw, velocity
    action: dict[str, list[float]]  # acceleration, steering
    obstacles: list[dict[str, Any]]  # Static obstacles list
    metadata: dict[str, Any]
    ad_logs: list[dict[str, Any]]  # List of dicts, one per step
