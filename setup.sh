#!/bin/bash

# StormForge Traffic Orchestrator - Linux Setup Script
# Run this script as a regular user (not root)

set -e  # Exit on any error

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

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    error "Please run this script as a regular user, not as root!"
    error "The script will use sudo when necessary."
    exit 1
fi

PROJECT_DIR=$(pwd)
USER_HOME=$HOME

log "Starting StormForge Traffic Orchestrator setup..."
info "Project directory: $PROJECT_DIR"
info "User: $(whoami)"
info "Home directory: $USER_HOME"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VERSION=$VERSION_ID
else
    error "Cannot detect OS version"
    exit 1
fi

log "Detected OS: $OS $VERSION"

# Update system packages
log "Updating system packages..."
case $OS in
    "ubuntu"|"debian")
        sudo apt update
        sudo apt upgrade -y
        PACKAGE_MANAGER="apt"
        ;;
    "centos"|"rhel"|"fedora")
        if command_exists dnf; then
            sudo dnf update -y
            PACKAGE_MANAGER="dnf"
        else
            sudo yum update -y
            PACKAGE_MANAGER="yum"
        fi
        ;;
    *)
        warn "Unsupported OS: $OS. Attempting to continue..."
        ;;
esac

# Install system dependencies
log "Installing system dependencies..."
case $OS in
    "ubuntu"|"debian")
        sudo apt install -y \
            python3 \
            python3-pip \
            python3-venv \
            hping3 \
            curl \
            wget \
            git \
            sqlite3 \
            build-essential \
            pkg-config \
            libcairo2-dev \
            libgirepository1.0-dev
        ;;
    "centos"|"rhel"|"fedora")
        if [ "$PACKAGE_MANAGER" = "dnf" ]; then
            sudo dnf install -y \
                python3 \
                python3-pip \
                python3-virtualenv \
                hping3 \
                curl \
                wget \
                git \
                sqlite \
                gcc \
                gcc-c++ \
                make \
                pkg-config \
                cairo-devel \
                gobject-introspection-devel
        else
            sudo yum install -y \
                python3 \
                python3-pip \
                python3-virtualenv \
                hping3 \
                curl \
                wget \
                git \
                sqlite \
                gcc \
                gcc-c++ \
                make \
                pkg-config \
                cairo-devel \
                gobject-introspection-devel
        fi
        ;;
esac

# Check if hping3 is installed and has proper capabilities
log "Checking hping3 installation..."
if ! command_exists hping3; then
    error "hping3 is not installed or not in PATH"
    exit 1
fi

HPING3_PATH=$(which hping3)
log "hping3 found at: $HPING3_PATH"

# Set capabilities for hping3 (requires sudo)
log "Setting capabilities for hping3..."
sudo setcap cap_net_raw=eip $HPING3_PATH
log "Capabilities set for hping3"

# Install Node.js if not present
if ! command_exists node; then
    log "Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
    case $OS in
        "ubuntu"|"debian")
            sudo apt install -y nodejs
            ;;
        "centos"|"rhel"|"fedora")
            if [ "$PACKAGE_MANAGER" = "dnf" ]; then
                sudo dnf install -y nodejs npm
            else
                sudo yum install -y nodejs npm
            fi
            ;;
    esac
else
    log "Node.js is already installed: $(node --version)"
fi

# Verify Node.js and npm
if ! command_exists npm; then
    error "npm is not installed"
    exit 1
fi

log "Node.js version: $(node --version)"
log "npm version: $(npm --version)"

# Create virtual environment for Python backend
log "Setting up Python virtual environment..."
cd "$PROJECT_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    log "Created Python virtual environment"
else
    log "Python virtual environment already exists"
fi

# Activate virtual environment and install Python dependencies
log "Installing Python dependencies..."
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install backend dependencies
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    log "Installed Python requirements"
else
    warn "requirements.txt not found, installing basic dependencies"
    pip install fastapi uvicorn sqlalchemy alembic python-jose bcrypt python-multipart websockets
