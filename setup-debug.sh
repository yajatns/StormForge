#!/bin/bash

# StormForge Traffic Orchestrator - Linux Setup Script (Debug Version)
# Run this script as a regular user (not root)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

# Function to run command with error handling
safe_run() {
    local cmd="$1"
    local desc="$2"
    
    log "Running: $desc"
    info "Command: $cmd"
    
    if eval "$cmd"; then
        log "✓ Success: $desc"
        return 0
    else
        error "✗ Failed: $desc"
        error "Command failed: $cmd"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
        return 1
    fi
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    error "Please run this script as a regular user, not as root!"
    error "The script will use sudo when necessary."
    exit 1
fi

PROJECT_DIR=$(pwd)
USER_HOME=$HOME

log "Starting StormForge Traffic Orchestrator setup (Debug Mode)..."
info "Project directory: $PROJECT_DIR"
info "User: $(whoami)"
info "Home directory: $USER_HOME"

# Check prerequisites
log "Checking prerequisites..."

if ! command -v python3 >/dev/null 2>&1; then
    error "python3 is not installed!"
    exit 1
fi

if ! command -v pip3 >/dev/null 2>&1; then
    warn "pip3 not found, trying to install..."
    safe_run "sudo apt update && sudo apt install -y python3-pip" "Install pip3"
fi

log "Python3 version: $(python3 --version)"
log "Pip3 version: $(pip3 --version)"

# Create virtual environment
log "Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
    safe_run "python3 -m venv venv" "Create Python virtual environment"
else
    log "Python virtual environment already exists"
fi

# Activate virtual environment
log "Activating virtual environment..."
source venv/bin/activate || {
    error "Failed to activate virtual environment"
    exit 1
}

# Upgrade pip
safe_run "pip install --upgrade pip" "Upgrade pip"

# Install requirements with better error handling
log "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    safe_run "pip install -r requirements.txt" "Install Python requirements"
else
    warn "requirements.txt not found, installing basic dependencies"
    safe_run "pip install fastapi uvicorn sqlalchemy alembic python-jose bcrypt python-multipart websockets aiosqlite" "Install basic dependencies"
fi

# Check if app directory exists
if [ ! -d "app" ]; then
    error "app directory not found in $PROJECT_DIR"
    error "Make sure you're running this script from the StormForge project root"
    exit 1
fi

# Create necessary directories
log "Creating application directories..."
mkdir -p logs data config

# Create environment file if it doesn't exist
if [ ! -f ".env" ]; then
    log "Creating environment configuration..."
    cat > .env << 'EOF'
# Database Configuration
DATABASE_URL=sqlite:///./data/orchestrator.db

# Security Configuration
SECRET_KEY=dev-secret-key-change-in-production
JWT_SECRET_KEY=dev-jwt-secret-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application Configuration
DEBUG=true
HOST=0.0.0.0
PORT=8000

# Hping3 Configuration
HPING3_PATH=/usr/sbin/hping3
MAX_CONCURRENT_JOBS=10
DEFAULT_TIMEOUT=30

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=./logs/orchestrator.log
EOF
    log "Created .env file with default configuration"
else
    log ".env file already exists"
fi

# Test basic imports
log "Testing Python imports..."
python3 -c "
try:
    import fastapi
    import sqlalchemy
    import uvicorn
    print('✓ Core dependencies imported successfully')
except ImportError as e:
    print(f'✗ Import error: {e}')
    exit(1)
" || {
    error "Failed to import required Python modules"
    exit 1
}

# Initialize database with better error handling
log "Initializing database..."
python3 -c "
import sys
sys.path.append('.')

try:
    from app.database import engine, Base
    Base.metadata.create_all(bind=engine)
    print('✓ Database tables created successfully')
except Exception as e:
    print(f'✗ Database initialization failed: {e}')
    print('This might be OK if tables already exist')
"

# Create startup script
log "Creating startup script..."
cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
EOF
chmod +x start.sh

log "Setup completed!"
echo
info "==================== SETUP COMPLETE ===================="
echo
log "To start the application:"
echo "  ./start.sh"
echo
log "Web interface will be available at:"
echo "  http://localhost:8000"
echo
log "API documentation available at:"
echo "  http://localhost:8000/docs"
echo
warn "NOTES:"
warn "1. This is a debug setup - change secrets in .env for production"
warn "2. Make sure hping3 is installed: sudo apt install hping3"
warn "3. You may need to set capabilities: sudo setcap cap_net_raw=eip /usr/sbin/hping3"
echo