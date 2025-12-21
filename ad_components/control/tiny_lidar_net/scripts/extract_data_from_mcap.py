"""Extract LiDAR and control data from MCAP files."""

import argparse
import json
from pathlib import Path

import numpy as np
from mcap.reader import make_reader
from mcap_ros2.decoder import DecoderFactory


def extract_data_from_mcap(mcap_path: Path, output_dir: Path) -> None:
    """Extract LiDAR scans and control commands from MCAP file.

    Args:
        mcap_path: Path to MCAP file
        output_dir: Directory to save extracted data
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    scans_list = []
    scan_times = []
    control_times = []
    control_data = []

    print(f"Reading MCAP file: {mcap_path}")

    with open(mcap_path, "rb") as f:
        reader = make_reader(f, decoder_factories=[DecoderFactory()])

        target_topics = ["/perception/lidar/scan", "/control/command/control_cmd"]

        for schema, channel, message in reader.iter_messages():
            if channel.topic not in target_topics:
                continue

            msg = None
            if schema.encoding in ["json", "jsonschema"]:
                try:
                    msg = json.loads(message.data)
                except json.JSONDecodeError as e:
                    print(f"JSON decode error for topic {channel.topic}: {e}")
                    continue
            elif schema.encoding == "cdr":
                decoder = DecoderFactory().decoder_for(schema.encoding, schema)
                if decoder:
                    msg = decoder.decode(message.data)

            if msg is None:
                continue

            # Extract LiDAR scans
            if channel.topic == "/perception/lidar/scan":
                ranges = None
                if isinstance(msg, dict):
                    if "ranges" in msg:
                        ranges = np.array(msg["ranges"], dtype=np.float32)
                elif hasattr(msg, "ranges"):
                    ranges = np.array(msg.ranges, dtype=np.float32)

                if ranges is not None:
                    scans_list.append(ranges)
                    scan_times.append(message.log_time)
                else:
                    print(f"Warning: LiDAR message missing ranges field. Type: {type(msg)}")

            # Extract control commands
            elif channel.topic == "/control/command/control_cmd":
                steer = 0.0
                accel = 0.0
                found = False

                if isinstance(msg, dict):
                    if "drive" in msg:  # AckermannDriveStamped
                        drive = msg["drive"]
                        steer = drive.get("steering_angle", 0.0)
                        accel = drive.get("acceleration", 0.0)
                        found = True
                    elif "lateral" in msg and "longitudinal" in msg:  # Autoware Control
                        steer = msg["lateral"].get("steering_tire_angle", 0.0)
                        accel = msg["longitudinal"].get("acceleration", 0.0)
                        found = True
                    elif "steering" in msg and "acceleration" in msg:  # Simple dict
                        steer = msg.get("steering", 0.0)
                        accel = msg.get("acceleration", 0.0)
                        found = True
                else:
                    if hasattr(msg, "drive"):  # AckermannDriveStamped
                        steer = msg.drive.steering_angle
                        accel = msg.drive.acceleration
                        found = True
                    elif hasattr(msg, "lateral") and hasattr(
                        msg, "longitudinal"
                    ):  # Autoware Control
                        steer = msg.lateral.steering_tire_angle
                        accel = msg.longitudinal.acceleration
                        found = True

                if found:
                    control_data.append([steer, accel])
                    control_times.append(message.log_time)
                else:
                    print(f"Warning: Control message format not recognized. Type: {type(msg)}")
                    if isinstance(msg, dict):
                        print(f"Keys: {msg.keys()}")

    if not scans_list or not control_data:
        print("Warning: No data extracted from MCAP file")
        print(f"Scans extracted: {len(scans_list)}")
        print(f"Control commands extracted: {len(control_data)}")
        return

    # Convert to numpy arrays
    scans = np.array(scans_list, dtype=np.float32)
    scan_times = np.array(scan_times, dtype=np.int64)
    control_data = np.array(control_data, dtype=np.float32)
    control_times = np.array(control_times, dtype=np.int64)

    print(f"Extracted {len(scans)} LiDAR scans and {len(control_data)} control commands")

    # Synchronize data using nearest neighbor
    indices, deltas = synchronize_data(scan_times, control_times)

    synced_controls = control_data[indices]
    synced_steers = synced_controls[:, 0]
    synced_accels = synced_controls[:, 1]

    # Save data
    np.save(output_dir / "scans.npy", scans)
    np.save(output_dir / "steers.npy", synced_steers)
    np.save(output_dir / "accelerations.npy", synced_accels)

    print(f"Saved data to {output_dir}")
    print(f"  scans.npy: {scans.shape}")
    print(f"  steers.npy: {synced_steers.shape}")
    print(f"  accelerations.npy: {synced_accels.shape}")


def synchronize_data(
    src_times: np.ndarray, target_times: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Synchronize two time series using nearest neighbor search.

    Args:
        src_times: Timestamps of the source data (e.g., Scan times)
        target_times: Reference timestamps to match against (e.g., Control times)

    Returns:
        Tuple of (indices, deltas) where indices are the matched target indices
        and deltas are the time differences
    """
    if len(target_times) == 0:
        return np.array([]), np.array([])

    # Find insertion points for source times in target times
    idx_sorted = np.searchsorted(target_times, src_times)

    # Clip indices to stay within valid bounds
    idx_sorted = np.clip(idx_sorted, 0, len(target_times) - 1)
    prev_idx = np.clip(idx_sorted - 1, 0, len(target_times) - 1)

    # Calculate time differences for current and previous indices
    time_diff_curr = np.abs(target_times[idx_sorted] - src_times)
    time_diff_prev = np.abs(target_times[prev_idx] - src_times)

    # Select the index with the smaller time difference
    use_prev = time_diff_prev < time_diff_curr
    final_indices = np.where(use_prev, prev_idx, idx_sorted)
    final_deltas = np.where(use_prev, time_diff_prev, time_diff_curr)

    return final_indices, final_deltas


def main():
    parser = argparse.ArgumentParser(description="Extract data from MCAP file")
    parser.add_argument("--mcap", type=Path, required=True, help="Path to MCAP file")
    parser.add_argument(
        "--output", type=Path, required=True, help="Output directory for extracted data"
    )

    args = parser.parse_args()

    extract_data_from_mcap(args.mcap, args.output)


if __name__ == "__main__":
    main()
