#!/bin/bash

# Function to parse the version from the setup.py file
get_version() {
  local setup_file="setup.py"
  if [ -f "$setup_file" ]; then
    version=$(grep -Po "(?<=version=\")[^\"]*" "$setup_file")
    echo $version
  else
    echo "Error: setup.py file not found!"
    exit 1
  fi
}

# Get the version
VERSION=$(get_version)

# Ensure the dist directory exists
mkdir -p dist

# Define the output tarball name
OUTPUT_TARBALL="dist/beacon-agent-${VERSION}.tar.gz"

# Define the directories and files to include
INCLUDE_ITEMS=(
  "beacon_agent"
  "SYSTEMD"
  "beacon_agent_main.py"
  "run.sh"
)

# Create a temporary directory to hold the files
TMP_DIR=$(mktemp -d)

# Copy the items into the temporary directory and rename SYSTEMD to systemd, exclude __pycache__
for ITEM in "${INCLUDE_ITEMS[@]}"; do
    if [ "$ITEM" == "SYSTEMD" ]; then
        rsync -avr --exclude='__pycache__' "$ITEM/" "$TMP_DIR/systemd"
    else
        rsync -avr --exclude='__pycache__' "$ITEM" "$TMP_DIR/"
    fi
done

# Create the tarball from the temporary directory
tar --exclude='__pycache__' -czvf $OUTPUT_TARBALL -C $TMP_DIR .

# Clean up the temporary directory
rm -rf $TMP_DIR

echo "Tarball $OUTPUT_TARBALL created successfully."