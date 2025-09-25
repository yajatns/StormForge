#!/bin/bash
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Set Python path
export PYTHONPATH="$(pwd):$PYTHONPATH"

echo "Starting StormForge (Simplified Version)..."
echo "Web interface: http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo "System status: http://localhost:8000/api/v1/system/status"
echo "Press Ctrl+C to stop"
echo

# Start the simplified application
uvicorn app.simple_main:app --host 0.0.0.0 --port 8000 --reload