#!/usr/bin/env python3
import sys
import yaml
import math
from pathlib import Path
from core.data import VehicleParameters, VehicleState
from core.data.autoware import AckermannControlCommand, AckermannLateralCommand, LongitudinalCommand
from core.utils.ros_message_builder import to_ros_time
from simulator.simulator import SimulatorNode, SimulatorConfig

from core.data import TopicSlot

def main():
    # Load config
    config_path = Path("experiment/conf/vehicle/default.yaml")
    with open(config_path) as f:
        vehicle_config = yaml.safe_load(f)
    
    # Create VehicleParameters
    params = VehicleParameters(**vehicle_config)
    
    # Create SimulatorConfig
    initial_state = VehicleState(x=0.0, y=0.0, yaw=0.0, velocity=0.0)
    sim_config = SimulatorConfig(
        vehicle_params=params,
        initial_state=initial_state,
        map_path=Path("experiment/assets/lanelet2_map.osm"),
        obstacle_color="#FF0000",
        topic_rates={} 
    )
    
    # Init Node
    node = SimulatorNode(config=sim_config, rate_hz=100.0, priority=10)
    node.on_init()
    
    print("Simulator Initialized.")
    print("Simulator Initialized.")
    print(f"Params:")
    print(f"  Gain={params.steer_gain}")
    print(f"  Delay={params.steer_delay_time}")
    print(f"  Omega={params.steer_omega_n}")
    print(f"  Zeta={params.steer_zeta}")
    print(f"  MaxRate={params.max_steer_rate}")
    
    # Simulation Loop
    target_steering = -0.2 # rad
    steps = 100 # 1.0 sec
    
    print("\nStarting Simulation (Target Steering = -0.2 rad)...")
    print("Time[s] | Command[rad] | Actual[rad] | Internal[rad/s]")
    print("-" * 50)
    
    for i in range(steps):
        t = i * 0.01
        
        # Create Command
        stamp = to_ros_time(t)
        cmd = AckermannControlCommand(
            stamp=stamp,
            lateral=AckermannLateralCommand(stamp=stamp, steering_tire_angle=target_steering),
            longitudinal=LongitudinalCommand(stamp=stamp, acceleration=0.0, speed=0.0)
        )
        
    # Create FrameData mock with real TopicSlot
    class MockFrameData:
        def __init__(self):
            # Inputs
            self.control_cmd = TopicSlot()
            self.termination_signal = TopicSlot(None)
            
            # Outputs
            self.sim_state = TopicSlot()
            self.obstacles = TopicSlot()
            self.obstacle_states = TopicSlot()
            self.obstacle_markers = TopicSlot()
            self.perception_lidar_scan = TopicSlot()
            self.steering_status = TopicSlot()
            
    mock_frame = MockFrameData()
    node.set_frame_data(mock_frame)
    
    print("\nStarting Simulation (Target Steering = -0.2 rad)...")
    print("Time[s] | Command[rad] | Actual[rad] | Internal[rad/s]")
    print("-" * 50)
    
    for i in range(steps):
        t = i * 0.01
        
        # Create Command
        stamp = to_ros_time(t)
        cmd = AckermannControlCommand(
            stamp=stamp,
            lateral=AckermannLateralCommand(stamp=stamp, steering_tire_angle=target_steering),
            longitudinal=LongitudinalCommand(stamp=stamp, acceleration=0.0, speed=0.0)
        )
        
        # Inject Command via FrameData
        mock_frame.control_cmd.update(cmd)
        
        node.on_run(t)
        
        # Retrieve state
        current_steering = node._current_state.actual_steering
        internal_rate = node._current_state.steer_rate_internal
        
        print(f"{t:5.2f}   | {target_steering:6.3f}       | {current_steering:6.3f}      | {internal_rate:6.3f}")

if __name__ == "__main__":
    main()
