"""Data injection utilities for dashboard generation."""

import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)


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


def parse_osm(osm_path: Path) -> tuple[list[MapLine], list[MapPolygon]]:
    """Parse OSM file to extract lane geometries and polygons.

    Args:
        osm_path: Path to OSM file

    Returns:
        Tuple containing list of map lines and list of map polygons
    """
    try:
        tree = ET.parse(osm_path)
        root = tree.getroot()

        nodes: dict[str, Point] = {}
        ways: dict[str, list[Point]] = {}  # Map way ID to list of points
        lines: list[MapLine] = []
        polygons: list[MapPolygon] = []

        # First pass: Extract all nodes with local coordinates
        for node in root.findall("node"):
            node_id = node.get("id")
            if not node_id:
                continue

            local_x = None
            local_y = None

            for tag in node.findall("tag"):
                k = tag.get("k")
                v = tag.get("v")
                if k == "local_x":
                    local_x = float(v) if v else None
                elif k == "local_y":
                    local_y = float(v) if v else None

            if local_x is not None and local_y is not None:
                nodes[node_id] = {"x": local_x, "y": local_y}

        # Second pass: Extract ways (lines)
        for way in root.findall("way"):
            way_id = way.get("id")
            if not way_id:
                continue

            line_points: list[Point] = []

            for nd in way.findall("nd"):
                ref = nd.get("ref")
                if ref and ref in nodes:
                    line_points.append(nodes[ref])

            if len(line_points) > 1:
                lines.append({"points": line_points})
                ways[way_id] = line_points

        # Third pass: Extract relations (lanelets) to form polygons
        for relation in root.findall("relation"):
            is_lanelet = False
            for tag in relation.findall("tag"):
                if tag.get("k") == "type" and tag.get("v") == "lanelet":
                    is_lanelet = True
                    break

            if not is_lanelet:
                continue

            left_way_id = None
            right_way_id = None

            for member in relation.findall("member"):
                role = member.get("role")
                ref = member.get("ref")
                if role == "left":
                    left_way_id = ref
                elif role == "right":
                    right_way_id = ref

            if left_way_id and right_way_id and left_way_id in ways and right_way_id in ways:
                left_points = ways[left_way_id]
                right_points = ways[right_way_id]

                # Construct polygon: left points + reversed right points
                # Assuming standard lanelet2 direction (left and right are parallel directional boundaries)
                # To form a closed loop: Go along left, then come back along right (reversed)
                polygon_points = left_points + list(reversed(right_points))

                # Close the loop if not already closed (though fill logic often handles open loops,
                # explicit closing is safer for some renderers)
                if polygon_points[0] != polygon_points[-1]:
                    polygon_points.append(polygon_points[0])

                polygons.append({"points": polygon_points})

    except Exception:
        logger.exception("Error parsing OSM file")
        return [], []
    else:
        logger.info("Parsed %d lines and %d polygons from OSM file.", len(lines), len(polygons))
        return lines, polygons


def inject_simulation_data(
    template_path: Path,
    json_data: dict,
    output_path: Path,
    osm_path: Path | None = None,
) -> None:
    """Inject simulation data into HTML template.

    Args:
        template_path: Path to HTML template file
        json_data: Simulation data as dictionary
        output_path: Path to save the generated HTML
        osm_path: Optional path to OSM file for map visualization

    Raises:
        FileNotFoundError: If template file not found
        ValueError: If JSON data is invalid
    """
    if not template_path.exists():
        msg = f"Template file not found: {template_path}"
        raise FileNotFoundError(msg)

    try:
        html_content = template_path.read_text(encoding="utf-8")

        # Inject OSM data if provided
        if osm_path and osm_path.exists():
            logger.info("Parsing OSM file: %s", osm_path)
            map_lines, map_polygons = parse_osm(osm_path)
            json_data["map_lines"] = map_lines
            json_data["map_polygons"] = map_polygons

        # Serialize to JSON string
        json_content = json.dumps(json_data)

        # Use regex to find the marker
        pattern = re.compile(r"window\.SIMULATION_DATA\s*=\s*null;?")

        if not pattern.search(html_content):
            logger.warning(
                "Marker 'window.SIMULATION_DATA = null;' not found in %s",
                template_path,
            )
            # Fallback: inject before </head>
            if "</head>" in html_content:
                logger.info("Attempting fallback injection before </head>")
                injection_script = f"<script>window.SIMULATION_DATA = {json_content};</script>"
                new_html_content = html_content.replace("</head>", f"{injection_script}</head>")
            else:
                msg = "Cannot inject data: no marker or </head> tag found"
                raise ValueError(msg)
        else:
            # Replace the marker with the data
            new_html_content = pattern.sub(
                lambda _: f"window.SIMULATION_DATA = {json_content};",
                html_content,
            )

        output_path.write_text(new_html_content, encoding="utf-8")
        logger.info("Successfully injected data into %s", output_path)

    except Exception as e:
        logger.exception("Error injecting data")
        raise ValueError(f"Failed to inject data: {e}") from e


__all__ = ["inject_simulation_data", "parse_osm"]
