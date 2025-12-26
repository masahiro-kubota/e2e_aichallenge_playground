"""Obstacle management and collision detection."""

import math
from typing import TYPE_CHECKING

from core.data import CsvPathTrajectory, ObstacleTrajectory
from core.utils.obstacle_utils import get_obstacle_state as get_obstacle_state_impl
from core.utils.obstacle_utils import load_csv_trajectory as load_csv_trajectory_impl

if TYPE_CHECKING:
    from core.data import ObstacleState, SimulatorObstacle
    from shapely.geometry import Polygon


def load_csv_trajectory(trajectory: CsvPathTrajectory) -> ObstacleTrajectory:
    """Load a CSV path and convert it into a waypoint trajectory."""
    return load_csv_trajectory_impl(trajectory)


def get_obstacle_state(obstacle: "SimulatorObstacle", time: float) -> "ObstacleState":
    """Get obstacle state at a specific time."""
    return get_obstacle_state_impl(obstacle, time)


def get_obstacle_polygon(obstacle: "SimulatorObstacle", state: "ObstacleState") -> "Polygon":
    """Get obstacle polygon for collision detection.

    Args:
        obstacle: Obstacle definition
        state: Obstacle state

    Returns:
        Shapely Polygon
    """
    from shapely.geometry import Point, Polygon

    shape = obstacle.shape

    if shape.type == "circle":
        if shape.radius is None:
            msg = "Circle shape must have radius"
            raise ValueError(msg)
        # Create circle as polygon with 16 points
        center = Point(state.x, state.y)
        return center.buffer(shape.radius)

    if shape.type == "rectangle":
        if shape.width is None or shape.length is None:
            msg = "Rectangle shape must have width and length"
            raise ValueError(msg)

        # Create rectangle polygon
        # Rectangle is centered at (state.x, state.y) with orientation state.yaw
        half_width = shape.width / 2.0
        half_length = shape.length / 2.0

        # Rectangle corners in local frame (x forward, y left)
        corners = [
            (half_length, half_width),
            (half_length, -half_width),
            (-half_length, -half_width),
            (-half_length, half_width),
        ]

        # Transform to global frame
        cos_yaw = math.cos(state.yaw)
        sin_yaw = math.sin(state.yaw)

        points = []
        for lx, ly in corners:
            # Rotate
            gx = lx * cos_yaw - ly * sin_yaw
            gy = lx * sin_yaw + ly * cos_yaw
            # Translate
            points.append((gx + state.x, gy + state.y))

        return Polygon(points)

    msg = f"Unknown shape type: {shape.type}"
    raise ValueError(msg)


def check_collision(vehicle_polygon: "Polygon", obstacle_polygon: "Polygon") -> bool:
    """Check collision between vehicle and obstacle.

    Args:
        vehicle_polygon: Vehicle polygon
        obstacle_polygon: Obstacle polygon

    Returns:
        True if collision detected
    """
    return vehicle_polygon.intersects(obstacle_polygon)


class ObstacleManager:
    """Manage multiple obstacles and check collisions."""

    def __init__(self, obstacles: list["SimulatorObstacle"]) -> None:
        """Initialize obstacle manager.

        Args:
            obstacles: List of obstacles
        """
        self.obstacles = obstacles

    def check_vehicle_collision(self, vehicle_polygon: "Polygon", current_time: float) -> bool:
        """Check if vehicle collides with any obstacle.

        Args:
            vehicle_polygon: Vehicle polygon
            current_time: Current simulation time [s]

        Returns:
            True if collision detected
        """
        for obstacle in self.obstacles:
            obstacle_state = get_obstacle_state(obstacle, current_time)
            obstacle_polygon = get_obstacle_polygon(obstacle, obstacle_state)

            if check_collision(vehicle_polygon, obstacle_polygon):
                return True

        return False
