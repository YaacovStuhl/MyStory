#!/bin/bash
# Start script for Render deployment
# Handles directory structure automatically

set -e  # Exit on error

echo "=== Render Start Script ==="
echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la | head -20

# Prefer the repo's own app.py, and avoid accidentally grabbing Flask's internal
# `site-packages/flask/app.py` from a virtualenv.
if [ -f "./app.py" ]; then
    APP_PATH="./app.py"
else
    # Search for app.py but ignore virtualenvs and site-packages.
    APP_PATH=$(
        find . \
            -type d \( -name ".venv" -o -name "venv" -o -name "__pycache__" -o -name "site-packages" \) -prune -o \
            -type f -name "app.py" -print 2>/dev/null | head -1
    )
fi

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
    # IMPORTANT: Render may run the start command multiple times (deploy/health/instance restarts).
    # Default to NOT running DB initialization on startup; you can opt-in temporarily.
    if [ "${RUN_DB_INIT_ON_START:-false}" = "true" ]; then
        DB_INIT_MARKER="${DB_INIT_MARKER:-.db_initialized}"
        if [ -n "$DATABASE_URL" ]; then
            if [ "${FORCE_DB_INIT:-false}" = "true" ] || [ ! -f "$DB_INIT_MARKER" ]; then
                echo "Initializing database at runtime (one-time)..."
                if python init_db.py; then
                    touch "$DB_INIT_MARKER" || true
                else
                    echo "Database initialization failed (continuing)"
                fi
            else
                echo "Database already initialized (marker found), skipping"
            fi
        else
            echo "DATABASE_URL not set, skipping database initialization"
        fi
    else
        echo "RUN_DB_INIT_ON_START is false; skipping database initialization"
    fi
    exec gunicorn --worker-class $WORKER_CLASS -w 1 --bind 0.0.0.0:$PORT --timeout 300 $WORKER_ARGS app:app
else
    # Change to directory containing app.py
    echo "Changing to directory: $APP_DIR"
    echo "Starting with $WORKER_CLASS workers"
    cd "$APP_DIR"
    # IMPORTANT: Render may run the start command multiple times (deploy/health/instance restarts).
    # Default to NOT running DB initialization on startup; you can opt-in temporarily.
    if [ "${RUN_DB_INIT_ON_START:-false}" = "true" ]; then
        DB_INIT_MARKER="${DB_INIT_MARKER:-.db_initialized}"
        if [ -n "$DATABASE_URL" ]; then
            if [ "${FORCE_DB_INIT:-false}" = "true" ] || [ ! -f "$DB_INIT_MARKER" ]; then
                echo "Initializing database at runtime (one-time)..."
                if python init_db.py; then
                    touch "$DB_INIT_MARKER" || true
                else
                    echo "Database initialization failed (continuing)"
                fi
            else
                echo "Database already initialized (marker found), skipping"
            fi
        else
            echo "DATABASE_URL not set, skipping database initialization"
        fi
    else
        echo "RUN_DB_INIT_ON_START is false; skipping database initialization"
    fi
    exec gunicorn --worker-class $WORKER_CLASS -w 1 --bind 0.0.0.0:$PORT --timeout 300 $WORKER_ARGS app:app
fi
