"""Experiment configuration data structures."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from core.interfaces.node import StrictConfig


class ExperimentType(str, Enum):
    """実験タイプ."""

    EVALUATION = "evaluation"
    DATA_COLLECTION = "data_collection"
    TRAINING = "training"


# Copied from experiment/src/experiment/preprocessing/schemas.py


class NodeConfig(BaseModel):
    """Unified configuration for any node (Simulator, Supervisor, AD components, Logger)."""

    name: str = Field(..., description="Node name (unique identifier)")
    type: str = Field(..., description="Node type (class or entry point)")
    rate_hz: float = Field(..., description="Node execution rate in Hz")
    params: dict[str, Any] = Field(default_factory=dict, description="Node parameters")


class ExecutionConfig(BaseModel):
    """Configuration for execution."""

    num_episodes: int = Field(..., description="Number of episodes to run")
    clock_rate_hz: float = Field(
        ..., description="Clock rate in Hz (should match simulator.rate_hz for efficiency)"
    )
    duration_sec: float = Field(..., description="Simulation duration in seconds")
    parallel: bool = Field(..., description="Run episodes in parallel")
    num_workers: int = Field(..., description="Number of parallel workers")

    # Future support for executor/clock switching
    clock_type: Literal["stepped", "realtime", "external"] = Field(
        ..., description="Clock type for simulation timing"
    )


class EvaluationConfig(BaseModel):
    """Configuration for evaluation."""

    metrics: list[str] = Field(
        ...,
        description="Metrics to calculate",
    )
    generate_dashboard: bool = Field(..., description="Generate dashboard")


class MLflowConfig(StrictConfig):
    """Configuration for MLflow logging."""

    enabled: bool = Field(..., description="Enable MLflow logging")
    tracking_uri: str = Field(..., description="MLflow tracking URI")


class MCAPConfig(StrictConfig):
    """Configuration for MCAP logging."""

    enabled: bool = Field(..., description="Enable MCAP logging")
    output_dir: str = Field(..., description="Output directory for MCAP files")


class DashboardConfig(StrictConfig):
    """Configuration for dashboard generation."""

    enabled: bool = Field(..., description="Enable dashboard generation")
    map_path: str = Field(..., description="Path to Lanelet2 OSM map file for visualization")
    vehicle_config_path: str = Field(..., description="Path to vehicle configuration YAML file")


class PostprocessConfig(StrictConfig):
    """Configuration for postprocessing (logging, metrics, dashboard)."""

    inputs: list[str] = Field(..., description="List of input files to log as artifacts")
    mlflow: MLflowConfig = Field(...)
    mcap: MCAPConfig = Field(...)
    dashboard: DashboardConfig = Field(...)


class ExperimentMetadata(BaseModel):
    """Experiment metadata."""

    name: str = Field(..., description="Experiment name")
    type: ExperimentType = Field(..., description="Experiment type")
    description: str = Field(..., description="Experiment description")


class ModuleConfig(BaseModel):
    """Module configuration (Pipeline definition)."""

    name: str = Field(..., description="Module name")
    nodes: list[NodeConfig] = Field(..., description="All nodes in execution order")


class SystemConfig(BaseModel):
    """System configuration (Environment settings)."""

    name: str = Field(..., description="System name")
    module: str = Field(..., description="Path to module configuration")
    vehicle: dict[str, Any] = Field(..., description="Vehicle configuration")
    map_path: str = Field(..., description="Path to map file (e.g. Lanelet2 OSM)")


class ExperimentLayerConfig(BaseModel):
    """Experiment layer configuration."""

    # Experiment metadata (can be at root or nested under 'experiment' key)
    name: str = Field(..., description="Experiment name")
    type: ExperimentType = Field(..., description="Experiment type")
    description: str = Field("", description="Experiment description")

    # Configuration fields
    system: str = Field(..., description="Path to system configuration")
    execution: ExecutionConfig = Field(..., description="Execution configuration")
    postprocess: PostprocessConfig = Field(..., description="Postprocessing configuration")


class ResolvedExperimentConfig(BaseModel):
    """Complete, resolved experiment configuration for evaluation experiments."""

    experiment: ExperimentMetadata = Field(..., description="Experiment metadata")
    nodes: list[NodeConfig] = Field(..., description="All resolved node configurations")
    execution: ExecutionConfig = Field(..., description="Execution configuration")
    postprocess: PostprocessConfig = Field(..., description="Postprocessing configuration")


class ExperimentFile(StrictConfig):
    """Experiment YAML file structure."""

    experiment: ExperimentLayerConfig


class SystemFile(StrictConfig):
    """System YAML file structure."""

    system: SystemConfig


class ModuleFile(StrictConfig):
    """Module YAML file structure."""

    module: ModuleConfig
