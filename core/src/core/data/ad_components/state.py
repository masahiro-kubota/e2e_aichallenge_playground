"""Vehicle state data structure."""

from dataclasses import dataclass

import numpy as np


@dataclass
class VehicleState:
    """車両の状態を表すデータクラス."""

    x: float  # X座標 [m]
    y: float  # Y座標 [m]
    yaw: float  # ヨー角 [rad]
    velocity: float  # 速度 [m/s]
    acceleration: float = 0.0  # 加速度 [m/s^2]
    steering: float = 0.0  # ステアリング角 [rad]
    steering_rate: float = 0.0  # ステアリング角速度 [rad/s]
    timestamp: float = 0.0  # タイムスタンプ [s]
    off_track: bool = False  # コース外判定フラグ
    collision: bool = False  # 障害物との衝突フラグ

    def to_array(self) -> np.ndarray:
        """numpy配列に変換."""
        # Note: off_track is not included in the array representation for now
        # to maintain compatibility with controllers/planners that expect specific size
        return np.array([self.x, self.y, self.yaw, self.velocity, self.steering_rate])

    @classmethod
    def from_array(cls, arr: np.ndarray, timestamp: float = 0.0) -> "VehicleState":
        """numpy配列から生成."""
        # Support both old (4 elements) and new (5 elements) formats for backward compatibility
        if len(arr) >= 5:
            return cls(
                x=arr[0],
                y=arr[1],
                yaw=arr[2],
                velocity=arr[3],
                steering_rate=arr[4],
                timestamp=timestamp,
            )
        return cls(x=arr[0], y=arr[1], yaw=arr[2], velocity=arr[3], timestamp=timestamp)
