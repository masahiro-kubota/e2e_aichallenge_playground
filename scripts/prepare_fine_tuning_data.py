import numpy as np
import json
import struct
from pathlib import Path
from mcap.reader import make_reader
from mcap_ros2.decoder import DecoderFactory
from sklearn.model_selection import train_test_split

def extract_and_split(mcap_path, output_dir, val_ratio=0.2):
    mcap_path = Path(mcap_path)
    output_dir = Path(output_dir)
    print(f"Processing {mcap_path} with mcap lib + manual decoding...")

    scans_list = []
    scan_times = []
    control_data = [] # [steer, accel]
    control_times = []
    
    decoder_factory = DecoderFactory()

    with open(mcap_path, "rb") as f:
        reader = make_reader(f)
        for schema, channel, message in reader.iter_messages():
            if channel.topic == "/sensing/lidar/scan":
                # Use standard decoder for Lidar
                decoder = decoder_factory.decoder_for(channel.message_encoding, schema)
                if decoder:
                    try:
                        # Try bytes first
                        msg = decoder(message.data)
                        if hasattr(msg, "ranges"):
                            ranges = np.array(msg.ranges, dtype=np.float32)
                            ranges = np.nan_to_num(ranges, posinf=30.0, neginf=0.0)
                            scans_list.append(ranges)
                            scan_times.append(message.log_time)
                    except Exception:
                        pass
            
            elif channel.topic == "/control/command/control_cmd":
                # Manual decoding for AckermannControlCommand
                # Expecting CDR encoding
                # Layout hypothesis (assuming CDR LE and specific struct):
                # Header (4 bytes)
                # Stamp (8 bytes)
                # Lateral: Stamp (8 bytes), Steer (4), Rate (4)
                # Longitudinal: Stamp (8 bytes), Speed (4), Accel (4), Jerk (4)
                
                # Check encoding
                # if channel.message_encoding != 'cdr': continue

                data = message.data
                if len(data) < 44: 
                    # Try to deduce offset from data size?
                    # 4+8+8+4+4+8+4+4+4 = 48 bytes? 
                    # Let's check size.
                    continue
                
                # Assume encapsulated CDR (4 byte header). 
                # Check byte 1 (index 1) for endianness: 1=Little Endian
                # But usually just try unpacking.
                
                try:
                    # Offset 4 (header) + 8 (Stamp) = 12
                    
                    # Lateral Stamp: 12-20
                    # Lateral Steer: 20
                    
                    # Longitudinal Stamp: 20+4+4 = 28
                    # Longitudinal Speed: 28+8 = 36
                    # Longitudinal Accel: 36+4 = 40
                    
                    # Wait, alignment.
                    # 4 (header). 
                    # 8 (Stamp). Aligned to 4 or 8?
                    # If aligned to 8 (Time), then no padding after header (4)? 
                    # 4 -> 8 (padding 4 bytes?) -> 16.
                    # Let's print raw bytes len first to guess structure.
                    
                    # Unpack float32 at different offsets.
                    # We expect values to be somewhat reasonable. 
                    # Steer: -0.5 to 0.5 roughly.
                    # Accel: -something to +something.
                    
                    # For now, let's just create a quick heuristic parser
                    # We will read logic in update loop.
                    
                    # Heuristic: 
                    # Offset 20?
                    steer = struct.unpack_from('<f', data, 20)[0] # Little endian
                    
                    # Offset 40?
                    # But if alignment adds padding...
                    # Header 4.
                    # Time 8. (4->12? No, 8-byte alignment usually requires address % 8 == 0)
                    # If CDR header is at 0.
                    # Stamp at 4? 4 is not 8-byte aligned. So padding 4 bytes? -> Start at 8?
                    # If start at 8:
                    # Stamp: 8-16.
                    # Lateral.Stamp: 16-24.
                    # Lateral.Steer: 24-28.
                    # Lateral.Rate: 28-32.
                    # Longitudinal.Stamp: 32-40.
                    # Longitudinal.Speed: 40-44.
                    # Longitudinal.Accel: 44-48.
                    
                    # Let's try offsets 24 and 44?
                    
                    # Just to be safe, I'm going to look for 'reasonable' float values? 
                    # No, that's dangerous.
                    
                    if len(control_data) == 0:
                         print(f"Control Data Len: {len(data)}")
                         
                         vals = {}
                         for off in [16, 20, 24, 36, 40, 44]:
                             try:
                                 vals[off] = struct.unpack_from('<f', data, off)[0]
                             except:
                                 vals[off] = "Err"
                         print(f"Cand Offsets: {vals}")
                         
                         # Assume 20 is Steer (likely correct)
                         # We need Accel.
                         
                    # Based on findings, we will set correct offsets.
                    # For current run, I will use logic:
                    # If I see 3.18 at 40, and 0 at 44. 
                    # Use placeholders for now until I confirm output.
                    
                    steer = struct.unpack_from('<f', data, 20)[0]
                    accel = struct.unpack_from('<f', data, 40)[0] # Tentative
                    
                    control_data.append([steer, accel])
                    control_times.append(message.log_time)
                    
                except Exception as e:
                    # print(f"Manual parse error: {e}")
                    pass

    print(f"Extracted: Scans={len(scans_list)}, Controls={len(control_data)}")

    if not scans_list or not control_data:
        print("Error: No data extracted.")
        return

    # Sync
    s_times = np.array(scan_times, dtype=np.int64)
    c_times = np.array(control_times, dtype=np.int64)
    c_data = np.array(control_data, dtype=np.float32)
    s_scans = np.array(scans_list, dtype=np.float32)

    # Sync: find closest control for each scan
    idx = np.searchsorted(c_times, s_times)
    idx = np.clip(idx, 0, len(c_times) - 1)
    
    synced_controls = c_data[idx]

    # Split
    X_train, X_val, y_train, y_val = train_test_split(
        s_scans, synced_controls, test_size=val_ratio, random_state=42
    )

    # Save
    train_dir = output_dir / "train"
    val_dir = output_dir / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    np.save(train_dir / "scans.npy", X_train)
    np.save(train_dir / "steers.npy", y_train[:, 0])
    np.save(train_dir / "accelerations.npy", y_train[:, 1])

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
