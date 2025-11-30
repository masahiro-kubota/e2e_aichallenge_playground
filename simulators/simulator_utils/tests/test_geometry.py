"""Tests for simulator_utils package."""

import math

from simulator_utils.geometry import normalize_angle


def test_normalize_angle_positive() -> None:
    """正の角度の正規化をテスト."""
    assert abs(normalize_angle(0.0) - 0.0) < 1e-10
    assert abs(normalize_angle(math.pi / 2) - math.pi / 2) < 1e-10
    assert abs(normalize_angle(math.pi) - math.pi) < 1e-10


def test_normalize_angle_negative() -> None:
    """負の角度の正規化をテスト."""
    assert abs(normalize_angle(-math.pi / 2) - (-math.pi / 2)) < 1e-10
    assert abs(normalize_angle(-math.pi) - (-math.pi)) < 1e-10


def test_normalize_angle_wrap_positive() -> None:
    """正の方向の折り返しをテスト."""
    # 2π + π/2 should wrap to π/2
    result = normalize_angle(2 * math.pi + math.pi / 2)
    assert abs(result - math.pi / 2) < 1e-10

    # 3π should wrap to π
    result = normalize_angle(3 * math.pi)
    assert abs(result - math.pi) < 1e-10


def test_normalize_angle_wrap_negative() -> None:
    """負の方向の折り返しをテスト."""
    # -2π - π/2 should wrap to -π/2
    result = normalize_angle(-2 * math.pi - math.pi / 2)
    assert abs(result - (-math.pi / 2)) < 1e-10

    # -3π should wrap to -π
    result = normalize_angle(-3 * math.pi)
    assert abs(result - (-math.pi)) < 1e-10
