#!/bin/bash
# Start script for Render deployment
# Handles directory structure automatically

# Try to find app.py in current directory or MyStory subdirectory
if [ -f app.py ]; then
    # Already in the right directory
    exec gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app
elif [ -f MyStory/app.py ]; then
    # Need to cd into MyStory
    cd MyStory
    exec gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app
else
    echo "Error: app.py not found in current directory or MyStory/"
    ls -la
    exit 1
fi

