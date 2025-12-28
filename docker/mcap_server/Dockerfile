FROM python:3.12-slim

WORKDIR /app

# The server doesn't have external dependencies besides the standard library,
# so we don't need a requirements.txt for now.

# Expose the server port
EXPOSE 8080

# Run the server
# The script is now in the same directory as the Dockerfile in the build context,
# but we mount the whole repo to /app in compose, so it's at /app/docker/mcap_server/mcap_server.py
CMD ["python3", "docker/mcap_server/mcap_server.py"]
