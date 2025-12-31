#!/usr/bin/env python3
"""Plot steering comparison from MCAP file."""

import json
import matplotlib.pyplot as plt
import numpy as np
from mcap.reader import make_reader

mcap_path = "/home/masa/python-self-driving-simulator/outputs/2025-12-30/16-44-37/train/raw_data/episode_seed42/simulation.mcap"
output_path = "/home/masa/.gemini/antigravity/brain/179317ce-cdae-492f-bd3d-d67c462ad0b1/steering_comparison_fixed.png"

with open(mcap_path, "rb") as f:
    reader = make_reader(f)
    
    steering_data = []
    control_data = []
    
    for schema, channel, message in reader.iter_messages(topics=["/vehicle/status/steering_status", "/control/command/control_cmd"]):
        if channel.topic == "/vehicle/status/steering_status":
            data = json.loads(message.data)
            steering_data.append({
                "time": message.log_time / 1e9,
                "angle": data.get("steering_tire_angle", 0.0)
            })
        elif channel.topic == "/control/command/control_cmd":
            data = json.loads(message.data)
            control_data.append({
                "time": message.log_time / 1e9,
                "angle": data.get("lateral", {}).get("steering_tire_angle", 0.0)
            })

# Convert to numpy arrays
steering_times = np.array([d["time"] for d in steering_data])
steering_angles = np.array([d["angle"] for d in steering_data])
control_times = np.array([d["time"] for d in control_data])
control_angles = np.array([d["angle"] for d in control_data])

# Create figure with 2 subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

# Plot 1: Both signals in radians
ax1.plot(control_times, control_angles, 'b-', label='Control Command (目標)', linewidth=2, alpha=0.7)
ax1.plot(steering_times, steering_angles, 'r-', label='Steering Status (実際)', linewidth=2, alpha=0.7)
ax1.set_xlabel('Time [s]', fontsize=12)
ax1.set_ylabel('Steering Angle [rad]', fontsize=12)
ax1.set_title('Steering Angle Comparison (Radians)', fontsize=14, fontweight='bold')
ax1.legend(fontsize=11)
ax1.grid(True, alpha=0.3)

# Plot 2: Both signals in degrees
ax2.plot(control_times, np.degrees(control_angles), 'b-', label='Control Command (目標)', linewidth=2, alpha=0.7)
ax2.plot(steering_times, np.degrees(steering_angles), 'r-', label='Steering Status (実際)', linewidth=2, alpha=0.7)
ax2.set_xlabel('Time [s]', fontsize=12)
ax2.set_ylabel('Steering Angle [deg]', fontsize=12)
ax2.set_title('Steering Angle Comparison (Degrees)', fontsize=14, fontweight='bold')
ax2.legend(fontsize=11)
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"Plot saved to: {output_path}")

# Print statistics
print("\n" + "="*80)
print("STATISTICS")
print("="*80)
print(f"\nControl Command:")
print(f"  Range: {np.degrees(np.ptp(control_angles)):.3f}° ({np.ptp(control_angles):.6f} rad)")
print(f"  Mean:  {np.degrees(np.mean(control_angles)):.3f}° ({np.mean(control_angles):.6f} rad)")
print(f"  Std:   {np.degrees(np.std(control_angles)):.3f}° ({np.std(control_angles):.6f} rad)")

print(f"\nSteering Status:")
print(f"  Range: {np.degrees(np.ptp(steering_angles)):.3f}° ({np.ptp(steering_angles):.6f} rad)")
print(f"  Mean:  {np.degrees(np.mean(steering_angles)):.3f}° ({np.mean(steering_angles):.6f} rad)")
print(f"  Std:   {np.degrees(np.std(steering_angles)):.3f}° ({np.std(steering_angles):.6f} rad)")

print(f"\nRatio (Steering/Control):")
print(f"  Range ratio: {np.ptp(steering_angles) / np.ptp(control_angles) * 100:.1f}%")
print(f"  Expected (steer_gain): 70%")
print(f"  Note: Lower ratio is expected due to delay and rate limiting")
