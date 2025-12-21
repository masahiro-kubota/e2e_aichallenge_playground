import math
from typing import TYPE_CHECKING

from shapely.geometry import LineString, Point
from shapely.ops import nearest_points

from core.data import LidarConfig, LidarScan, VehicleState

if TYPE_CHECKING:
    from simulator.map import LaneletMap
    from simulator.obstacle import ObstacleManager


class LidarSensor:
    """LiDAR sensor simulation."""

    def __init__(
        self,
        config: LidarConfig,
        map_instance: "LaneletMap | None" = None,
        obstacle_manager: "ObstacleManager | None" = None,
    ) -> None:
        """Initialize LiDAR sensor.

        Args:
            config: Lidar configuration
            map_instance: LaneletMap instance for map boundary raycasting
            obstacle_manager: ObstacleManager for obstacle raycasting
        """
        self.config = config
        self.map = map_instance
        self.obstacle_manager = obstacle_manager

        # Precompute angles
        fov_rad = math.radians(self.config.fov)
        if self.config.angle_increment > 0:
            self.increment = self.config.angle_increment
        else:
            self.increment = fov_rad / self.config.num_beams

        self.start_angle = -fov_rad / 2.0

    def scan(self, vehicle_state: VehicleState) -> LidarScan:
        """Perform LiDAR scan.

        Args:
            vehicle_state: Current vehicle state

        Returns:
            LidarScan data
        """
        range_max = self.config.range_max
        sensor_x, sensor_y = self._get_sensor_pose(vehicle_state)
        sensor_point = Point(sensor_x, sensor_y)

        ranges = []

        # Get relevant map boundaries
        map_boundaries = []
        if (
            self.map is not None
            and self.map.drivable_area is not None
            and hasattr(self.map.drivable_area, "boundary")
        ):
            boundary = self.map.drivable_area.boundary
            if boundary.geom_type == "LineString":
                map_boundaries.append(boundary)
            elif boundary.geom_type == "MultiLineString":
                map_boundaries.extend(boundary.geoms)
            elif boundary.geom_type == "LinearRing":
                map_boundaries.append(boundary)

        # Get relevant obstacle polygons (use current time for dynamic ones)
        # Note: Optimization would be to select only nearby obstacles
        obstacle_polygons = []
        if self.obstacle_manager is not None:
            # We need to access get_obstacle_polygon logic
            # Assuming we can get all obstacles
            from simulator.obstacle import get_obstacle_polygon, get_obstacle_state

            for obs in self.obstacle_manager.obstacles:
                try:
                    st = get_obstacle_state(obs, vehicle_state.timestamp)
                    # Simple distance check before polygon creation
                    dist = math.hypot(st.x - sensor_x, st.y - sensor_y)
                    # Rough culling
                    if dist < range_max + 10.0:  # +10 safety margin for size
                        poly = get_obstacle_polygon(obs, st)
                        obstacle_polygons.append(poly)
                except Exception:
                    continue

        for i in range(self.config.num_beams):
            angle = self.start_angle + i * self.increment + vehicle_state.yaw + self.config.yaw

            # Limited ray for intersection check
            ray_end_x = sensor_x + range_max * math.cos(angle)
            ray_end_y = sensor_y + range_max * math.sin(angle)
            ray = LineString([(sensor_x, sensor_y), (ray_end_x, ray_end_y)])

            min_dist = float("inf")
            found_hit = False

            # Check map boundaries
            for boundary in map_boundaries:
                if ray.intersects(boundary):
                    intersection = ray.intersection(boundary)
                    # Intersection can be Point, MultiPoint, or other
                    if intersection.is_empty:
                        continue

                    points = []
                    if intersection.geom_type == "Point":
                        points = [intersection]
                    elif intersection.geom_type == "MultiPoint":
                        points = list(intersection.geoms)
                    elif intersection.geom_type in [
                        "LineString",
                        "MultiLineString",
                        "GeometryCollection",
                    ]:
                        # Complex intersection, take nearest point
                        # Usually boundary and ray intersect at point(s)
                        # Simplify by taking distance to intersection
                        points = [nearest_points(sensor_point, intersection)[1]]

                    for p in points:
                        dist = sensor_point.distance(p)
                        if dist < min_dist:
                            min_dist = dist
                            found_hit = True

            # Check obstacles
            for poly in obstacle_polygons:
                if ray.intersects(poly):
                    intersection = ray.intersection(
                        poly
                    )  # Usually produces a LineString (ray inside) or Point
                    if intersection.is_empty:
                        continue

                    # For a solid polygon, ray enters and exits. We want the first entry point.
                    # intersection of a LineString (Ray) and Polygon is a LineString (segment inside)
                    # or MultiLineString

                    geoms = []
                    if intersection.geom_type == "LineString":
                        geoms = [intersection]
                    elif intersection.geom_type == "MultiLineString":
                        geoms = list(intersection.geoms)
                    elif intersection.geom_type == "Point":  # Touch
                        geoms = [intersection]
                    elif intersection.geom_type == "MultiPoint":
                        geoms = list(intersection.geoms)

                    for geom in geoms:
                        # Get nearest point on the intersection geometry to the sensor
                        p = nearest_points(sensor_point, geom)[1]
                        dist = sensor_point.distance(p)
                        if dist < min_dist:
                            min_dist = dist
                            found_hit = True

            if found_hit and min_dist >= self.config.range_min:
                ranges.append(float(min_dist))
            else:
                ranges.append(float("inf"))

        return LidarScan(timestamp=vehicle_state.timestamp, config=self.config, ranges=ranges)

    def _get_sensor_pose(self, vehicle_state: VehicleState) -> tuple[float, float]:
        """Calculate sensor position in global frame."""
        # Vehicle -> Global rotation
        cos_yaw = math.cos(vehicle_state.yaw)
        sin_yaw = math.sin(vehicle_state.yaw)

        # Rotate sensor offset
        rx = self.config.x * cos_yaw - self.config.y * sin_yaw
        ry = self.config.x * sin_yaw + self.config.y * cos_yaw

        # Global position
        gx = vehicle_state.x + rx
        gy = vehicle_state.y + ry

        return gx, gy
