#!/usr/bin/env python3
"""Check MCAP file for steering_status topic."""

from mcap.reader import make_reader

mcap_path = "/home/masa/python-self-driving-simulator/outputs/2025-12-30/16-25-16/train/raw_data/episode_seed42/simulation.mcap"

with open(mcap_path, "rb") as f:
    reader = make_reader(f)
    
    print("Topics in MCAP file:")
    print("=" * 80)
    
    for schema_id, schema in reader.get_summary().schemas.items():
        print(f"Schema ID {schema_id}: {schema.name}")
    
    print("\n" + "=" * 80)
    
    for channel_id, channel in reader.get_summary().channels.items():
        schema = reader.get_summary().schemas.get(channel.schema_id)
        schema_name = schema.name if schema else "Unknown"
        print(f"Topic: {channel.topic:50s} | Schema: {schema_name:40s} | Messages: {reader.get_summary().statistics.channel_message_counts.get(channel_id, 0)}")
    
    # Check specifically for steering_status
    print("\n" + "=" * 80)
    steering_topics = [ch for ch in reader.get_summary().channels.values() if "steering" in ch.topic.lower()]
    
    if steering_topics:
        print(f"\n✓ Found {len(steering_topics)} steering-related topic(s):")
        for ch in steering_topics:
            schema = reader.get_summary().schemas.get(ch.schema_id)
            schema_name = schema.name if schema else "Unknown"
            msg_count = reader.get_summary().statistics.channel_message_counts.get(ch.id, 0)
            print(f"  - {ch.topic} ({schema_name}): {msg_count} messages")
    else:
        print("\n✗ No steering-related topics found")
