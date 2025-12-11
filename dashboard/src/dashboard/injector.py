"""Data injection utilities for dashboard generation."""

import json
import logging
import re
from pathlib import Path

from core.utils.osm_parser import parse_osm_for_visualization

logger = logging.getLogger(__name__)


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
            map_lines, map_polygons = parse_osm_for_visualization(osm_path)
            json_data["map_lines"] = map_lines
            json_data["map_polygons"] = map_polygons

        # Serialize to JSON string
        def _json_serial(obj):
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            if hasattr(obj, "to_dict"):
                return obj.to_dict()
            if hasattr(obj, "dict"):  # Fallback for older Pydantic or other objects
                return obj.dict()
            raise TypeError(f"Type {type(obj)} not serializable")

        json_content = json.dumps(json_data, default=_json_serial)

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


__all__ = ["inject_simulation_data"]
