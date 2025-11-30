import json
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def inject_data(html_path: str, json_path: str, output_path: str) -> None:
    """
    Injects JSON data into the HTML file by replacing the placeholder.
    """
    try:
        html_content = Path(html_path).read_text(encoding="utf-8")
        json_content = Path(json_path).read_text(encoding="utf-8")

        # Verify JSON validity
        json.loads(json_content)

        # Prepare the injection string
        # We use json.dumps again to ensure it's a valid JS string literal if needed,
        # but here we want to assign the object directly.
        # However, simply pasting the JSON string might be enough if it's a valid JS object literal.
        # To be safe and handle escaping correctly, we can dump it as a string and parse it,
        # or just assign it if we trust the JSON structure.
        # Let's go with direct assignment of the JSON string which is valid JS object notation.

        injection_marker = "window.SIMULATION_DATA = null;"
        replacement = f"window.SIMULATION_DATA = {json_content};"

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
    if len(sys.argv) != 4:
        logger.error("Usage: python inject_data.py <html_path> <json_path> <output_path>")
        sys.exit(1)

    inject_data(sys.argv[1], sys.argv[2], sys.argv[3])
