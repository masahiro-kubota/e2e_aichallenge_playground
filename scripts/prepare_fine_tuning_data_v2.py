import numpy as np
from pathlib import Path
from mcap.reader import make_reader
from rosbags.typesys import get_types_from_idl, get_typestore, Stores
from rosbags.serde import deserialize_cdr
from sklearn.model_selection import train_test_split

def extract_and_split(mcap_path, output_dir, val_ratio=0.2):
    mcap_path = Path(mcap_path)
    output_dir = Path(output_dir)
    print(f"Processing {mcap_path}...")

    scans_list = []
    scan_times = []
    control_data = [] # [steer, accel]
    control_times = []

    # Initialize a type store
    # LATEST_ROS2 provides standard types
    typestore = get_typestore(Stores.ROS2_FOXY) # Assuming standard ROS2 distro, or just empty?
    # Actually, custom types need to be added. 
    # If I use EMPTY, I must add everything. ROS2_FOXY has std_msgs/sensor_msgs.
    
    registered_schemas = set()

    with open(mcap_path, "rb") as f:
        reader = make_reader(f)
        for schema, channel, message in reader.iter_messages():
            if channel.topic == "/sensing/lidar/scan":
                msg_type_name = schema.name.replace("/", ".")
                
                # Register if needed
                if schema.id not in registered_schemas:
                    if schema.encoding == "ros2idl":
                        idl_text = schema.data.decode("utf-8")
                        try:
                            types = get_types_from_idl(idl_text)
                            typestore.register(types)
                            registered_schemas.add(schema.id)
                        except Exception as e:
                            # If it fails, maybe it's already there (standard)?
                            # Or dependency missing.
                            # For LidarScan, it likely exists in ROS2_FOXY store.
                            # print(f"Schema reg error {schema.name}: {e}")
                            pass
                
                try:
                    # Pass typestore to deserialize_cdr?
                    # rosbags 0.11 deserialize_cdr signature: (rawdata, typename, typestore)
                    msg = deserialize_cdr(message.data, msg_type_name, typestore)
                    
                    if hasattr(msg, "ranges"):
                        ranges = np.array(msg.ranges, dtype=np.float32)
                        ranges = np.nan_to_num(ranges, posinf=30.0, neginf=0.0)
                        scans_list.append(ranges)
                        scan_times.append(message.log_time)
                except Exception as e:
                     # print(f"Lidar decode error: {e}")
                     pass

            elif channel.topic == "/control/command/control_cmd":
                msg_type_name = schema.name.replace("/", ".")
                
                if schema.id not in registered_schemas:
                    if schema.encoding == "ros2idl":
                        idl_text = schema.data.decode("utf-8")
                        try:
                            types = get_types_from_idl(idl_text)
                            typestore.register(types)
                            registered_schemas.add(schema.id)
                        except Exception as e:
                            print(f"Failed to register schema for {schema.name}: {e}")

                try:
                    msg = deserialize_cdr(message.data, msg_type_name, typestore)
                    # autoware_auto_control_msgs.msg.AckermannControlCommand
                    steer = msg.lateral.steering_tire_angle
                    accel = msg.longitudinal.acceleration
                    control_data.append([steer, accel])
                    control_times.append(message.log_time)
                except AttributeError:
                    # Maybe structure is different?
                    # Try inspecting keys if possible?
                    pass
                except Exception as e:
                    # print(f"Control decode error: {e}")
                    pass

    print(f"Extracted: Scans={len(scans_list)}, Controls={len(control_data)}")

    if not scans_list or not control_data:
        print("Error: No data extracted.")
        return

    # Sync
    s_times = np.array(scan_times, dtype=np.int64)
    c_times = np.array(control_times, dtype=np.int64)
    c_data = np.array(control_data, dtype=np.float32)

    # Sync: find closest control for each scan
    idx = np.searchsorted(c_times, s_times)
    idx = np.clip(idx, 0, len(c_times) - 1)
    
    synced_controls = c_data[idx]
    scans_array = np.array(scans_list, dtype=np.float32)

    print(f"Synced Data Shape: Scans={scans_array.shape}, Controls={synced_controls.shape}")

    # Split
    X_train, X_val, y_train, y_val = train_test_split(
        scans_array, synced_controls, test_size=val_ratio, random_state=42
    )

    # Save
    train_dir = output_dir / "train"
    val_dir = output_dir / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    # Train
    np.save(train_dir / "scans.npy", X_train)
    np.save(train_dir / "steers.npy", y_train[:, 0])
    np.save(train_dir / "accelerations.npy", y_train[:, 1])

    # Val
    np.save(val_dir / "scans.npy", X_val)
    np.save(val_dir / "steers.npy", y_val[:, 0])
    np.save(val_dir / "accelerations.npy", y_val[:, 1])

    print(f"Saved Train: {len(X_train)} samples to {train_dir}")
    print(f"Saved Val: {len(X_val)} samples to {val_dir}")

if __name__ == "__main__":
    extract_and_split(
        "temp_mcap_dir/rosbag2_autoware_0.mcap",
        "data/processed/extra_tuning"
    )
