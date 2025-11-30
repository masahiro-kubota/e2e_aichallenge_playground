import json
import logging
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TypedDict

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class Point(TypedDict):
    x: float
    y: float


class MapLine(TypedDict):
    points: list[Point]


def parse_osm(osm_path: str) -> list[MapLine]:
    """
    Parses an OSM file to extract lane geometries using local_x and local_y tags.
    Returns a list of lines (ways), where each line is a list of points.
    """
    try:
        tree = ET.parse(osm_path)
        root = tree.getroot()

        nodes: dict[str, Point] = {}
        lines: list[MapLine] = []

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
                    local_x = float(v)
                elif k == "local_y":
                    local_y = float(v)

            if local_x is not None and local_y is not None:
                nodes[node_id] = {"x": local_x, "y": local_y}

        # Second pass: Extract ways (lines)
        for way in root.findall("way"):
            line_points: list[Point] = []

            for nd in way.findall("nd"):
                ref = nd.get("ref")
                if ref in nodes:
                    line_points.append(nodes[ref])

            if len(line_points) > 1:
                lines.append({"points": line_points})

        logger.info("Parsed %d lines from OSM file.", len(lines))

    except Exception:
        logger.exception("Error parsing OSM file")
        return []
    else:
        return lines


def inject_data(
    html_path: str, json_path: str, output_path: str, osm_path: str | None = None
) -> None:
    """
    Injects JSON data into the HTML file by replacing the placeholder.
    Optionally merges OSM map data into the JSON payload.
    """
    try:
        html_content = Path(html_path).read_text(encoding="utf-8")
        json_content = Path(json_path).read_text(encoding="utf-8")

        # Verify JSON validity and load it
        data = json.loads(json_content)

        # Inject OSM data if provided
        if osm_path:
            logger.info("Parsing OSM file: %s", osm_path)
            map_lines = parse_osm(osm_path)
            data["map_lines"] = map_lines

        # Serialize back to JSON string
        final_json_content = json.dumps(data)

        injection_marker = "window.SIMULATION_DATA = null;"
        replacement = f"window.SIMULATION_DATA = {final_json_content};"

        if injection_marker not in html_content:
            logger.error("Error: Marker '%s' not found in %s", injection_marker, html_path)
            sys.exit(1)

        new_html_content = html_content.replace(injection_marker, replacement)

        Path(output_path).write_text(new_html_content, encoding="utf-8")
        logger.info("Successfully injected data from %s into %s", json_path, output_path)

    except Exception:
        logger.exception("Error injecting data")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 4 or len(sys.argv) > 6:
        logger.error(
            "Usage: python inject_data.py <html_path> <json_path> "
            "<output_path> [--osm-path <osm_path>]"
        )
        sys.exit(1)

    html_path = sys.argv[1]
    json_path = sys.argv[2]
    output_path = sys.argv[3]
    osm_path = None

    if len(sys.argv) == 6 and sys.argv[4] == "--osm-path":
        osm_path = sys.argv[5]

    inject_data(html_path, json_path, output_path, osm_path)
