#!/bin/bash
set -e

echo "Building static srmc-agent binary using Docker..."

cd "$(dirname "$0")"

# Build the Docker image
docker build -t srmc-agent-builder .

# Create a temporary container and copy the binary
docker create --name srmc-agent-temp srmc-agent-builder
mkdir -p output
docker cp srmc-agent-temp:/app/srmc-agent output/srmc-agent-linux-amd64
docker rm srmc-agent-temp

# Make it executable
chmod +x output/srmc-agent-linux-amd64

echo "Done! Binary is at output/srmc-agent-linux-amd64"
echo "File size:"
ls -lh output/srmc-agent-linux-amd64
echo ""
echo "To deploy to 192.168.12.195:"
echo "  scp output/srmc-agent-linux-amd64 user@192.168.12.195:/usr/local/bin/srmc-agent"
echo "  ssh user@192.168.12.195 'systemctl restart srmc-agent'"
