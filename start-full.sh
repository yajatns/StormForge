#!/bin/bash
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Set Python path
export PYTHONPATH="$(pwd):$PYTHONPATH"

echo "Starting FULL StormForge Traffic Orchestrator..."
echo "Web interface: http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo "Press Ctrl+C to stop"
echo

# Start the full application directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload