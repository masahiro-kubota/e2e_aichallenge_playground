#!/usr/bin/env python3
"""Analyze steering_status messages from MCAP file."""

import json

import numpy as np
from mcap.reader import make_reader

mcap_path = "/home/masa/python-self-driving-simulator/outputs/2025-12-30/16-44-37/train/raw_data/episode_seed42/simulation.mcap"

with open(mcap_path, "rb") as f:
    reader = make_reader(f)

    steering_angles = []
    control_angles = []

    for schema, channel, message in reader.iter_messages(
        topics=["/vehicle/status/steering_status", "/control/command/control_cmd"]
    ):
        if channel.topic == "/vehicle/status/steering_status":
            data = json.loads(message.data)
            steering_angles.append(data.get("steering_tire_angle", 0.0))
        elif channel.topic == "/control/command/control_cmd":
            data = json.loads(message.data)
            control_angles.append(data.get("lateral", {}).get("steering_tire_angle", 0.0))

    print("=" * 80)
    print("STEERING STATUS ANALYSIS")
    print("=" * 80)

    if steering_angles:
        steering_arr = np.array(steering_angles)
        print(f"\nTotal messages: {len(steering_angles)}")
        print(
            f"Min value:  {np.min(steering_arr):.6f} rad ({np.degrees(np.min(steering_arr)):.3f}°)"
        )
        print(
            f"Max value:  {np.max(steering_arr):.6f} rad ({np.degrees(np.max(steering_arr)):.3f}°)"
        )
        print(
            f"Mean value: {np.mean(steering_arr):.6f} rad ({np.degrees(np.mean(steering_arr)):.3f}°)"
        )
        print(
            f"Std dev:    {np.std(steering_arr):.6f} rad ({np.degrees(np.std(steering_arr)):.3f}°)"
        )
        print(
            f"Range:      {np.ptp(steering_arr):.6f} rad ({np.degrees(np.ptp(steering_arr)):.3f}°)"
        )

        # Check if values are changing
        unique_values = len(np.unique(steering_arr))
        print(f"\nUnique values: {unique_values} out of {len(steering_angles)}")

        # Check for consecutive duplicates
        changes = np.diff(steering_arr) != 0
        num_changes = np.sum(changes)
        print(f"Number of changes: {num_changes}")
        print(f"Change rate: {num_changes / len(steering_angles) * 100:.1f}%")

    print("\n" + "=" * 80)
    print("CONTROL CMD ANALYSIS")
    print("=" * 80)

    if control_angles:
        control_arr = np.array(control_angles)
        print(f"\nTotal messages: {len(control_angles)}")
        print(f"Min value:  {np.min(control_arr):.6f} rad ({np.degrees(np.min(control_arr)):.3f}°)")
        print(f"Max value:  {np.max(control_arr):.6f} rad ({np.degrees(np.max(control_arr)):.3f}°)")
        print(
            f"Mean value: {np.mean(control_arr):.6f} rad ({np.degrees(np.mean(control_arr)):.3f}°)"
        )
        print(f"Std dev:    {np.std(control_arr):.6f} rad ({np.degrees(np.std(control_arr)):.3f}°)")
        print(f"Range:      {np.ptp(control_arr):.6f} rad ({np.degrees(np.ptp(control_arr)):.3f}°)")

        unique_values = len(np.unique(control_arr))
        print(f"\nUnique values: {unique_values} out of {len(control_angles)}")

        changes = np.diff(control_arr) != 0
        num_changes = np.sum(changes)
        print(f"Number of changes: {num_changes}")
        print(f"Change rate: {num_changes / len(control_angles) * 100:.1f}%")

    print("\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)

    if steering_angles and control_angles:
        print(f"\nsteering_status range: {np.degrees(np.ptp(steering_arr)):.3f}°")
        print(f"control_cmd range:     {np.degrees(np.ptp(control_arr)):.3f}°")
        print(
            f"\nRatio (steering/control): {np.ptp(steering_arr) / np.ptp(control_arr) * 100:.1f}%"
        )
