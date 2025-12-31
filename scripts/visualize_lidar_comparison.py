import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from mcap.reader import make_reader
from rosbags.highlevel import AnyReader


def load_and_infer_tinylidarnet(ranges: np.ndarray, model_path: Path, max_range: float = 30.0) -> tuple[float, float]:
    """Load TinyLidarNet model and perform actual inference.
    
    Args:
        ranges: Raw LiDAR ranges array
        model_path: Path to .npy model weights file
        max_range: Maximum range for normalization
        
    Returns:
        (acceleration, steering) predictions
    """
    # Import TinyLidarNet NumPy implementation
    import sys
    sys.path.insert(0, '/home/masa/python-self-driving-simulator/ad_components/control/tiny_lidar_net/src')
    from tiny_lidar_net.model.tinylidarnet import TinyLidarNetNp
    
    # Load model weights
    weights_dict = np.load(model_path, allow_pickle=True).item()
    
    # Create model instance
    model = TinyLidarNetNp(input_dim=1080, output_dim=2)
    
    # Load weights into model
    model.params = weights_dict
    
    # Preprocess: normalize by max_range (same as training/inference)
    ranges_normalized = np.clip(ranges / max_range, 0.0, 1.0)
    
    # Reshape for model input: (batch_size=1, channels=1, length=1080)
    x = ranges_normalized.reshape(1, 1, -1).astype(np.float32)
    
    # Forward pass
    output = model(x)  # Shape: (1, 2)
    
    # Extract predictions
    accel = float(output[0, 0])  # First output: acceleration
    steer = float(output[0, 1])  # Second output: steering
    
    return accel, steer


def read_first_lidar_ros2(mcap_path: Path, target_time_sec: float = 10.0) -> tuple[np.ndarray, dict]:
    """Read LiDAR scan closest to target time from ROS2 MCAP (CDR encoded).
    
    Uses relative time from the first LiDAR message.
    """
    best_scan = None
    best_diff = float('inf')
    start_time_ns = None
    
    with AnyReader([mcap_path]) as reader:
        for connection, timestamp, rawdata in reader.messages():
            if connection.topic == "/sensing/lidar/scan":
                # Set start time from first message
                if start_time_ns is None:
                    start_time_ns = timestamp
                
                # Calculate relative time
                relative_time_sec = (timestamp - start_time_ns) / 1e9
                time_diff = abs(relative_time_sec - target_time_sec)
                
                if time_diff < best_diff:
                    msg = reader.deserialize(rawdata, connection.msgtype)
                    ranges = np.array(msg.ranges, dtype=np.float32)
                    header_info = {
                        "frame_id": msg.header.frame_id,
                        "angle_min": msg.angle_min,
                        "angle_max": msg.angle_max,
                        "angle_increment": msg.angle_increment,
                        "range_min": msg.range_min,
                        "range_max": msg.range_max,
                        "num_points": len(ranges),
                        "timestamp_sec": relative_time_sec,
                        "absolute_timestamp": timestamp / 1e9,
                    }
                    best_scan = (ranges, header_info)
                    best_diff = time_diff
    
    if best_scan is None:
        raise ValueError("No LiDAR scan found in ROS2 MCAP")
    return best_scan


def read_first_lidar_json(mcap_path: Path, target_time_sec: float = 10.0) -> tuple[np.ndarray, dict]:
    """Read LiDAR scan closest to target time from JSON MCAP (Simulator)."""
    target_time_ns = int(target_time_sec * 1e9)
    best_scan = None
    best_diff = float('inf')
    
    with open(mcap_path, "rb") as f:
        reader = make_reader(f)
        for schema, channel, message in reader.iter_messages():
            if channel.topic == "/sensing/lidar/scan":
                time_diff = abs(message.log_time - target_time_ns)
                if time_diff < best_diff:
                    data = json.loads(message.data.decode("utf-8"))
                    
                    # Handle None values in ranges
                    ranges_raw = data.get("ranges", [])
                    ranges = []
                    for r in ranges_raw:
                        if r is None:
                            ranges.append(30.0)  # Use max_range for None
                        else:
                            ranges.append(float(r))
                    
                    ranges = np.array(ranges, dtype=np.float32)
                    
                    header_info = {
                        "frame_id": data.get("header", {}).get("frame_id", "unknown"),
                        "angle_min": data.get("angle_min", 0.0),
                        "angle_max": data.get("angle_max", 0.0),
                        "angle_increment": data.get("angle_increment", 0.0),
                        "range_min": data.get("range_min", 0.0),
                        "range_max": data.get("range_max", 30.0),
                        "num_points": len(ranges),
                        "timestamp_sec": message.log_time / 1e9,
                    }
                    best_scan = (ranges, header_info)
                    best_diff = time_diff
    
    if best_scan is None:
        raise ValueError("No LiDAR scan found in JSON MCAP")
    return best_scan


