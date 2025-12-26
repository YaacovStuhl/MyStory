#!/bin/bash
# Start script for Render deployment
# Handles directory structure automatically

set -e  # Exit on error

echo "=== Render Start Script ==="
echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la | head -20

# Try to find app.py
APP_PATH=$(find . -name "app.py" -type f 2>/dev/null | head -1)

if [ -z "$APP_PATH" ]; then
    echo "ERROR: app.py not found anywhere"
    echo "Searching for Python files:"
    find . -name "*.py" -type f 2>/dev/null | head -10
    exit 1
fi

echo "Found app.py at: $APP_PATH"

# Get directory containing app.py
APP_DIR=$(dirname "$APP_PATH")

# If app.py is in current directory
if [ "$APP_DIR" = "." ]; then
    echo "Starting from current directory"
    exec gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app
else
    # Change to directory containing app.py
    echo "Changing to directory: $APP_DIR"
    cd "$APP_DIR"
    exec gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app
fi
