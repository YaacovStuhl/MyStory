#!/bin/bash
# Build script for Render deployment

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Initializing database..."
python init_db.py || echo "Database initialization failed or already initialized"

echo "Build complete!"

