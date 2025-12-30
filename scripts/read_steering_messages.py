#!/usr/bin/env python3
"""Read steering_status messages from MCAP file."""

import json
from mcap.reader import make_reader

mcap_path = "/home/masa/python-self-driving-simulator/outputs/2025-12-30/16-29-06/evaluation/episode_0000/simulation.mcap"

with open(mcap_path, "rb") as f:
    reader = make_reader(f)
    
    steering_messages = []
    control_messages = []
    
    for schema, channel, message in reader.iter_messages(topics=["/vehicle/status/steering_status", "/control/command/control_cmd"]):
        if channel.topic == "/vehicle/status/steering_status":
            data = json.loads(message.data)
            steering_messages.append({
                "time": message.log_time / 1e9,
                "steering_tire_angle": data.get("steering_tire_angle", 0.0)
            })
        elif channel.topic == "/control/command/control_cmd":
            data = json.loads(message.data)
            control_messages.append({
                "time": message.log_time / 1e9,
                "steering_tire_angle": data.get("lateral", {}).get("steering_tire_angle", 0.0)
            })
    
    print(f"Found {len(steering_messages)} steering_status messages")
    print(f"Found {len(control_messages)} control_cmd messages")
    print("\n" + "=" * 80)
    
    if steering_messages:
        print("\nFirst 10 steering_status messages:")
        for i, msg in enumerate(steering_messages[:10]):
            print(f"  {i}: time={msg['time']:.3f}s, steering_tire_angle={msg['steering_tire_angle']:.6f}")
        
        print("\nLast 10 steering_status messages:")
        for i, msg in enumerate(steering_messages[-10:]):
            print(f"  {len(steering_messages)-10+i}: time={msg['time']:.3f}s, steering_tire_angle={msg['steering_tire_angle']:.6f}")
    
    if control_messages:
        print("\n" + "=" * 80)
        print("\nFirst 10 control_cmd messages:")
        for i, msg in enumerate(control_messages[:10]):
            print(f"  {i}: time={msg['time']:.3f}s, steering_tire_angle={msg['steering_tire_angle']:.6f}")
