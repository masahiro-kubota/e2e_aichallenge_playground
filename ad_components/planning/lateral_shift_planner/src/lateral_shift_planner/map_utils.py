from pathlib import Path

import numpy as np
from core.utils.osm_parser import parse_osm_file


class LaneletMap:
    """Helper to calculate road boundaries using Lanelet structure."""

    def __init__(self, map_path: Path):
        """Initialize LaneletMap from OSM file.

        Args:
            map_path: Path to Lanelet2 OSM file
        """
        osm_data = parse_osm_file(map_path)
        self.nodes = osm_data["nodes"]
        self.lanelets = osm_data["lanelets"]

        if not self.lanelets:
            raise ValueError(f"No lanelets found in {map_path}")

        # Pre-calculate centerlines for each lanelet (for nearest neighbor search)
        self.lanelet_centerlines: list[list[tuple[float, float]]] = []
        for left_nodes, right_nodes in self.lanelets:
            centerline = []
            # Calculate centerline as midpoint of left and right bounds
            min_len = min(len(left_nodes), len(right_nodes))
            for i in range(min_len):
                if left_nodes[i] in self.nodes and right_nodes[i] in self.nodes:
                    lx, ly = self.nodes[left_nodes[i]]
                    rx, ry = self.nodes[right_nodes[i]]
                    cx = (lx + rx) / 2.0
                    cy = (ly + ry) / 2.0
                    centerline.append((cx, cy))
            self.lanelet_centerlines.append(centerline)

    def _find_closest_lanelet(self, x: float, y: float) -> int:
        """Find the index of the lanelet closest to the given point.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Index of the closest lanelet
        """
        min_dist = float("inf")
        closest_idx = 0

        for idx, centerline in enumerate(self.lanelet_centerlines):
            if not centerline:
                continue

            # Calculate minimum distance to this lanelet's centerline
            for cx, cy in centerline:
                dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                if dist < min_dist:
                    min_dist = dist
                    closest_idx = idx

        return closest_idx

    def _distance_to_polyline(
        self, x: float, y: float, polyline: list[tuple[float, float]]
    ) -> float:
        """Calculate minimum distance from point to polyline.

        Args:
            x: X coordinate of point
            y: Y coordinate of point
            polyline: List of (x, y) points forming the polyline

        Returns:
            Minimum distance to the polyline
        """
        if len(polyline) < 2:
            if len(polyline) == 1:
                px, py = polyline[0]
                return np.sqrt((x - px) ** 2 + (y - py) ** 2)
            return 0.0

        min_dist = float("inf")

        # Check distance to each line segment
        for i in range(len(polyline) - 1):
            x1, y1 = polyline[i]
            x2, y2 = polyline[i + 1]

            # Vector from segment start to point
            dx = x - x1
            dy = y - y1

            # Vector of the segment
            sx = x2 - x1
            sy = y2 - y1

            # Length squared of segment
            seg_len_sq = sx * sx + sy * sy

            if seg_len_sq < 1e-10:
                # Degenerate segment (point)
                dist = np.sqrt(dx * dx + dy * dy)
            else:
                # Project point onto line
                t = max(0.0, min(1.0, (dx * sx + dy * sy) / seg_len_sq))

                # Closest point on segment
                closest_x = x1 + t * sx
                closest_y = y1 + t * sy

                # Distance to closest point
                dist = np.sqrt((x - closest_x) ** 2 + (y - closest_y) ** 2)

            min_dist = min(min_dist, dist)

        return min_dist

    def get_lateral_width(self, x: float, y: float) -> float | None:
        """Calculate total road width at specified position.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Width [m] or None if calculation fails
        """
        boundaries = self.get_lateral_boundaries(x, y)
        if boundaries is None:
            return None
        left_dist, right_dist = boundaries
        return left_dist + right_dist

    def get_lateral_boundaries(self, x: float, y: float) -> tuple[float, float] | None:
        """Calculate distance to left and right road boundaries at specified position.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            (left_boundary_distance, right_boundary_distance) in meters, or None if calculation fails.
            Distances are measured from the query point to the lanelet boundaries.
        """
        try:
            # Find closest lanelet
            lanelet_idx = self._find_closest_lanelet(x, y)

            # Get left and right boundary nodes
            left_nodes, right_nodes = self.lanelets[lanelet_idx]

            # Convert node IDs to coordinates
            left_bound = [self.nodes[nid] for nid in left_nodes if nid in self.nodes]
            right_bound = [self.nodes[nid] for nid in right_nodes if nid in self.nodes]

            if not left_bound or not right_bound:
                return None

            # Calculate distances
            left_dist = self._distance_to_polyline(x, y, left_bound)
            right_dist = self._distance_to_polyline(x, y, right_bound)

            return (left_dist, right_dist)

        except Exception:
            return None


# Keep old class name for backward compatibility
RoadWidthMap = LaneletMap
