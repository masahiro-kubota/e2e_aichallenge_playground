"""Lanelet2 OSM file parser utilities.

This module provides common utilities for parsing Lanelet2 OSM files,
used by both simulator (for collision detection) and dashboard (for visualization).
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TypedDict

from shapely.geometry import Polygon
from shapely.ops import unary_union


class Point(TypedDict):
    """2D point coordinates."""

    x: float
    y: float


class MapLine(TypedDict):
    """Map line consisting of multiple points."""

    points: list[Point]


class MapPolygon(TypedDict):
    """Map polygon consisting of points."""

    points: list[Point]


class OSMData(TypedDict):
    """Parsed OSM data structure."""

    nodes: dict[int, tuple[float, float]]
    ways: dict[int, list[int]]
    lanelets: list[tuple[list[int], list[int]]]  # (left_nodes, right_nodes)


def parse_osm_file(osm_path: Path) -> OSMData:
    """Parse OSM file and extract nodes, ways, and lanelets.

    Args:
        osm_path: Path to the .osm file

    Returns:
        Dictionary containing nodes, ways, and lanelets

    Raises:
        FileNotFoundError: If OSM file does not exist
        ET.ParseError: If OSM file is malformed
    """
    if not osm_path.exists():
        msg = f"OSM file not found: {osm_path}"
        raise FileNotFoundError(msg)

    tree = ET.parse(osm_path)
    root = tree.getroot()

    nodes: dict[int, tuple[float, float]] = {}
    ways: dict[int, list[int]] = {}
    lanelets: list[tuple[list[int], list[int]]] = []

    # Parse nodes
    for node in root.findall("node"):
        node_id = int(node.get("id", 0))
        local_x = 0.0
        local_y = 0.0

        for tag in node.findall("tag"):
            if tag.get("k") == "local_x":
                local_x = float(tag.get("v", 0.0))
            elif tag.get("k") == "local_y":
                local_y = float(tag.get("v", 0.0))

        nodes[node_id] = (local_x, local_y)

    # Parse ways
    for way in root.findall("way"):
        way_id = int(way.get("id", 0))
        nd_refs = [int(nd.get("ref", 0)) for nd in way.findall("nd")]
        ways[way_id] = nd_refs

    # Parse relations (lanelets)
    for relation in root.findall("relation"):
        is_lanelet = False
        left_way_id = None
        right_way_id = None

        for tag in relation.findall("tag"):
            if tag.get("k") == "type" and tag.get("v") == "lanelet":
                is_lanelet = True

        if not is_lanelet:
            continue

        for member in relation.findall("member"):
            role = member.get("role")
            ref = int(member.get("ref", 0))
            if role == "left":
                left_way_id = ref
            elif role == "right":
                right_way_id = ref

        if left_way_id and right_way_id and left_way_id in ways and right_way_id in ways:
            left_nodes = ways[left_way_id]
            right_nodes = ways[right_way_id]
            lanelets.append((left_nodes, right_nodes))

    return {"nodes": nodes, "ways": ways, "lanelets": lanelets}


def parse_osm_for_collision(osm_path: Path) -> Polygon | None:
    """Parse OSM file and create a unified drivable area polygon for collision detection.

    Args:
        osm_path: Path to the .osm file

    Returns:
        Shapely Polygon representing the drivable area, or None if parsing fails
    """
    try:
        osm_data = parse_osm_file(osm_path)
        nodes = osm_data["nodes"]
        lanelets = osm_data["lanelets"]

        polygons: list[Polygon] = []

        for left_nodes, right_nodes in lanelets:
            # Create polygon from left and right boundaries
            # Left boundary points (forward)
            polygon_points = [nodes[nid] for nid in left_nodes if nid in nodes]
            # Right boundary points (reverse to close loop)
            polygon_points.extend([nodes[nid] for nid in reversed(right_nodes) if nid in nodes])

            if len(polygon_points) >= 3:
                polygons.append(Polygon(polygon_points))

        # Merge all lanelets into a single drivable area
        if polygons:
            return unary_union(polygons)

        return None

    except Exception:
        return None


def parse_osm_for_visualization(osm_path: Path) -> tuple[list[MapLine], list[MapPolygon]]:
    """Parse OSM file and extract geometries for dashboard visualization.

    Args:
        osm_path: Path to OSM file

    Returns:
        Tuple containing list of map lines and list of map polygons
    """
    try:
        osm_data = parse_osm_file(osm_path)
        nodes = osm_data["nodes"]
        ways = osm_data["ways"]
        lanelets = osm_data["lanelets"]

        lines: list[MapLine] = []
        polygons: list[MapPolygon] = []

        # Convert ways to lines
        for way_nodes in ways.values():
            line_points: list[Point] = []
            for node_id in way_nodes:
                if node_id in nodes:
                    x, y = nodes[node_id]
                    line_points.append({"x": x, "y": y})

            if len(line_points) > 1:
                lines.append({"points": line_points})

        # Convert lanelets to polygons
        for left_nodes, right_nodes in lanelets:
            left_points: list[Point] = []
            right_points: list[Point] = []

            for node_id in left_nodes:
                if node_id in nodes:
                    x, y = nodes[node_id]
                    left_points.append({"x": x, "y": y})

            for node_id in right_nodes:
                if node_id in nodes:
                    x, y = nodes[node_id]
                    right_points.append({"x": x, "y": y})

            if left_points and right_points:
                # Construct polygon: left points + reversed right points
                polygon_points = left_points + list(reversed(right_points))

                # Close the loop if not already closed
                if polygon_points[0] != polygon_points[-1]:
                    polygon_points.append(polygon_points[0])

                polygons.append({"points": polygon_points})

        return lines, polygons

    except Exception:
        return [], []


__all__ = [
    "MapLine",
    "MapPolygon",
    "OSMData",
    "Point",
    "parse_osm_file",
    "parse_osm_for_collision",
    "parse_osm_for_visualization",
]
