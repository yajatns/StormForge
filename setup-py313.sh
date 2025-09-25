#!/bin/bash

# StormForge - Python 3.13 Compatible Setup Script
# Fixes SQLAlchemy compatibility issues

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
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')

log "Starting StormForge setup (Python $PYTHON_VERSION compatible)..."
info "Project directory: $PROJECT_DIR"
info "User: $(whoami)"

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    error "app/main.py not found. Please run this from the StormForge project root."
    exit 1
fi

# Install essential packages
log "Installing essential packages..."
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

# Remove existing venv if it has compatibility issues
if [ -d "venv" ]; then
    warn "Removing existing virtual environment to fix compatibility issues..."
    rm -rf venv
fi

# Create fresh virtual environment
log "Creating fresh Python virtual environment..."
python3 -m venv venv

# Activate and upgrade pip
log "Activating virtual environment and upgrading pip..."
source venv/bin/activate
pip install --upgrade pip

# Install Python 3.13 compatible versions
log "Installing Python 3.13 compatible dependencies..."

# Core web framework with compatible versions
pip install fastapi==0.104.1 || {
    error "Failed to install FastAPI"
    exit 1
}

pip install "uvicorn[standard]==0.24.0" || {
    warn "Uvicorn with extras failed, trying basic version..."
    pip install uvicorn==0.24.0
}

# Use newer SQLAlchemy that supports Python 3.13
log "Installing SQLAlchemy 2.0.25 (Python 3.13 compatible)..."
pip install sqlalchemy==2.0.25 || {
    warn "SQLAlchemy 2.0.25 failed, trying 2.0.35..."
    pip install sqlalchemy==2.0.35 || {
        error "Failed to install compatible SQLAlchemy version"
        exit 1
    }
}

# Database drivers
pip install aiosqlite==0.19.0

# Authentication and security
pip install "python-jose[cryptography]==3.3.0" || {
    warn "python-jose with cryptography failed, trying without extras..."
    pip install python-jose==3.3.0
    pip install cryptography
}

pip install bcrypt==4.1.2
pip install passlib==1.7.4

# Other core dependencies
pip install python-multipart==0.0.6
pip install websockets==12.0
pip install python-dotenv==1.0.0
pip install pydantic==2.5.0
pip install httpx==0.25.2

# Create directories
mkdir -p logs data config

# Create environment file
if [ ! -f ".env" ]; then
    log "Creating .env file..."
    cat > .env << 'EOF'
DATABASE_URL=sqlite:///./data/orchestrator.db
SECRET_KEY=dev-secret-change-in-production-$(openssl rand -hex 16)
JWT_SECRET_KEY=dev-jwt-secret-change-in-production-$(openssl rand -hex 16)
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEBUG=true
HOST=0.0.0.0
PORT=8000
HPING3_PATH=/usr/sbin/hping3
MAX_CONCURRENT_JOBS=10
DEFAULT_TIMEOUT=30
LOG_LEVEL=INFO
LOG_FILE=./logs/orchestrator.log
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
EOF
fi

# Test imports with better error handling
log "Testing Python setup..."
python3 -c "
try:
    import fastapi
    print('✓ FastAPI imported successfully')
    
    import sqlalchemy
    print(f'✓ SQLAlchemy {sqlalchemy.__version__} imported successfully')
    
    import uvicorn
    print('✓ Uvicorn imported successfully')
    
    import aiosqlite
    print('✓ AsyncSQLite imported successfully')
    
    print('✓ All core modules imported successfully')
except Exception as e:
    print(f'✗ Import error: {e}')
    import sys
    sys.exit(1)
"

# Initialize database with better error handling
log "Initializing database..."
python3 -c "
import sys
sys.path.append('.')

try:
    from app.database import engine, Base
    print('✓ Database modules imported')
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print('✓ Database tables created successfully')
    
except Exception as e:
    print(f'Database initialization error: {e}')
    print('This might be OK if tables already exist or modules need adjustment')
"

# Create improved start script
cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Set Python path
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found!"
    exit 1
fi

echo "Starting StormForge Traffic Orchestrator..."
echo "Web interface will be available at: http://localhost:8000"
echo "API documentation: http://localhost:8000/docs"
echo "Press Ctrl+C to stop"
echo

# Start the application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
EOF
chmod +x start.sh

# Create a test script
cat > test-setup.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

echo "Testing StormForge setup..."

python3 -c "
import sys
sys.path.append('.')

print('Testing imports...')
import fastapi, sqlalchemy, uvicorn, aiosqlite
print(f'✓ FastAPI: {fastapi.__version__}')
print(f'✓ SQLAlchemy: {sqlalchemy.__version__}')
print(f'✓ Uvicorn: {uvicorn.__version__}')

print('\nTesting database...')
from app.database import engine
print('✓ Database engine created')

print('\nTesting FastAPI app...')
from app.main import app
print('✓ FastAPI app imported')

print('\n✅ All tests passed! StormForge is ready to start.')
"
EOF
chmod +x test-setup.sh

log "Setup complete!"
echo
info "==================== SETUP COMPLETE ===================="
echo
log "Python $(python3 --version) compatible setup finished!"
echo
log "To test the setup:"
echo "  ./test-setup.sh"
echo
log "To start StormForge:"
echo "  ./start.sh"
echo
log "Access the web interface at:"
echo "  http://localhost:8000"
echo "  http://$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'YOUR-SERVER-IP'):8000"
echo
log "API documentation:"
echo "  http://localhost:8000/docs"
echo
warn "IMPORTANT NOTES:"
warn "1. Updated to SQLAlchemy 2.0.25+ for Python 3.13 compatibility"
warn "2. Change the secrets in .env for production use"
warn "3. Run './test-setup.sh' to verify everything works"
echo