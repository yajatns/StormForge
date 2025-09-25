#!/bin/bash

# Install missing dependencies for full StormForge app
cd "$(dirname "$0")"
source venv/bin/activate

echo "Installing missing dependencies for full StormForge app..."

# Install structlog and other missing dependencies
pip install structlog || echo "structlog install failed, will create workaround"

# Install other likely missing dependencies
pip install python-jose || echo "python-jose failed"
pip install passlib || echo "passlib failed"
pip install python-multipart || echo "python-multipart failed"

echo "Dependencies installed. You can now try: ./start-full.sh"