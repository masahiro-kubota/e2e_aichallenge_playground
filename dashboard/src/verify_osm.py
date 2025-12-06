import sys
from pathlib import Path

sys.path.append("/home/masa/e2e_aichallenge_playground/dashboard/src")

import logging

from dashboard.injector import parse_osm

logging.basicConfig(level=logging.INFO)

osm_path = Path("/home/masa/e2e_aichallenge_playground/dashboard/assets/lanelet2_map.osm")
map_lines, map_polygons = parse_osm(osm_path)

print(f"Extracted {len(map_lines)} map lines")
print(f"Extracted {len(map_polygons)} map polygons")

if len(map_polygons) > 0:
    print("Verification Successful: Polygons extracted.")
else:
    print("Verification Failed: No polygons extracted.")
