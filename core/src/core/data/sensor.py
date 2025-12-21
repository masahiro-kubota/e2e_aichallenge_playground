from pydantic import BaseModel

from core.data.node import ComponentConfig


class LidarConfig(ComponentConfig):
    """Configuration for LiDAR sensor."""

    num_beams: int = 720
    fov: float = 270.0  # degrees
    range_min: float = 0.1
    range_max: float = 30.0
    angle_increment: float = 0.0  # If 0, calculated from num_beams and fov
    # Mounting position relative to vehicle center
    x: float = 0.0
    y: float = 0.0
    z: float = 2.0  # 3D only, but good to have
    yaw: float = 0.0


class LidarScan(BaseModel):
    """LiDAR scan data."""

    timestamp: float
    config: LidarConfig
    ranges: list[float]  # inf for no return
    intensities: list[float] | None = None
