
import json
import random
import shutil
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 3:
        print("Usage: python split_successful_data.py <input_root_dir> <output_base_dir> [train_ratio] [suffix]")
        return

    input_root = Path(sys.argv[1])
    output_base = Path(sys.argv[2])
    train_ratio = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8
    suffix = sys.argv[4] if len(sys.argv) > 4 else "v3"

    if not input_root.exists():

        print(f"Error: Input directory {input_root} does not exist.")
        return

    # Find all successful episodes
    successful_episodes = []
    
    # Structure is usually: input_root / <seed_dir> / pool / raw_data
    # We look for result.json recursively
    for result_file in input_root.rglob("result.json"):
        try:
            with open(result_file, 'r') as f:
                data = json.load(f)
                if data.get("success", False):
                    # Found a successful episode
                    # The "raw_data" directory is usually the parent of result.json
                    raw_data_dir = result_file.parent
                    successful_episodes.append(raw_data_dir)
        except Exception as e:
            print(f"Warning: Failed to read {result_file}: {e}")

    total_success = len(successful_episodes)
    print(f"Found {total_success} successful episodes.")

    if total_success == 0:
        print("No successful episodes found. Exiting.")
        return

    # Shuffle and split
    random.seed(42)
    random.shuffle(successful_episodes)

    n_train = int(total_success * train_ratio)
    train_episodes = successful_episodes[:n_train]
    val_episodes = successful_episodes[n_train:]

    print(f"Split: {len(train_episodes)} Train, {len(val_episodes)} Val")

    # Create Output Directories
    train_dir = output_base / f"train_{suffix}"
    val_dir = output_base / f"val_{suffix}"
    
    # Clean up existing

    if train_dir.exists(): shutil.rmtree(train_dir)
    if val_dir.exists(): shutil.rmtree(val_dir)
    
    train_dir.mkdir(parents=True)
    val_dir.mkdir(parents=True)

    # Function to copy/link
    def link_episodes(episodes, target_dir):
        for i, ep_dir in enumerate(episodes):
            # Create a real directory for the episode
            dest_ep_dir = target_dir / f"episode_{i}"
            dest_ep_dir.mkdir()
            
            # Symlink the MCAP file and result.json
            src_mcap = ep_dir / "simulation.mcap"
            src_result = ep_dir / "result.json"
            
            if src_mcap.exists():
                (dest_ep_dir / "simulation.mcap").symlink_to(src_mcap.resolve())
            if src_result.exists():
                (dest_ep_dir / "result.json").symlink_to(src_result.resolve())

    link_episodes(train_episodes, train_dir)
    link_episodes(val_episodes, val_dir)

    print(f"Successfully created symlinks in {output_base}")
    print(f"Train Input Dir for Extraction: {train_dir}")
    print(f"Val Input Dir for Extraction: {val_dir}")

if __name__ == "__main__":
    main()
