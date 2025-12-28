from pathlib import Path

import numpy as np
from core.utils.osm_parser import parse_osm_for_collision
from shapely.geometry import LineString, Point
from shapely.prepared import prep


class RoadWidthMap:
    """Helper to calculate drivable area bounds."""

    def __init__(self, map_path: Path):
        self.drivable_area = parse_osm_for_collision(map_path)
        if self.drivable_area is None:
            raise ValueError(f"Failed to load drivable area from {map_path}")
        self.prepared = prep(self.drivable_area)

    def get_lateral_width(
        self, x: float, y: float, yaw: float, check_dist: float = 10.0
    ) -> float | None:
        """Calculate total road width (left + right) at specified position perpdendicular to yaw.

        Args:
            x: X coordinate
            y: Y coordinate
            yaw: Heading angle (radians)
            check_dist: Max distance to check on each side [m]

        Returns:
            Width [m] or None if calculation fails or outside map.
        """
        # Center point
        p = Point(x, y)
        if not self.prepared.contains(p):
            return None

        # Normal vector (Left)
        nx = -np.sin(yaw)
        ny = np.cos(yaw)

        # Construct line: P - check_dist * N to P + check_dist * N
        # Right to Left
        p_right = (x - nx * check_dist, y - ny * check_dist)
        p_left = (x + nx * check_dist, y + ny * check_dist)
        line = LineString([p_right, p_left])

        intersection = self.drivable_area.intersection(line)

        if intersection.is_empty:
            return None

        # Intersection might be MultiLineString if road loops or is complex
        # We want the segment containing P.
        # Simplification: return the length of the intersection
        # This assumes we are on a single road segment and not crossing gaps.
        return intersection.length
