"""Core framework for autonomous driving components."""

from core.data import Action, Observation, Trajectory, VehicleState
from core.interfaces import (
    ControlComponent,
    PerceptionComponent,
    PlanningComponent,
    Simulator,
)

__all__ = [
    "Action",
    "ControlComponent",
    "Observation",
    "PerceptionComponent",
    "PlanningComponent",
    "Simulator",
    "Trajectory",
    "VehicleState",
]
