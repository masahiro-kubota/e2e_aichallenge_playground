from dataclasses import dataclass

from core.data.experiment.config import ResolvedExperimentConfig
from core.interfaces import Node


@dataclass
class Experiment:
    """An executable experiment definition containing configuration and initialized nodes."""

    id: str
    type: str
    config: ResolvedExperimentConfig
    nodes: list[Node]
