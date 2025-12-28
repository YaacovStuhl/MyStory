#!/bin/bash
# Build script for Render deployment
# Handles directory structure automatically

set -e  # Exit on error

echo "=== Render Build Script ==="
echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la | head -20

# Prefer requirements.txt in the current working directory (Render's default),
# otherwise fall back to common subdirectory layouts.
if [ -f "./requirements.txt" ]; then
    REQ_PATH="./requirements.txt"
elif [ -f "./MyStory/requirements.txt" ]; then
    REQ_PATH="./MyStory/requirements.txt"
else
    # Last resort: find the first requirements.txt anywhere (non-deterministic)
    REQ_PATH=$(find . -name "requirements.txt" -type f 2>/dev/null | head -1)
fi

if [ -z "$REQ_PATH" ]; then
    echo "ERROR: requirements.txt not found"
    exit 1
fi

echo "Found requirements.txt at: $REQ_PATH"

# Get directory containing requirements.txt
REQ_DIR=$(dirname "$REQ_PATH")

# If requirements.txt is in current directory
if [ "$REQ_DIR" = "." ]; then
    echo "Installing from current directory"
    pip install -r requirements.txt
else
    # Change to directory containing requirements.txt
    echo "Changing to directory: $REQ_DIR"
    cd "$REQ_DIR"
    pip install -r requirements.txt
fi

echo "Skipping database initialization during build (will run at runtime if DATABASE_URL is set)..."

echo "Build complete!"
