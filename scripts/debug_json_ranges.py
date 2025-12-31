import json
from pathlib import Path

from mcap.reader import make_reader


def inspect_json(path):
    print(f"\n{'=' * 20} Sim Data (JSON MCAP) {'=' * 20}")
    if not Path(path).exists():
        print("File not found.")
        return
    try:
        with open(path, "rb") as f:
            reader = make_reader(f)

            for schema, channel, message in reader.iter_messages():
                if "scan" in channel.topic:
                    data = json.loads(message.data)
                    ranges = data.get("ranges", [])
                    print(f"Ranges Type: {type(ranges)}")
                    print(f"Ranges Length: {len(ranges)}")
                    if len(ranges) > 0:
                        print(f"First element: {ranges[0]} (Type: {type(ranges[0])})")
                        print(f"Sample (first 5): {ranges[:5]}")

                        # Check for non-floats
                        non_floats = [x for x in ranges if not isinstance(x, (int, float))]
                        if non_floats:
                            print(
                                f"Found non-float values (count={len(non_floats)}): {non_floats[:5]}"
                            )

                        # Check for nulls
                        nulls = [x for x in ranges if x is None]
                        if nulls:
                            print(f"Found None/null values (count={len(nulls)})")
                    break

    except Exception as e:
        print(f"Error inspecting JSON: {e}")


if __name__ == "__main__":
    inspect_json("outputs/2025-12-30/00-55-17/75/train/raw_data/episode_seed75/simulation.mcap")
