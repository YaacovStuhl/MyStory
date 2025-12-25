#!/bin/bash
# Build script for Render deployment

echo "Changing to MyStory directory..."
cd MyStory || exit 1

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Initializing database..."
python init_db.py || echo "Database initialization failed or already initialized"

echo "Build complete!"

