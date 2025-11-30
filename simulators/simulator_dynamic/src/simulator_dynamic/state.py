"""Vehicle state for dynamic simulator."""

from dataclasses import dataclass


@dataclass
class DynamicVehicleState:
    """ダイナミックモデル用の拡張車両状態."""

    # 位置・姿勢
    x: float  # X座標 [m]
    y: float  # Y座標 [m]
    yaw: float  # ヨー角 [rad]

    # 速度
    vx: float  # 縦方向速度 [m/s]
    vy: float  # 横方向速度 [m/s]
    yaw_rate: float  # ヨーレート [rad/s]

    # 入力
    steering: float = 0.0  # ステアリング角 [rad]
    throttle: float = 0.0  # スロットル [-1.0 to 1.0]

    # タイムスタンプ
    timestamp: float | None = None

    @property
    def velocity(self) -> float:
        """合成速度 [m/s]."""
        return (self.vx**2 + self.vy**2) ** 0.5

    @property
    def beta(self) -> float:
        """車体横滑り角 [rad]."""
        if abs(self.vx) < 0.1:
            return 0.0
        import math

        return math.atan2(self.vy, self.vx)
