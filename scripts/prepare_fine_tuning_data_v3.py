import argparse
from pathlib import Path

import numpy as np
from mcap.reader import make_reader
from mcap_ros2.decoder import DecoderFactory


def clean_scan_array(scan_array: np.ndarray, max_range: float) -> np.ndarray:
    if not isinstance(scan_array, np.ndarray):
        scan_array = np.array(scan_array, dtype=np.float32)
    cleaned = np.nan_to_num(scan_array, nan=0.0, posinf=max_range, neginf=0.0)
    cleaned = np.clip(cleaned, 0.0, max_range)
    return cleaned.astype(np.float32)


def synchronize_data(src_times: np.ndarray, target_times: np.ndarray):
    """
    Find indices in target_times that correspond to src_times (nearest neighbor, strictly previous preferred?)
    Actually the original logic was:
    Idx closest, but with a slight preference or check?
    Original:
    idx_sorted = np.searchsorted(target_times, src_times)
    ...
    use_prev = time_diff_prev < time_diff_curr
    """
    if len(target_times) == 0:
        return np.array([], dtype=int)

    idx_sorted = np.searchsorted(target_times, src_times)
    idx_sorted = np.clip(idx_sorted, 0, len(target_times) - 1)

    prev_idx = np.clip(idx_sorted - 1, 0, len(target_times) - 1)

    time_diff_curr = np.abs(target_times[idx_sorted] - src_times)
    time_diff_prev = np.abs(target_times[prev_idx] - src_times)

    # Choose closer one
    use_prev = time_diff_prev < time_diff_curr
    final_indices = np.where(use_prev, prev_idx, idx_sorted)
    return final_indices


def process_single_mcap(bag_path: Path, control_topic: str, scan_topic: str):
    cmd_data = []
    cmd_times = []
    scan_data = []
    scan_times = []

    try:
        import json
        from types import SimpleNamespace

        def dict_to_obj(d):
            if isinstance(d, dict):
                return SimpleNamespace(**{k: dict_to_obj(v) for k, v in d.items()})
            elif isinstance(d, list):
                return [dict_to_obj(v) for v in d]
            return d

        with open(bag_path, "rb") as f:
            reader = make_reader(f, decoder_factories=[DecoderFactory()])
            for schema, channel, message in reader.iter_messages(
                topics=[control_topic, scan_topic]
            ):
                timestamp = message.log_time

                msg_obj = None
                if schema.encoding == "jsonschema":
                    msg_dict = json.loads(message.data)
                    msg_obj = dict_to_obj(msg_dict)
                else:
                    # Fallback to standard decoding if possible (though iter_messages returns bytes)
                    # If we used iter_decoded_messages, it would fail on json.
                    # We might need to handle CDR manually if mixed? Assuming all JSON for now based on error.
                    pass

                if msg_obj is None:
                    continue

                if channel.topic == control_topic:
                    # JSON structure usually matches message field names
                    accel = msg_obj.longitudinal.acceleration
                    steer = msg_obj.lateral.steering_tire_angle
                    cmd_data.append([steer, accel])
                    cmd_times.append(timestamp)
                elif channel.topic == scan_topic:
                    ranges = np.array(msg_obj.ranges, dtype=np.float32)
                    scan_vec = clean_scan_array(ranges, 30.0)
                    scan_data.append(scan_vec)
                    scan_times.append(timestamp)

    except Exception as e:
        print(f"Failed to read {bag_path}: {e}")
        return None, None

    if not scan_data or not cmd_data:
        return None, None

    np_cmd_data = np.array(cmd_data, dtype=np.float32)
    np_cmd_times = np.array(cmd_times, dtype=np.int64)
    np_scan_data = np.array(scan_data, dtype=np.float32)
    np_scan_times = np.array(scan_times, dtype=np.int64)

    # Sort cmd times
    sort_idx = np.argsort(np_cmd_times)
    np_cmd_times = np_cmd_times[sort_idx]
    np_cmd_data = np_cmd_data[sort_idx]

    # Sync: For every SCAN, find closest CONTROL
    # This aligns inputs (scans) with labels (controls)
    indices = synchronize_data(np_scan_times, np_cmd_times)
    synced_cmds = np_cmd_data[indices]

    return np_scan_data, synced_cmds


def main():
    parser = argparse.ArgumentParser(description="Extract training data from directory of MCAPs")
    parser.add_argument(
        "--input-dir", required=True, help="Directory containing MCAP files (can be nested)"
    )
    parser.add_argument("--output-dir", required=True, help="Output directory for .npy files")
    parser.add_argument(
        "--control-topic", default="/control/command/control_cmd", help="Control topic name"
    )
    parser.add_argument("--scan-topic", default="/sensing/lidar/scan", help="Lidar scan topic name")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"Error: Input directory {input_dir} does not exist.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    all_scans = []
    all_steers = []
    all_accels = []

    # Recursively find all simulation.mcap files
    # Also look for *.mcap in case names are different
    mcap_files = list(input_dir.rglob("*.mcap"))
    print(f"Found {len(mcap_files)} MCAP files in {input_dir}")

    count = 0
    for mcap_file in mcap_files:
        scans, cmds = process_single_mcap(mcap_file, args.control_topic, args.scan_topic)
        if scans is not None and cmds is not None:
            all_scans.append(scans)
            # cmds is [steer, accel]
            all_steers.append(cmds[:, 0])
            all_accels.append(cmds[:, 1])
            count += 1

            if count % 100 == 0:
                print(f"Processed {count} files...")

    if count == 0:
        print("No valid data extracted.")
        return

    # Concatenate
    final_scans = np.concatenate(all_scans, axis=0)
    final_steers = np.concatenate(all_steers, axis=0)
    final_accels = np.concatenate(all_accels, axis=0)

    print(f"Total Samples: {len(final_scans)}")
    print(f"Saving to {output_dir}...")

    np.save(output_dir / "scans.npy", final_scans)
    np.save(output_dir / "steers.npy", final_steers)
    np.save(output_dir / "accelerations.npy", final_accels)
    print("Done.")


if __name__ == "__main__":
    main()
