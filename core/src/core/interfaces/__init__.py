"""Core interfaces for the simulation framework."""

from core.interfaces.ad_components import ADComponent
from core.interfaces.dashboard import DashboardGenerator
from core.interfaces.experiment import ExperimentLogger
from core.interfaces.node import Node, SimulationContext
from core.interfaces.node_io import NodeIO
from core.interfaces.processor import ProcessorProtocol
from core.interfaces.simulator import SimulationLogRepository, Simulator
from core.interfaces.vehicle import VehicleParametersRepository

__all__ = [
    "ADComponent",
    "DashboardGenerator",
    "ExperimentLogger",
    "Node",
    "NodeIO",
    "ProcessorProtocol",
    "SimulationContext",
    "SimulationLogRepository",
    "Simulator",
    "VehicleParametersRepository",
]
