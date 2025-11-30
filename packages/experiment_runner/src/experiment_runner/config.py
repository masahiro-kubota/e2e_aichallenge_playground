"""Configuration models for experiment runner."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class ComponentConfig(BaseModel):
    """Configuration for a component."""

    type: str = Field(..., description="Component class name")
    params: dict[str, Any] = Field(default_factory=dict, description="Component parameters")


class SimulatorConfig(BaseModel):
    """Configuration for simulator."""

    type: str = Field(..., description="Simulator class name")
    params: dict[str, Any] = Field(default_factory=dict, description="Simulator parameters")


class ExecutionConfig(BaseModel):
    """Configuration for execution."""

    mode: Literal["training", "inference"] = Field(..., description="Execution mode")
    max_steps: int = Field(2000, description="Maximum simulation steps")
    num_runs: int = Field(1, description="Number of runs")
    parallel: bool = Field(False, description="Run in parallel")


class TrainingConfig(BaseModel):
    """Configuration for training."""

    epochs: int = Field(100, description="Number of training epochs")
    batch_size: int = Field(32, description="Batch size")
    learning_rate: float = Field(0.001, description="Learning rate")
    validation_split: float = Field(0.2, description="Validation split ratio")


class MLflowConfig(BaseModel):
    """Configuration for MLflow logging."""

    enabled: bool = Field(True, description="Enable MLflow logging")
    tracking_uri: str = Field("http://localhost:5000", description="MLflow tracking URI")


class MCAPConfig(BaseModel):
    """Configuration for MCAP logging."""

    enabled: bool = Field(True, description="Enable MCAP logging")
    output_dir: str = Field("/tmp", description="Output directory for MCAP files")


class DashboardConfig(BaseModel):
    """Configuration for dashboard generation."""

    enabled: bool = Field(True, description="Enable dashboard generation")


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    mlflow: MLflowConfig = Field(default_factory=MLflowConfig)
    mcap: MCAPConfig = Field(default_factory=MCAPConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)


class ExperimentMetadata(BaseModel):
    """Experiment metadata."""

    name: str = Field(..., description="Experiment name")
    description: str = Field("", description="Experiment description")


class ComponentsConfig(BaseModel):
    """Configuration for all components."""

    perception: ComponentConfig | None = Field(None, description="Perception component config")
    planning: ComponentConfig = Field(..., description="Planning component config")
    control: ComponentConfig = Field(..., description="Control component config")


class ExperimentConfig(BaseModel):
    """Complete experiment configuration."""

    experiment: ExperimentMetadata = Field(..., description="Experiment metadata")
    components: ComponentsConfig = Field(..., description="Components configuration")
    simulator: SimulatorConfig = Field(..., description="Simulator configuration")
    execution: ExecutionConfig = Field(..., description="Execution configuration")
    training: TrainingConfig | None = Field(None, description="Training configuration")
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentConfig":
        """Load configuration from YAML file.

        Args:
            path: Path to YAML file

        Returns:
            ExperimentConfig instance
        """
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
