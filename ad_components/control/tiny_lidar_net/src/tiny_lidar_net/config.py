"""Configuration for Tiny LiDAR Net node."""

from pathlib import Path

from pydantic import Field

from core.data import ComponentConfig, VehicleParameters


class TinyLidarNetConfig(ComponentConfig):
    """Configuration for TinyLidarNetNode."""

    model_path: Path = Field(..., description="Path to .npy weights file")
    input_dim: int = Field(1080, description="LiDAR input dimension (number of beams)")
    output_dim: int = Field(2, description="Output dimension (acceleration, steering)")
    architecture: str = Field("large", description="Model architecture ('large' or 'small')")
    max_range: float = Field(30.0, description="Maximum LiDAR range for normalization [m]")
    control_mode: str = Field("ai", description="Control mode ('ai' or 'fixed')")
    fixed_acceleration: float = Field(
        0.1, description="Fixed acceleration when control_mode='fixed'"
    )
    vehicle_params: VehicleParameters = Field(..., description="Vehicle parameters")
