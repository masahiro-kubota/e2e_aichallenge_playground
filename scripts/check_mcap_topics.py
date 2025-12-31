#!/usr/bin/env python3
"""Check MCAP file for steering_status topic."""

import sys
from mcap.reader import make_reader

if len(sys.argv) > 1:
    mcap_path = sys.argv[1]
else:
    mcap_path = "/home/masa/python-self-driving-simulator/outputs/2025-12-30/16-25-16/train/raw_data/episode_seed42/simulation.mcap"

with open(mcap_path, "rb") as f:
    reader = make_reader(f)
    
    print(f"Inspecting: {mcap_path}")
    print("Topics in MCAP file:")
    print("=" * 80)
    
    for schema_id, schema in reader.get_summary().schemas.items():
        print(f"Schema ID {schema_id}: {schema.name} (Encoding: {schema.encoding})")
    
    print("\n" + "=" * 80)
    
    for channel_id, channel in reader.get_summary().channels.items():
        schema = reader.get_summary().schemas.get(channel.schema_id)
        schema_name = schema.name if schema else "Unknown"
        print(f"Topic: {channel.topic:50s} | Schema: {schema_name:40s} | Messages: {reader.get_summary().statistics.channel_message_counts.get(channel_id, 0)}")
