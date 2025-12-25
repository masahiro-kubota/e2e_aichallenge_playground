"""Collision detection and avoidance for trajectory optimization."""

import casadi as ca
import numpy as np
from numpy.typing import NDArray


class CollisionChecker:
    """Collision checking utilities for MPC trajectory optimization."""
    
    def __init__(self, vehicle_width: float, vehicle_length: float, safety_margin: float):
        """Initialize collision checker.
        
        Args:
            vehicle_width: Width of the vehicle [m]
            vehicle_length: Length of the vehicle [m]
            safety_margin: Additional safety margin [m]
        """
        self.vehicle_width = vehicle_width
        self.vehicle_length = vehicle_length
        self.safety_margin = safety_margin
    
    def compute_vehicle_corners(
        self,
        x: float,
        y: float,
        theta: float,
    ) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]:
        """Compute the four corners of the vehicle.
        
        Args:
            x: Vehicle center X position [m]
            y: Vehicle center Y position [m]
            theta: Vehicle heading [rad]
            
        Returns:
            Tuple of 4 corners: (front_left, front_right, rear_left, rear_right)
            Each corner is (x, y)
        """
        half_length = self.vehicle_length / 2.0
        half_width = self.vehicle_width / 2.0
        
        cos_theta = ca.cos(theta)
        sin_theta = ca.sin(theta)
        
        # Front left
        fl_x = x + half_length * cos_theta - half_width * sin_theta
        fl_y = y + half_length * sin_theta + half_width * cos_theta
        
        # Front right
        fr_x = x + half_length * cos_theta + half_width * sin_theta
        fr_y = y + half_length * sin_theta - half_width * cos_theta
        
        # Rear left
        rl_x = x - half_length * cos_theta - half_width * sin_theta
        rl_y = y - half_length * sin_theta + half_width * cos_theta
        
        # Rear right
        rr_x = x - half_length * cos_theta + half_width * sin_theta
        rr_y = y - half_length * sin_theta - half_width * cos_theta
        
        return (fl_x, fl_y), (fr_x, fr_y), (rl_x, rl_y), (rr_x, rr_y)
    
    def point_to_rectangle_distance(
        self,
        px: float,
        py: float,
        rect_x: float,
        rect_y: float,
        rect_theta: float,
        rect_width: float,
        rect_length: float,
    ) -> float:
        """Compute distance from a point to a rectangle.
        
        This computes the signed distance from a point to the closest edge of a rectangle.
        Positive distance means the point is outside the rectangle.
        
        Args:
            px: Point X coordinate [m]
            py: Point Y coordinate [m]
            rect_x: Rectangle center X [m]
            rect_y: Rectangle center Y [m]
            rect_theta: Rectangle heading [rad]
            rect_width: Rectangle width [m]
            rect_length: Rectangle length [m]
            
        Returns:
            Distance from point to rectangle [m] (positive if outside)
        """
        # Transform point to rectangle's local frame
        cos_theta = ca.cos(rect_theta)
        sin_theta = ca.sin(rect_theta)
        
        dx = px - rect_x
        dy = py - rect_y
        
        # Rotate to rectangle's frame
        local_x = dx * cos_theta + dy * sin_theta
        local_y = -dx * sin_theta + dy * cos_theta
        
        # Half dimensions
        half_length = rect_length / 2.0
        half_width = rect_width / 2.0
        
        # Distance to each edge (in local frame)
        # For a rectangle aligned with axes, distance is max of distances to edges
        dx_edge = ca.fabs(local_x) - half_length
        dy_edge = ca.fabs(local_y) - half_width
        
        # If both are negative, point is inside
        # Distance is the maximum of the two (closest to zero)
        inside_distance = ca.fmax(dx_edge, dy_edge)
        
        # If at least one is positive, point is outside
        # Distance is Euclidean distance to nearest corner/edge
        outside_distance = ca.sqrt(
            ca.fmax(dx_edge, 0.0)**2 + ca.fmax(dy_edge, 0.0)**2
        )
        
        # Use smooth approximation: if inside, use inside_distance, else outside_distance
        # We use a smooth max to make this differentiable
        distance = ca.if_else(
            ca.logic_and(dx_edge <= 0, dy_edge <= 0),
            inside_distance,
            outside_distance
        )
        
        return distance
    
    def four_corners_distance(
        self,
        vehicle_x: float,
        vehicle_y: float,
        vehicle_theta: float,
        obstacle_x: float,
        obstacle_y: float,
        obstacle_theta: float,
        obstacle_width: float,
        obstacle_length: float,
    ) -> float:
        """Compute minimum distance from vehicle corners to obstacle.
        
        This is the main collision avoidance method (Option 2).
        
        Args:
            vehicle_x: Vehicle center X [m]
            vehicle_y: Vehicle center Y [m]
            vehicle_theta: Vehicle heading [rad]
            obstacle_x: Obstacle center X [m]
            obstacle_y: Obstacle center Y [m]
            obstacle_theta: Obstacle heading [rad]
            obstacle_width: Obstacle width [m]
            obstacle_length: Obstacle length [m]
            
        Returns:
            Minimum distance from any vehicle corner to obstacle [m]
        """
        corners = self.compute_vehicle_corners(vehicle_x, vehicle_y, vehicle_theta)
        
        # Compute distance from each corner to obstacle
        distances = []
        for corner_x, corner_y in corners:
            dist = self.point_to_rectangle_distance(
                corner_x, corner_y,
                obstacle_x, obstacle_y, obstacle_theta,
                obstacle_width, obstacle_length
            )
            distances.append(dist)
        
        # Return minimum distance (most critical)
        min_distance = distances[0]
        for dist in distances[1:]:
            min_distance = ca.fmin(min_distance, dist)
        
        return min_distance
    
    def circle_approximation_distance(
        self,
        vehicle_x: float,
        vehicle_y: float,
        obstacle_x: float,
        obstacle_y: float,
        obstacle_width: float,
        obstacle_length: float,
    ) -> float:
        """Compute distance using circle approximation (Option 1).
        
        This is a conservative approximation for comparison/fallback.
        
        Args:
            vehicle_x: Vehicle center X [m]
            vehicle_y: Vehicle center Y [m]
            obstacle_x: Obstacle center X [m]
            obstacle_y: Obstacle center Y [m]
            obstacle_width: Obstacle width [m]
            obstacle_length: Obstacle length [m]
            
        Returns:
            Distance between circle boundaries [m]
        """
        # Compute bounding circle radii
        vehicle_radius = ca.sqrt(
            (self.vehicle_length / 2.0)**2 + (self.vehicle_width / 2.0)**2
        )
        obstacle_radius = ca.sqrt(
            (obstacle_length / 2.0)**2 + (obstacle_width / 2.0)**2
        )
        
        # Center-to-center distance
        center_distance = ca.sqrt((vehicle_x - obstacle_x)**2 + (vehicle_y - obstacle_y)**2)
        
        # Distance between circle boundaries
        return center_distance - vehicle_radius - obstacle_radius
    
    def multi_circle_distance(
        self,
        vehicle_x: float,
        vehicle_y: float,
        vehicle_theta: float,
        obstacle_x: float,
        obstacle_y: float,
        obstacle_theta: float,
        obstacle_width: float,
        obstacle_length: float,
    ) -> float:
        """Compute distance using multiple circles along rectangle length.
        
        Approximates a rectangle with multiple circles of diameter = width,
        placed along the length axis. This is more accurate than single circle
        approximation while being faster than four-corners method.
        
        Args:
            vehicle_x: Vehicle center X [m]
            vehicle_y: Vehicle center Y [m]
            vehicle_theta: Vehicle heading [rad]
            obstacle_x: Obstacle center X [m]
            obstacle_y: Obstacle center Y [m]
            obstacle_theta: Obstacle heading [rad]
            obstacle_width: Obstacle width [m]
            obstacle_length: Obstacle length [m]
            
        Returns:
            Minimum distance to any circle [m]
        """
        # Vehicle radius (single circle approximation for vehicle)
        vehicle_radius = self.vehicle_width / 2.0
        
        # Obstacle: multiple circles along length
        circle_radius = obstacle_width / 2.0
        
        # Use fixed number of circles (3) for CasADi compatibility
        # This covers: front, center, rear of the rectangle
        num_circles = 3
        
        # Circle positions along obstacle's length axis
        # -length/2 (rear), 0 (center), +length/2 (front)
        offsets = [-obstacle_length / 2.0, 0.0, obstacle_length / 2.0]
        
        # Compute minimum distance to all circles
        min_distance = 1e6  # Large initial value
        
        for offset in offsets:
            # Circle center in global frame
            circle_x = obstacle_x + offset * ca.cos(obstacle_theta)
            circle_y = obstacle_y + offset * ca.sin(obstacle_theta)
            
            # Distance between vehicle center and this circle center
            center_dist = ca.sqrt(
                (vehicle_x - circle_x)**2 + (vehicle_y - circle_y)**2
            )
            
            # Distance between boundaries
            boundary_dist = center_dist - vehicle_radius - circle_radius
            
            # Track minimum
            min_distance = ca.fmin(min_distance, boundary_dist)
        
        return min_distance
