"""Core utilities and base classes for simulators."""

from core.utils.geometry import normalize_angle
from simulator_core.base import BaseSimulator
from simulator_core.environment import Obstacle, ObstacleType, Scene, TrackBoundary
from simulator_core.integration import euler_step, rk4_step
from simulator_core.vehicle import VehicleParameters

__all__ = [
    "BaseSimulator",
    "Obstacle",
    "ObstacleType",
    "Scene",
    "TrackBoundary",
    "VehicleParameters",
    "euler_step",
    "normalize_angle",
    "rk4_step",
]
