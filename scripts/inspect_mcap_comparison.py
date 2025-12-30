
import json
import numpy as np
from pathlib import Path
from rosbags.highlevel import AnyReader
from mcap.reader import make_reader

def analyze_ranges(ranges, max_range=30.0):
    ranges = np.array(ranges)
    total = ranges.size
    nans = np.isnan(ranges).sum()
    infs = np.isinf(ranges).sum()
    zeros = (ranges == 0.0).sum()
    max_range_hits = (ranges >= max_range - 0.1).sum()
    
    # Valid ranges for stat calculation
    valid_mask = (~np.isnan(ranges)) & (~np.isinf(ranges)) & (ranges > 0.05) & (ranges < max_range - 0.1)
    valid = ranges[valid_mask]
    
    return {
        "shape": ranges.shape,
        "nans": nans,
        "infs": infs,
        "zeros": zeros,
        "max_range_hits": max_range_hits,
        "valid_count": valid.size,
        "valid_min": valid.min() if valid.size > 0 else None,
        "valid_max": valid.max() if valid.size > 0 else None,
        "valid_mean": valid.mean() if valid.size > 0 else None,
        "sample_center_20": ranges[len(ranges)//2-10 : len(ranges)//2+10].tolist()
    }

def print_stats(stats, max_r):
    print("\n--- Range Statistics ---")
    print(f"Shape: {stats['shape']}")
    print(f"NaNs: {stats['nans']}")
    print(f"Infs: {stats['infs']}")
    print(f"Zeros: {stats['zeros']}")
    print(f"Max Range Hits (>= {max_r-0.1}): {stats['max_range_hits']}")
    print(f"Valid Returns: {stats['valid_count']} / {stats['shape'][0]}")
    if stats['valid_count'] > 0:
            print(f"Valid Min: {stats['valid_min']:.4f}")
            print(f"Valid Max: {stats['valid_max']:.4f}")
            print(f"Valid Mean: {stats['valid_mean']:.4f}")
    
    print(f"\nCenter 20 beams sample:\n{np.array(stats['sample_center_20'])}")

def inspect_ros2(path):
    print(f"\n{'='*20} ROS2 Data (rosbags) {'='*20}")
    if not Path(path).exists():
        print("File not found.")
        return
    try:
        with AnyReader([Path(path)]) as reader:
            connections = [x for x in reader.connections if 'scan' in x.topic]
            if not connections:
                print("No scan topic found.")
                return

            conn = connections[0]
            print(f"Topic: {conn.topic}, Type: {conn.msgtype}")
            
            for _, _, raw in reader.messages(connections=[conn]):
                msg = reader.deserialize(raw, conn.msgtype)
                print(f"Frame ID: '{msg.header.frame_id}'")
                print(f"Angle Min: {msg.angle_min:.6f} rad")
                print(f"Angle Max: {msg.angle_max:.6f} rad")
                print(f"Angle Inc: {msg.angle_increment:.6f} rad")
                print(f"Range Min: {msg.range_min:.4f}")
                print(f"Range Max: {msg.range_max:.4f}")
                
                stats = analyze_ranges(msg.ranges, msg.range_max)
                print_stats(stats, msg.range_max)
                break
    except Exception as e:
        print(f"Error inspecting ROS2: {e}")

def inspect_json(path):
    print(f"\n{'='*20} Sim Data (JSON MCAP) {'='*20}")
    if not Path(path).exists():
        print("File not found.")
        return
    try:
        with open(path, "rb") as f:
            reader = make_reader(f)
            scan_topic_found = False
            
            for schema, channel, message in reader.iter_messages():
                if "scan" in channel.topic:
                    scan_topic_found = True
                    print(f"Topic: {channel.topic}, Encoding: {channel.message_encoding}")
                    data = json.loads(message.data)
                    
                    frame_id = data.get("header", {}).get("frame_id", "unknown")
                    angle_min = data.get("angle_min", 0.0)
                    angle_max = data.get("angle_max", 0.0)
                    angle_inc = data.get("angle_increment", 0.0)
                    range_min = data.get("range_min", 0.0)
                    range_max = data.get("range_max", 30.0)
                    ranges = data.get("ranges", [])
                    
                    print(f"Frame ID: '{frame_id}'")
                    print(f"Angle Min: {angle_min:.6f} rad")
                    print(f"Angle Max: {angle_max:.6f} rad")
                    print(f"Angle Inc: {angle_inc:.6f} rad")
                    print(f"Range Min: {range_min:.4f}")
                    print(f"Range Max: {range_max:.4f}")
                    
                    stats = analyze_ranges(ranges, range_max)
                    print_stats(stats, range_max)
                    break
            
            if not scan_topic_found:
                print("No scan topic found.")

    except Exception as e:
        print(f"Error inspecting JSON: {e}")

if __name__ == "__main__":
    inspect_ros2("rosbag2_autoware_0.mcap")
    inspect_json("outputs/2025-12-30/00-55-17/75/train/raw_data/episode_seed75/simulation.mcap")
