import sys
from mcap.reader import make_reader
from mcap_ros2.decoder import DecoderFactory
from pathlib import Path

def inspect_mcap(mcap_path):
    print(f"Inspecting {mcap_path}...")
    topic_counts = {}
    
    with open(mcap_path, "rb") as f:
        reader = make_reader(f, decoder_factories=[DecoderFactory()])
        for schema, channel, message in reader.iter_messages():
            topic_counts[channel.topic] = topic_counts.get(channel.topic, 0) + 1
            
    print("\nTopic Counts:")
    for topic, count in topic_counts.items():
        print(f"  {topic}: {count}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_mcap.py <path_to_mcap>")
        sys.exit(1)
    inspect_mcap(sys.argv[1])
