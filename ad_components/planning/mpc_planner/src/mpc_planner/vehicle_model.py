"""Vehicle kinematic model for trajectory optimization."""

import casadi as ca
import numpy as np


class KinematicBicycleModel:
    """Kinematic bicycle model for vehicle motion.
    
    State: [x, y, theta, v]
    Control: [a, delta]
    """
    
    def __init__(self, wheelbase: float):
        """Initialize the kinematic model.
        
        Args:
            wheelbase: Distance between front and rear axles [m]
        """
        self.wheelbase = wheelbase
    
    def state_derivative(
        self,
        x: float,
        y: float,
        theta: float,
        v: float,
        a: float,
        delta: float,
    ) -> tuple[float, float, float, float]:
        """Compute state derivatives.
        
        Args:
            x: X position [m]
            y: Y position [m]
            theta: Heading angle [rad]
            v: Velocity [m/s]
            a: Acceleration [m/s^2]
            delta: Steering angle [rad]
            
        Returns:
            Tuple of (dx/dt, dy/dt, dtheta/dt, dv/dt)
        """
        dx_dt = v * ca.cos(theta)
        dy_dt = v * ca.sin(theta)
        dtheta_dt = v * ca.tan(delta) / self.wheelbase
        dv_dt = a
        
        return dx_dt, dy_dt, dtheta_dt, dv_dt
    
    def discretize_euler(
        self,
        x: float,
        y: float,
        theta: float,
        v: float,
        a: float,
        delta: float,
        dt: float,
    ) -> tuple[float, float, float, float]:
        """Discretize using forward Euler method.
        
        Args:
            x: Current X position [m]
            y: Current Y position [m]
            theta: Current heading angle [rad]
            v: Current velocity [m/s]
            a: Acceleration [m/s^2]
            delta: Steering angle [rad]
            dt: Time step [s]
            
        Returns:
            Next state (x_next, y_next, theta_next, v_next)
        """
        dx_dt, dy_dt, dtheta_dt, dv_dt = self.state_derivative(x, y, theta, v, a, delta)
        
        x_next = x + dx_dt * dt
        y_next = y + dy_dt * dt
        theta_next = theta + dtheta_dt * dt
        v_next = v + dv_dt * dt
        
        return x_next, y_next, theta_next, v_next
    
    def discretize_rk4(
        self,
        x: float,
        y: float,
        theta: float,
        v: float,
        a: float,
        delta: float,
        dt: float,
    ) -> tuple[float, float, float, float]:
        """Discretize using RK4 method (more accurate).
        
        Args:
            x: Current X position [m]
            y: Current Y position [m]
            theta: Current heading angle [rad]
            v: Current velocity [m/s]
            a: Acceleration [m/s^2]
            delta: Steering angle [rad]
            dt: Time step [s]
            
        Returns:
            Next state (x_next, y_next, theta_next, v_next)
        """
        # k1
        k1_x, k1_y, k1_theta, k1_v = self.state_derivative(x, y, theta, v, a, delta)
        
        # k2
        k2_x, k2_y, k2_theta, k2_v = self.state_derivative(
            x + 0.5 * dt * k1_x,
            y + 0.5 * dt * k1_y,
            theta + 0.5 * dt * k1_theta,
            v + 0.5 * dt * k1_v,
            a,
            delta,
        )
        
        # k3
        k3_x, k3_y, k3_theta, k3_v = self.state_derivative(
            x + 0.5 * dt * k2_x,
            y + 0.5 * dt * k2_y,
            theta + 0.5 * dt * k2_theta,
            v + 0.5 * dt * k2_v,
            a,
            delta,
        )
        
        # k4
        k4_x, k4_y, k4_theta, k4_v = self.state_derivative(
            x + dt * k3_x,
            y + dt * k3_y,
            theta + dt * k3_theta,
            v + dt * k3_v,
            a,
            delta,
        )
        
        # Combine
        x_next = x + (dt / 6.0) * (k1_x + 2 * k2_x + 2 * k3_x + k4_x)
        y_next = y + (dt / 6.0) * (k1_y + 2 * k2_y + 2 * k3_y + k4_y)
        theta_next = theta + (dt / 6.0) * (k1_theta + 2 * k2_theta + 2 * k3_theta + k4_theta)
        v_next = v + (dt / 6.0) * (k1_v + 2 * k2_v + 2 * k3_v + k4_v)
        
        return x_next, y_next, theta_next, v_next
