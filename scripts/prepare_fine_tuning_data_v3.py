from pathlib import Path

import numpy as np
from rosbags.highlevel import AnyReader
from sklearn.model_selection import train_test_split


def clean_scan_array(scan_array: np.ndarray, max_range: float) -> np.ndarray:
    if not isinstance(scan_array, np.ndarray):
        scan_array = np.array(scan_array, dtype=np.float32)
    cleaned = np.nan_to_num(scan_array, nan=0.0, posinf=max_range, neginf=0.0)
    cleaned = np.clip(cleaned, 0.0, max_range)
    return cleaned.astype(np.float32)


def synchronize_data(src_times: np.ndarray, target_times: np.ndarray):
    if len(target_times) == 0:
        return np.array([]), np.array([])
    idx_sorted = np.searchsorted(target_times, src_times)
    idx_sorted = np.clip(idx_sorted, 0, len(target_times) - 1)
    prev_idx = np.clip(idx_sorted - 1, 0, len(target_times) - 1)
    time_diff_curr = np.abs(target_times[idx_sorted] - src_times)
    time_diff_prev = np.abs(target_times[prev_idx] - src_times)
    use_prev = time_diff_prev < time_diff_curr
    final_indices = np.where(use_prev, prev_idx, idx_sorted)
    return final_indices


def process_and_split(bag_path, output_dir, control_topic, scan_topic, val_ratio=0.2):
    bag_path = Path(bag_path)
    output_dir = Path(output_dir)
    print(f"Processing {bag_path}...")

    cmd_data = []
    cmd_times = []
    scan_data = []
    scan_times = []

    with AnyReader([bag_path]) as reader:
        connections = [c for c in reader.connections if c.topic in [control_topic, scan_topic]]
        if not connections:
            print("No connections found.")
            return

        for conn, timestamp, raw in reader.messages(connections=connections):
            try:
                msg = reader.deserialize(raw, conn.msgtype)
                if conn.topic == control_topic:
                    accel = msg.longitudinal.acceleration
                    steer = msg.lateral.steering_tire_angle
                    cmd_data.append([steer, accel])
                    cmd_times.append(timestamp)
                elif conn.topic == scan_topic:
                    ranges = np.array(msg.ranges, dtype=np.float32)
                    scan_vec = clean_scan_array(ranges, 30.0)
                    scan_data.append(scan_vec)
                    scan_times.append(timestamp)
            except Exception:
                # print(f"Error decoding {conn.topic}: {e}")
                pass

    print(f"Extracted: Scans={len(scan_data)}, Controls={len(cmd_data)}")

    if not scan_data or not cmd_data:
        print("Insufficient data.")
        return

    np_cmd_data = np.array(cmd_data, dtype=np.float32)
    np_cmd_times = np.array(cmd_times, dtype=np.int64)
    np_scan_data = np.array(scan_data, dtype=np.float32)
    np_scan_times = np.array(scan_times, dtype=np.int64)

    # Sort cmd times just in case
    sort_idx = np.argsort(np_cmd_times)
    np_cmd_times = np_cmd_times[sort_idx]
    np_cmd_data = np_cmd_data[sort_idx]

    # Sync
    indices = synchronize_data(np_scan_times, np_cmd_times)
    synced_cmds = np_cmd_data[indices]

    print(f"Synced Data Shape: Scans={np_scan_data.shape}, Controls={synced_cmds.shape}")

    # Split
    x_train, x_val, y_train, y_val = train_test_split(
        np_scan_data, synced_cmds, test_size=val_ratio, random_state=42
    )

    # Save
    train_dir = output_dir / "train"
    val_dir = output_dir / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    np.save(train_dir / "scans.npy", x_train)
    np.save(train_dir / "steers.npy", y_train[:, 0])
    np.save(train_dir / "accelerations.npy", y_train[:, 1])

    np.save(val_dir / "scans.npy", x_val)
    np.save(val_dir / "steers.npy", y_val[:, 0])
    np.save(val_dir / "accelerations.npy", y_val[:, 1])

    print(f"Saved Train: {len(x_train)} samples to {train_dir}")
    print(f"Saved Val: {len(x_val)} samples to {val_dir}")


if __name__ == "__main__":
    process_and_split(
        "temp_mcap_dir/rosbag2_autoware_0.mcap",
        "data/processed/extra_tuning",
        control_topic="/control/command/control_cmd",
        scan_topic="/sensing/lidar/scan",
    )
