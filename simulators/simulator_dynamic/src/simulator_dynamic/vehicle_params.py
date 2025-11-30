"""Vehicle parameters for dynamic simulator."""

from dataclasses import dataclass


@dataclass
class VehicleParameters:
    """車両の物理パラメータ."""

    # 質量・慣性
    mass: float = 1500.0  # 質量 [kg]
    iz: float = 2500.0  # ヨー慣性モーメント [kg*m^2]

    # 寸法
    wheelbase: float = 2.5  # ホイールベース [m]
    lf: float = 1.2  # 重心から前軸までの距離 [m]
    lr: float = 1.3  # 重心から後軸までの距離 [m]

    # タイヤ特性
    cf: float = 80000.0  # 前輪コーナリング剛性 [N/rad]
    cr: float = 80000.0  # 後輪コーナリング剛性 [N/rad]

    # 抵抗係数
    c_drag: float = 0.3  # 空気抵抗係数
    c_roll: float = 0.015  # 転がり抵抗係数

    # 駆動力
    max_drive_force: float = 5000.0  # 最大駆動力 [N]
    max_brake_force: float = 8000.0  # 最大制動力 [N]

    def __post_init__(self) -> None:
        """初期化後の検証."""
        # ホイールベースの整合性チェック
        if abs(self.lf + self.lr - self.wheelbase) > 1e-6:
            msg = (
                f"Wheelbase mismatch: lf({self.lf}) + lr({self.lr}) != wheelbase({self.wheelbase})"
            )
            raise ValueError(msg)
