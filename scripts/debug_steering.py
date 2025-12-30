#!/usr/bin/env python3
"""Read first few messages to debug steering values."""

import json
from mcap.reader import make_reader

mcap_path = "/home/masa/python-self-driving-simulator/outputs/2025-12-30/16-34-37/train/raw_data/episode_seed42/simulation.mcap"

with open(mcap_path, "rb") as f:
    reader = make_reader(f)
    
    steering_messages = []
    control_messages = []
    
    for schema, channel, message in reader.iter_messages(topics=["/vehicle/status/steering_status", "/control/command/control_cmd"]):
        if channel.topic == "/vehicle/status/steering_status" and len(steering_messages) < 50:
            data = json.loads(message.data)
            steering_messages.append({
                "time": message.log_time / 1e9,
                "steering_tire_angle": data.get("steering_tire_angle", 0.0)
            })
        elif channel.topic == "/control/command/control_cmd" and len(control_messages) < 50:
            data = json.loads(message.data)
            control_messages.append({
                "time": message.log_time / 1e9,
                "steering_tire_angle": data.get("lateral", {}).get("steering_tire_angle", 0.0)
            })
    
    print("First 30 messages comparison:")
    print("=" * 100)
    print(f"{'Index':<6} {'Time':<10} {'Control CMD (rad)':<20} {'Control CMD (deg)':<20} {'Steering Status (rad)':<22} {'Steering Status (deg)':<22} {'Ratio':<10}")
    print("=" * 100)
    
    # Merge by time
    all_times = sorted(set([m['time'] for m in steering_messages] + [m['time'] for m in control_messages]))
    
    for i, t in enumerate(all_times[:30]):
        control_val = next((m['steering_tire_angle'] for m in control_messages if abs(m['time'] - t) < 0.001), None)
        steering_val = next((m['steering_tire_angle'] for m in steering_messages if abs(m['time'] - t) < 0.001), None)
        
        if control_val is not None and steering_val is not None:
            import math
            ratio = (steering_val / control_val * 100) if control_val != 0 else 0
            print(f"{i:<6} {t:<10.3f} {control_val:<20.6f} {math.degrees(control_val):<20.3f} {steering_val:<22.6f} {math.degrees(steering_val):<22.3f} {ratio:<10.1f}%")
        elif control_val is not None:
            import math
            print(f"{i:<6} {t:<10.3f} {control_val:<20.6f} {math.degrees(control_val):<20.3f} {'N/A':<22} {'N/A':<22} {'N/A':<10}")
        elif steering_val is not None:
            import math
            print(f"{i:<6} {t:<10.3f} {'N/A':<20} {'N/A':<20} {steering_val:<22.6f} {math.degrees(steering_val):<22.3f} {'N/A':<10}")
