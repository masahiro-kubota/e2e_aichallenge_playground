"""Tests for geometry utility functions."""

import math

import numpy as np
import pytest

from core.utils.geometry import (
    angle_between_points,
    curvature_from_points,
    distance,
    nearest_point_on_line,
    normalize_angle,
    rotate_point,
)


class TestNormalizeAngle:
    """Tests for normalize_angle function."""

    def test_zero(self) -> None:
        """Test normalization of zero angle."""
        assert normalize_angle(0.0) == 0.0

    def test_positive_small(self) -> None:
        """Test normalization of small positive angle."""
        assert abs(normalize_angle(1.0) - 1.0) < 1e-10

    def test_positive_large(self) -> None:
        """Test normalization of large positive angle."""
        result = normalize_angle(2 * math.pi + 1.0)
        assert abs(result - 1.0) < 1e-10

    def test_negative_small(self) -> None:
        """Test normalization of small negative angle."""
        assert abs(normalize_angle(-1.0) - (-1.0)) < 1e-10

    def test_negative_large(self) -> None:
        """Test normalization of large negative angle."""
        result = normalize_angle(-2 * math.pi - 1.0)
        assert abs(result - (-1.0)) < 1e-10

    def test_pi(self) -> None:
        """Test normalization of pi."""
        result = normalize_angle(math.pi)
        assert abs(result - math.pi) < 1e-10

    def test_minus_pi(self) -> None:
        """Test normalization of -pi."""
        result = normalize_angle(-math.pi)
        assert abs(result - (-math.pi)) < 1e-10


class TestDistance:
    """Tests for distance function."""

    def test_zero_distance(self) -> None:
        """Test distance between same points."""
        assert distance(0.0, 0.0, 0.0, 0.0) == 0.0

    def test_horizontal_distance(self) -> None:
        """Test horizontal distance."""
        assert distance(0.0, 0.0, 3.0, 0.0) == 3.0

    def test_vertical_distance(self) -> None:
        """Test vertical distance."""
        assert distance(0.0, 0.0, 0.0, 4.0) == 4.0

    def test_diagonal_distance(self) -> None:
        """Test diagonal distance (3-4-5 triangle)."""
        assert distance(0.0, 0.0, 3.0, 4.0) == 5.0

    def test_negative_coordinates(self) -> None:
        """Test distance with negative coordinates."""
        assert distance(-1.0, -1.0, 2.0, 3.0) == 5.0


class TestAngleBetweenPoints:
    """Tests for angle_between_points function."""

    def test_horizontal_right(self) -> None:
        """Test angle for horizontal right direction."""
        angle = angle_between_points(0.0, 0.0, 1.0, 0.0)
        assert abs(angle - 0.0) < 1e-10

    def test_vertical_up(self) -> None:
        """Test angle for vertical up direction."""
        angle = angle_between_points(0.0, 0.0, 0.0, 1.0)
        assert abs(angle - math.pi / 2) < 1e-10

    def test_horizontal_left(self) -> None:
        """Test angle for horizontal left direction."""
        angle = angle_between_points(0.0, 0.0, -1.0, 0.0)
        assert abs(angle - math.pi) < 1e-10

    def test_vertical_down(self) -> None:
        """Test angle for vertical down direction."""
        angle = angle_between_points(0.0, 0.0, 0.0, -1.0)
        assert abs(angle - (-math.pi / 2)) < 1e-10


class TestRotatePoint:
    """Tests for rotate_point function."""

    def test_no_rotation(self) -> None:
        """Test rotation by zero angle."""
        x, y = rotate_point(1.0, 0.0, 0.0)
        assert abs(x - 1.0) < 1e-10
        assert abs(y - 0.0) < 1e-10

    def test_90_degree_rotation(self) -> None:
        """Test 90 degree rotation."""
        x, y = rotate_point(1.0, 0.0, math.pi / 2)
        assert abs(x - 0.0) < 1e-10
        assert abs(y - 1.0) < 1e-10

    def test_180_degree_rotation(self) -> None:
        """Test 180 degree rotation."""
        x, y = rotate_point(1.0, 0.0, math.pi)
        assert abs(x - (-1.0)) < 1e-10
        assert abs(y - 0.0) < 1e-10

    def test_rotation_with_origin(self) -> None:
        """Test rotation around custom origin."""
        x, y = rotate_point(2.0, 1.0, math.pi / 2, origin_x=1.0, origin_y=1.0)
        assert abs(x - 1.0) < 1e-10
        assert abs(y - 2.0) < 1e-10


class TestNearestPointOnLine:
    """Tests for nearest_point_on_line function."""

    def test_point_on_line(self) -> None:
        """Test when point is on the line."""
        x, y, dist = nearest_point_on_line(1.0, 0.0, 0.0, 0.0, 2.0, 0.0)
        assert abs(x - 1.0) < 1e-10
        assert abs(y - 0.0) < 1e-10
        assert abs(dist - 0.0) < 1e-10

    def test_point_perpendicular(self) -> None:
        """Test point perpendicular to line."""
        x, y, dist = nearest_point_on_line(1.0, 1.0, 0.0, 0.0, 2.0, 0.0)
        assert abs(x - 1.0) < 1e-10
        assert abs(y - 0.0) < 1e-10
        assert abs(dist - 1.0) < 1e-10

    def test_point_before_start(self) -> None:
        """Test point before line segment start."""
        x, y, dist = nearest_point_on_line(-1.0, 1.0, 0.0, 0.0, 2.0, 0.0)
        assert abs(x - 0.0) < 1e-10
        assert abs(y - 0.0) < 1e-10
        assert abs(dist - math.sqrt(2)) < 1e-10

    def test_point_after_end(self) -> None:
        """Test point after line segment end."""
        x, y, dist = nearest_point_on_line(3.0, 1.0, 0.0, 0.0, 2.0, 0.0)
        assert abs(x - 2.0) < 1e-10
        assert abs(y - 0.0) < 1e-10
        assert abs(dist - math.sqrt(2)) < 1e-10


class TestCurvatureFromPoints:
    """Tests for curvature_from_points function."""

    def test_straight_line(self) -> None:
        """Test curvature of straight line (should be 0)."""
        curv = curvature_from_points(0.0, 0.0, 1.0, 0.0, 2.0, 0.0)
        assert abs(curv) < 1e-10

    def test_right_angle(self) -> None:
        """Test curvature of right angle."""
        # Points forming a right angle
        curv = curvature_from_points(0.0, 0.0, 1.0, 0.0, 1.0, 1.0)
        # For a right angle with unit sides, curvature should be non-zero
        assert curv > 0

    def test_circle(self) -> None:
        """Test curvature of circle points."""
        # Three points on a circle of radius 1
        curv = curvature_from_points(1.0, 0.0, 0.0, 1.0, -1.0, 0.0)
        # Curvature should be approximately 1/radius = 1
        assert abs(curv - 1.0) < 0.1  # Allow some numerical error