fi

# Setup frontend dependencies
log "Setting up frontend dependencies..."
cd frontend

if [ ! -d "node_modules" ]; then
    npm install
    log "Installed frontend dependencies"
else
    log "Frontend dependencies already installed"
fi

# Build frontend for production
log "Building frontend for production..."
npm run build
cd ..

# Create necessary directories
log "Creating application directories..."
mkdir -p logs
mkdir -p data
mkdir -p config

# Create environment file if it doesn't exist
if [ ! -f ".env" ]; then
    log "Creating environment configuration..."
    cat > .env << EOF
# Database Configuration
DATABASE_URL=sqlite:///./data/orchestrator.db

# Security Configuration
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application Configuration
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Hping3 Configuration
HPING3_PATH=/usr/sbin/hping3
MAX_CONCURRENT_JOBS=10
DEFAULT_TIMEOUT=30

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=./logs/orchestrator.log

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# CORS Configuration
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
EOF
    log "Created .env file with default configuration"
else
    log ".env file already exists"
fi

# Initialize database
log "Initializing database..."
source venv/bin/activate

# Create initial database and tables
python3 -c "
from app.database import engine, Base
from app.models import User, Job, TargetGroup, APIKey, AuditLog, Quota
Base.metadata.create_all(bind=engine)
print('Database tables created')
"

# Create default admin user
log "Creating default admin user..."
python3 -c "
import asyncio
from app.database import get_db_session
from app.crud.user import create_user
from app.schemas.user import UserCreate
from app.auth.security import get_password_hash

async def create_admin():
    async with get_db_session() as db:
        admin_user = UserCreate(
            username='admin',
            email='admin@localhost',
            password='admin123',
            role='admin',
            is_active=True
        )
        try:
            user = await create_user(db, admin_user)
            print(f'Created admin user: {user.username}')
        except Exception as e:
            print(f'Admin user might already exist: {e}')

asyncio.run(create_admin())
"

# Create systemd service file
log "Creating systemd service..."
sudo tee /etc/systemd/system/stormforge.service > /dev/null << EOF
[Unit]
Description=StormForge Traffic Orchestrator
After=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$PROJECT_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PROJECT_DIR/logs $PROJECT_DIR/data
AmbientCapabilities=CAP_NET_RAW

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable stormforge.service

log "Systemd service created and enabled"

# Set proper permissions
log "Setting file permissions..."
chmod +x setup.sh
chmod 755 logs data config
chmod 600 .env

# Create startup script
log "Creating startup script..."
cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
EOF
chmod +x start.sh

# Create stop script
log "Creating stop script..."
cat > stop.sh << 'EOF'
#!/bin/bash
sudo systemctl stop stormforge.service
EOF
chmod +x stop.sh

# Display final instructions
log "Setup completed successfully!"
echo
info "==================== SETUP COMPLETE ===================="
echo
log "Default admin credentials:"
echo "  Username: admin"
echo "  Password: admin123"
echo
log "To start the service:"
echo "  sudo systemctl start stormforge.service"
echo
log "To start in development mode:"
echo "  ./start.sh"
echo
log "To check service status:"
echo "  sudo systemctl status stormforge.service"
echo
log "To view logs:"
echo "  sudo journalctl -u stormforge.service -f"
echo
log "Web interface will be available at:"
echo "  http://localhost:8000"
echo "  http://$(hostname -I | awk '{print $1}'):8000"
echo
log "API documentation available at:"
echo "  http://localhost:8000/docs"
echo
warn "IMPORTANT SECURITY NOTES:"
warn "1. Change the default admin password immediately"
warn "2. Review and customize the .env file"
warn "3. Consider setting up SSL/TLS for production use"
warn "4. Review firewall settings and network access"
echo
info "==================== NEXT STEPS ===================="
log "1. Review configuration in .env file"
log "2. Start the service: sudo systemctl start hping3-orchestrator.service"
log "3. Access web interface and change admin password"
log "4. Configure target allowlists and security policies"
echo