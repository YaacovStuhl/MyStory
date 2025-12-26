#!/bin/bash
# Build script for Render deployment
# Handles directory structure automatically

set -e  # Exit on error

echo "=== Render Build Script ==="
echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la | head -20

# Try to find requirements.txt
REQ_PATH=$(find . -name "requirements.txt" -type f 2>/dev/null | head -1)

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

echo "Initializing database..."
python init_db.py || echo "Database initialization failed or already initialized"

echo "Build complete!"
