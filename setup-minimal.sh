#!/bin/bash

# StormForge - Minimal Setup Script
# Skips problematic system updates and focuses on core setup

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"; }
error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"; }
warn() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"; }
info() { echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"; }

if [ "$EUID" -eq 0 ]; then
    error "Please run this script as a regular user, not as root!"
    exit 1
fi

PROJECT_DIR=$(pwd)

log "Starting StormForge minimal setup..."
info "Project directory: $PROJECT_DIR"
info "User: $(whoami)"

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    error "app/main.py not found. Please run this from the StormForge project root."
    exit 1
fi

# Install only essential packages without full system update
log "Installing essential packages (no system update)..."
sudo apt install -y python3 python3-pip python3-venv hping3 curl wget git sqlite3 || {
    warn "Some packages failed to install, continuing..."
}

# Set hping3 capabilities
log "Setting capabilities for hping3..."
HPING3_PATH=$(which hping3 2>/dev/null || echo "/usr/sbin/hping3")
if [ -f "$HPING3_PATH" ]; then
    sudo setcap cap_net_raw=eip "$HPING3_PATH"
    log "Capabilities set for hping3 at $HPING3_PATH"
else
    warn "hping3 not found, you may need to install it manually"
fi

# Create virtual environment
log "Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
else
    log "Virtual environment already exists"
fi

# Activate and install Python dependencies
log "Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip

# Install core dependencies directly
pip install fastapi==0.104.1 uvicorn[standard]==0.24.0 sqlalchemy==2.0.23 || {
    error "Failed to install core dependencies"
    exit 1
}

pip install aiosqlite==0.19.0 python-jose[cryptography]==3.3.0 bcrypt==4.1.2 || {
    warn "Some optional dependencies failed, continuing..."
}

pip install python-multipart==0.0.6 websockets==12.0 python-dotenv==1.0.0 || {
    warn "Some optional dependencies failed, continuing..."
}

# Create directories
mkdir -p logs data config

# Create environment file
if [ ! -f ".env" ]; then
    log "Creating .env file..."
    cat > .env << 'EOF'
DATABASE_URL=sqlite:///./data/orchestrator.db
SECRET_KEY=dev-secret-change-in-production  
JWT_SECRET_KEY=dev-jwt-secret-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEBUG=true
HOST=0.0.0.0
PORT=8000
HPING3_PATH=/usr/sbin/hping3
MAX_CONCURRENT_JOBS=10
DEFAULT_TIMEOUT=30
LOG_LEVEL=INFO
LOG_FILE=./logs/orchestrator.log
EOF
fi

# Test imports
log "Testing Python setup..."
python3 -c "
import fastapi, sqlalchemy, uvicorn
print('✓ Core modules imported successfully')
"

# Initialize database
log "Initializing database..."
python3 -c "
import sys; sys.path.append('.')
from app.database import engine, Base
Base.metadata.create_all(bind=engine)
print('✓ Database initialized')
" || warn "Database initialization had issues (may be OK if already exists)"

# Create start script
cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
export PYTHONPATH="$(pwd):$PYTHONPATH"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
EOF
chmod +x start.sh

log "Minimal setup complete!"
echo
info "==================== SETUP COMPLETE ===================="
echo
log "To start StormForge:"
echo "  ./start.sh"
echo
log "Access the web interface at:"
echo "  http://localhost:8000"
echo "  http://$(hostname -I | awk '{print $1}'):8000"
echo
log "API docs available at:"  
echo "  http://localhost:8000/docs"
echo
warn "IMPORTANT NOTES:"
warn "1. Change the secrets in .env for production use"
warn "2. Default admin user will be created on first run"
warn "3. This is a minimal setup - run fix-system.sh first if you had package errors"
echo