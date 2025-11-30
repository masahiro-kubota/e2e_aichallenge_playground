"""Tire models for dynamic simulator."""

from abc import ABC, abstractmethod


class TireModel(ABC):
    """タイヤモデルの抽象基底クラス."""

    @abstractmethod
    def lateral_force(self, slip_angle: float, normal_force: float) -> float:
        """横方向力を計算.

        Args:
            slip_angle: 横滑り角 [rad]
            normal_force: 垂直荷重 [N]

        Returns:
            横方向力 [N]
        """


class LinearTireModel(TireModel):
    """線形タイヤモデル.

    F_y = C_alpha * alpha
    """

    def __init__(self, cornering_stiffness: float) -> None:
        """初期化.

        Args:
            cornering_stiffness: コーナリング剛性 [N/rad]
        """
        self.cornering_stiffness = cornering_stiffness

    def lateral_force(self, slip_angle: float, _normal_force: float) -> float:
        """横方向力を計算.

        Args:
            slip_angle: 横滑り角 [rad]
            normal_force: 垂直荷重 [N] (未使用)

        Returns:
            横方向力 [N]
        """
        return self.cornering_stiffness * slip_angle
