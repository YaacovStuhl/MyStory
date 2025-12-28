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

# Default to thread-based workers for maximum compatibility on Render/Python 3.13.
# You can opt into gevent by setting USE_GEVENT=true in env vars.
USE_GEVENT="${USE_GEVENT:-false}"
if [ "$USE_GEVENT" = "true" ] && python -c "import gevent" 2>/dev/null; then
    WORKER_CLASS="gevent"
    WORKER_ARGS="--worker-connections 1000"
else
    WORKER_CLASS="gthread"
    WORKER_ARGS="--threads ${GUNICORN_THREADS:-4}"
fi

# If app.py is in current directory
if [ "$APP_DIR" = "." ]; then
    echo "Starting from current directory with $WORKER_CLASS workers"
    echo "Initializing database at runtime (if configured)..."
    python init_db.py || echo "Database initialization skipped/failed (continuing)"
    exec gunicorn --worker-class $WORKER_CLASS -w 1 --bind 0.0.0.0:$PORT --timeout 300 $WORKER_ARGS app:app
else
    # Change to directory containing app.py
    echo "Changing to directory: $APP_DIR"
    echo "Starting with $WORKER_CLASS workers"
    cd "$APP_DIR"
    echo "Initializing database at runtime (if configured)..."
    python init_db.py || echo "Database initialization skipped/failed (continuing)"
    exec gunicorn --worker-class $WORKER_CLASS -w 1 --bind 0.0.0.0:$PORT --timeout 300 $WORKER_ARGS app:app
fi
