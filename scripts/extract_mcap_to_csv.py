#!/usr/bin/env python3
# Usage:
#   uv run scripts/extract_mcap_to_csv.py input.mcap /topic/name
#   uv run scripts/extract_mcap_to_csv.py --help
#
# Description:
#   MCAPファイル (ROS2 CDR または JSON 形式) から指定したトピックを抽出し、CSV形式で保存します。

import argparse
import csv
from pathlib import Path
from typing import List, Optional, Any

# Adjust path to find core
from core.utils.mcap_utils import read_messages, msg_to_dict

def flatten(d, parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def extract_topics_to_csv(mcap_path: str, topics: List[str], output_path: Optional[str] = None):
    input_path = Path(mcap_path)
    if not input_path.exists():
        print(f"Error: File not found: {mcap_path}")
        sys.exit(1)

    if not output_path:
        output_path = input_path.with_suffix(".csv")
    
    print(f"Reading {mcap_path}...")
    print(f"Extracting topics: {topics}")
    
    rows = []
    all_keys = set(["timestamp_ns", "log_time_s", "topic"])
    
    count = 0
    try:
        for topic, msg, timestamp_ns in read_messages(mcap_path, topics):
            try:
                # msg can be SimpleNamespace (JSON) or rosbags object (CDR)
                # We need a dict for flattening
                msg_dict = msg_to_dict(msg)
                flat_data = flatten(msg_dict)
                
                row = {
                    "timestamp_ns": timestamp_ns,
                    "log_time_s": timestamp_ns / 1e9,
                    "topic": topic
                }
                row.update(flat_data)
                rows.append(row)
                all_keys.update(flat_data.keys())
                count += 1
            except Exception as e:
                # print(f"Error processing message from {topic}: {e}")
                pass
                
    except Exception as e:
        print(f"Error reading MCAP: {e}")
        return

    if not rows:
        print("No messages extracted.")
        return

    # Sort keys
    header = ["timestamp_ns", "log_time_s", "topic"]
    data_keys = sorted([k for k in all_keys if k not in header])
    header.extend(data_keys)
    
    print(f"Writing {count} rows to {output_path}...")
    try:
        with open(output_path, "w", newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Done. Saved to {output_path}")
    except Exception as e:
        print(f"Error writing CSV: {e}")

def main():
    parser = argparse.ArgumentParser(description="Convert MCAP topics to CSV via rosbags/mcap utils")
    parser.add_argument("input", help="Input MCAP file")
    parser.add_argument("topics", nargs="+", help="Topics to extract")
    parser.add_argument("-o", "--output", help="Output CSV file path")
    
    args = parser.parse_args()
    
    extract_topics_to_csv(args.input, args.topics, args.output)

if __name__ == "__main__":
    main()
