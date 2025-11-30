"""Coordinate transformation utilities."""

import numpy as np

from core.utils.geometry import normalize_angle


def global_to_local(
    global_x: float,
    global_y: float,
    origin_x: float,
    origin_y: float,
    origin_yaw: float,
) -> tuple[float, float]:
    """グローバル座標からローカル座標に変換.

    Args:
        global_x, global_y: グローバル座標
        origin_x, origin_y: ローカル座標系の原点（グローバル座標）
        origin_yaw: ローカル座標系のヨー角 [rad]

    Returns:
        ローカル座標 (x, y)
    """
    # 原点に平行移動
    dx = global_x - origin_x
    dy = global_y - origin_y

    # 回転
    cos_yaw = np.cos(-origin_yaw)
    sin_yaw = np.sin(-origin_yaw)

    local_x = dx * cos_yaw - dy * sin_yaw
    local_y = dx * sin_yaw + dy * cos_yaw

    return local_x, local_y


def local_to_global(
    local_x: float,
    local_y: float,
    origin_x: float,
    origin_y: float,
    origin_yaw: float,
) -> tuple[float, float]:
    """ローカル座標からグローバル座標に変換.

    Args:
        local_x, local_y: ローカル座標
        origin_x, origin_y: ローカル座標系の原点（グローバル座標）
        origin_yaw: ローカル座標系のヨー角 [rad]

    Returns:
        グローバル座標 (x, y)
    """
    # 回転
    cos_yaw = np.cos(origin_yaw)
    sin_yaw = np.sin(origin_yaw)

    rotated_x = local_x * cos_yaw - local_y * sin_yaw
    rotated_y = local_x * sin_yaw + local_y * cos_yaw

    # 平行移動
    global_x = rotated_x + origin_x
    global_y = rotated_y + origin_y

    return global_x, global_y


def transform_angle_to_local(
    global_angle: float,
    origin_yaw: float,
) -> float:
    """グローバル角度をローカル角度に変換.

    Args:
        global_angle: グローバル角度 [rad]
        origin_yaw: ローカル座標系のヨー角 [rad]

    Returns:
        ローカル角度 [rad]
    """
    return normalize_angle(global_angle - origin_yaw)


def transform_angle_to_global(
    local_angle: float,
    origin_yaw: float,
) -> float:
    """ローカル角度をグローバル角度に変換.

    Args:
        local_angle: ローカル角度 [rad]
        origin_yaw: ローカル座標系のヨー角 [rad]

    Returns:
        グローバル角度 [rad]
    """
    return normalize_angle(local_angle + origin_yaw)


def rotation_matrix_2d(angle: float) -> np.ndarray:
    """2D回転行列を生成.

    Args:
        angle: 回転角度 [rad]

    Returns:
        2x2回転行列
    """
    cos_angle = np.cos(angle)
    sin_angle = np.sin(angle)
    return np.array([[cos_angle, -sin_angle], [sin_angle, cos_angle]])


def transformation_matrix_2d(x: float, y: float, yaw: float) -> np.ndarray:
    """2D同次変換行列を生成.

    Args:
        x, y: 平行移動
        yaw: 回転角度 [rad]

    Returns:
        3x3同次変換行列
    """
    cos_yaw = np.cos(yaw)
    sin_yaw = np.sin(yaw)
    return np.array([[cos_yaw, -sin_yaw, x], [sin_yaw, cos_yaw, y], [0, 0, 1]])


__all__ = [
    "global_to_local",
    "local_to_global",
    "rotation_matrix_2d",
    "transform_angle_to_global",
    "transform_angle_to_local",
    "transformation_matrix_2d",
]