def ranges_to_xy(ranges: np.ndarray, angle_min: float, angle_increment: float) -> tuple[np.ndarray, np.ndarray]:
    """Convert ranges to XY coordinates."""
    num_points = len(ranges)
    angles = angle_min + np.arange(num_points) * angle_increment
    
    # Filter out invalid ranges (inf, nan, 0)
    valid_mask = np.isfinite(ranges) & (ranges > 0.01)
    
    x = ranges[valid_mask] * np.cos(angles[valid_mask])
    y = ranges[valid_mask] * np.sin(angles[valid_mask])
    
    return x, y, valid_mask


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Compare LiDAR scans from ROS2 and Simulator MCAPs')
    parser.add_argument('--time', type=float, default=5.0, 
                        help='Target time in seconds from start (default: 5.0)')
    parser.add_argument('--ros2-mcap', type=str, 
                        default='/home/masa/python-self-driving-simulator/rosbag2_autoware_0.mcap',
                        help='Path to ROS2 MCAP file')
    parser.add_argument('--sim-mcap', type=str,
                        default='/home/masa/python-self-driving-simulator/outputs/2025-12-30/00-55-17/75/train/raw_data/episode_seed75/simulation.mcap',
                        help='Path to Simulator MCAP file')
    parser.add_argument('--output', type=str,
                        default='/home/masa/python-self-driving-simulator/lidar_comparison.png',
                        help='Output image path')
    parser.add_argument('--model', type=str,
                        default='/home/masa/python-self-driving-simulator/outputs/2025-12-30/02-05-08/checkpoints/best_model.npy',
                        help='Path to model weights (.npy file)')
    
    args = parser.parse_args()
    
    ros2_mcap = Path(args.ros2_mcap)
    sim_mcap = Path(args.sim_mcap)
    target_time = args.time
    model_path = Path(args.model)
    
    # Read data
    print(f"Reading ROS2 MCAP (target time: {target_time}s from start)...")
    ros2_ranges, ros2_info = read_first_lidar_ros2(ros2_mcap, target_time)
    print(f"  Relative Time: {ros2_info['timestamp_sec']:.3f}s (Absolute: {ros2_info['absolute_timestamp']:.3f}s)")
    print(f"  Frame: {ros2_info['frame_id']}, Points: {ros2_info['num_points']}")
    print(f"  Angle: [{ros2_info['angle_min']:.3f}, {ros2_info['angle_max']:.3f}], Increment: {ros2_info['angle_increment']:.6f}")
    print(f"  Range: [{ros2_info['range_min']:.3f}, {ros2_info['range_max']:.3f}]")
    
    print(f"\nReading Simulator MCAP (target time: {target_time}s)...")
    sim_ranges, sim_info = read_first_lidar_json(sim_mcap, target_time)
    print(f"  Timestamp: {sim_info['timestamp_sec']:.3f}s")
    print(f"  Frame: {sim_info['frame_id']}, Points: {sim_info['num_points']}")
    print(f"  Angle: [{sim_info['angle_min']:.3f}, {sim_info['angle_max']:.3f}], Increment: {sim_info['angle_increment']:.6f}")
    print(f"  Range: [{sim_info['range_min']:.3f}, {sim_info['range_max']:.3f}]")
    
    # Model inference
    print(f"\nRunning TinyLidarNet model inference...")
    print(f"  Model: {model_path}")
    
    # Use actual trained model
    ros2_accel, ros2_steer = load_and_infer_tinylidarnet(ros2_ranges, model_path, max_range=30.0)
    sim_accel, sim_steer = load_and_infer_tinylidarnet(sim_ranges, model_path, max_range=30.0)
    
    print(f"\n  ROS2 Predictions:")
    print(f"    Accel:  {ros2_accel:.4f}")
    print(f"    Steer:  {ros2_steer:.4f} rad ({np.degrees(ros2_steer):.2f}°)")
    print(f"\n  Sim Predictions:")
    print(f"    Accel:  {sim_accel:.4f}")
    print(f"    Steer:  {sim_steer:.4f} rad ({np.degrees(sim_steer):.2f}°)")
    print(f"\n  Difference:")
    print(f"    Accel:  {abs(ros2_accel - sim_accel):.4f}")
    print(f"    Steer:  {abs(ros2_steer - sim_steer):.4f} rad ({np.degrees(abs(ros2_steer - sim_steer)):.2f}°)")
    
    # Convert to XY
    ros2_x, ros2_y, ros2_valid = ranges_to_xy(ros2_ranges, ros2_info['angle_min'], ros2_info['angle_increment'])
    sim_x, sim_y, sim_valid = ranges_to_xy(sim_ranges, sim_info['angle_min'], sim_info['angle_increment'])
    
    # Create rainbow colors based on array index
    ros2_colors = np.arange(len(ros2_x))
    sim_colors = np.arange(len(sim_x))
    
    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    
    # ROS2 plot
    scatter1 = axes[0].scatter(ros2_x, ros2_y, c=ros2_colors, cmap='rainbow', s=2, alpha=0.8)
    axes[0].set_title(f'ROS2 LiDAR @ {ros2_info["timestamp_sec"]:.2f}s\n({ros2_info["frame_id"]}, {len(ros2_x)} valid points)', 
                      fontsize=11, fontweight='bold')
    axes[0].set_xlabel('X [m]')
    axes[0].set_ylabel('Y [m]')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_aspect('equal')
    axes[0].axhline(0, color='k', linewidth=0.5, alpha=0.3)
    axes[0].axvline(0, color='k', linewidth=0.5, alpha=0.3)
    
    # Add steering prediction as text box
    steer_text1 = f'Predicted Steer:\n{ros2_steer:.4f} rad\n({np.degrees(ros2_steer):.2f}°)'
    axes[0].text(0.02, 0.98, steer_text1, transform=axes[0].transAxes,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.colorbar(scatter1, ax=axes[0], label='Point Index (Array Order)')
    
    # Simulator plot
    scatter2 = axes[1].scatter(sim_x, sim_y, c=sim_colors, cmap='rainbow', s=2, alpha=0.8)
    axes[1].set_title(f'Simulator LiDAR @ {sim_info["timestamp_sec"]:.2f}s\n({sim_info["frame_id"]}, {len(sim_x)} valid points)', 
                      fontsize=11, fontweight='bold')
    axes[1].set_xlabel('X [m]')
    axes[1].set_ylabel('Y [m]')
    axes[1].grid(True, alpha=0.3)
    axes[1].set_aspect('equal')
    axes[1].axhline(0, color='k', linewidth=0.5, alpha=0.3)
    axes[1].axvline(0, color='k', linewidth=0.5, alpha=0.3)
    
    # Add steering prediction as text box
    steer_text2 = f'Predicted Steer:\n{sim_steer:.4f} rad\n({np.degrees(sim_steer):.2f}°)'
    axes[1].text(0.02, 0.98, steer_text2, transform=axes[1].transAxes,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.colorbar(scatter2, ax=axes[1], label='Point Index (Array Order)')
    
    plt.tight_layout()
    output_path = Path(args.output)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nSaved comparison plot to: {output_path}")
    
    # Statistics
    print("\n=== Statistics ===")
    print(f"ROS2: Valid={len(ros2_x)}/{len(ros2_ranges)} ({100*len(ros2_x)/len(ros2_ranges):.1f}%)")
    print(f"  Range: [{ros2_ranges[ros2_valid].min():.2f}, {ros2_ranges[ros2_valid].max():.2f}] m")
    print(f"  Mean: {ros2_ranges[ros2_valid].mean():.2f} m")
    
    print(f"\nSim: Valid={len(sim_x)}/{len(sim_ranges)} ({100*len(sim_x)/len(sim_ranges):.1f}%)")
    print(f"  Range: [{sim_ranges[sim_valid].min():.2f}, {sim_ranges[sim_valid].max():.2f}] m")
    print(f"  Mean: {sim_ranges[sim_valid].mean():.2f} m")


if __name__ == "__main__":
    main()
