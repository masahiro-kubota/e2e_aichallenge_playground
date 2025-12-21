import sys

from mcap.reader import make_reader


def inspect_mcap(path):
    with open(path, "rb") as f:
        reader = make_reader(f)
        params = {}
        for schema, channel, message in reader.iter_messages():
            key = (channel.topic, schema.name, schema.encoding)
            params[key] = params.get(key, 0) + 1

        print(f"Messages in {path}:")
        for (topic, schema_name, encoding), count in params.items():
            print(f"  Topic: {topic}")
            print(f"    Schema: {schema_name}")
            print(f"    Encoding: {encoding}")
            print(f"    Count: {count}")
            print()


if __name__ == "__main__":
    inspect_mcap(sys.argv[1])
