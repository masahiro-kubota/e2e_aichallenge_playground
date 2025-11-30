"""Geometry utility functions for simulators."""

import math


def normalize_angle(angle: float) -> float:
    """角度を[-π, π]の範囲に正規化.

    Args:
        angle: 角度 [rad]

    Returns:
        正規化された角度 [rad]
    """
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle
