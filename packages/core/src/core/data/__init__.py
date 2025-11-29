"""Data structures for autonomous driving."""

from dataclasses import dataclass

import numpy as np


@dataclass
class VehicleState:
    """車両の状態を表すデータクラス."""

    x: float  # X座標 [m]
    y: float  # Y座標 [m]
    yaw: float  # ヨー角 [rad]
    velocity: float  # 速度 [m/s]
    acceleration: float | None = None  # 加速度 [m/s^2]
    steering: float | None = None  # ステアリング角 [rad]
    timestamp: float | None = None  # タイムスタンプ [s]

    def to_array(self) -> np.ndarray:
        """numpy配列に変換."""
        return np.array([self.x, self.y, self.yaw, self.velocity])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "VehicleState":
        """numpy配列から生成."""
        return cls(x=arr[0], y=arr[1], yaw=arr[2], velocity=arr[3])


@dataclass
class Observation:
    """センサー観測データを表すデータクラス."""

    lateral_error: float  # 横方向偏差 [m]
    heading_error: float  # ヨー角偏差 [rad]
    velocity: float  # 現在速度 [m/s]
    target_velocity: float  # 目標速度 [m/s]
    distance_to_goal: float | None = None  # ゴールまでの距離 [m]
    timestamp: float | None = None  # タイムスタンプ [s]

    def to_array(self) -> np.ndarray:
        """numpy配列に変換."""
        return np.array(
            [
                self.lateral_error,
                self.heading_error,
                self.velocity,
                self.target_velocity,
            ]
        )

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "Observation":
        """numpy配列から生成."""
        return cls(
            lateral_error=arr[0],
            heading_error=arr[1],
            velocity=arr[2],
            target_velocity=arr[3],
        )


@dataclass
class Action:
    """制御指令を表すデータクラス."""

    steering: float  # ステアリング角 [rad]
    acceleration: float  # 加速度 [m/s^2]
    timestamp: float | None = None  # タイムスタンプ [s]

    def to_array(self) -> np.ndarray:
        """numpy配列に変換."""
        return np.array([self.steering, self.acceleration])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "Action":
        """numpy配列から生成."""
        return cls(steering=arr[0], acceleration=arr[1])


@dataclass
class TrajectoryPoint:
    """軌道上の1点を表すデータクラス."""

    x: float  # X座標 [m]
    y: float  # Y座標 [m]
    yaw: float  # ヨー角 [rad]
    velocity: float  # 速度 [m/s]
    curvature: float | None = None  # 曲率 [1/m]
    timestamp: float | None = None  # タイムスタンプ [s]


@dataclass
class Trajectory:
    """軌道を表すデータクラス."""

    points: list[TrajectoryPoint]  # 軌道点のリスト

    def __len__(self) -> int:
        """軌道点の数を返す."""
        return len(self.points)

    def __getitem__(self, idx: int) -> TrajectoryPoint:
        """インデックスで軌道点を取得."""
        return self.points[idx]

    def to_arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """numpy配列に変換 (x, y, yaw, velocity)."""
        x = np.array([p.x for p in self.points])
        y = np.array([p.y for p in self.points])
        yaw = np.array([p.yaw for p in self.points])
        velocity = np.array([p.velocity for p in self.points])
        return x, y, yaw, velocity
