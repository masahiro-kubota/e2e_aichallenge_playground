from pathlib import Path

from core.data import ComponentConfig, VehicleParameters
from pydantic import Field


class SpatialTemporalLidarNetConfig(ComponentConfig):
    """Configuration for SpatialTemporalLidarNetNode."""

    model_path: Path = Field(..., description="Path to .pth weights file")
    num_frames: int = Field(20, description="Number of historical frames to stack")
    max_range: float = Field(30.0, description="Maximum LiDAR range for normalization [m]")
    target_velocity: float = Field(10.0, description="Target velocity [m/s]")
    device: str = Field("cpu", description="Device for inference (cpu/cuda)")
    vehicle_params: VehicleParameters = Field(..., description="Vehicle parameters")
