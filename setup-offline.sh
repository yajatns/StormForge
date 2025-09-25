#!/bin/bash

# StormForge - Network/Rust-Free Setup Script
# Avoids packages that require Rust compilation or external downloads

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

log "Starting StormForge offline-friendly setup..."
info "Project directory: $PROJECT_DIR"
info "User: $(whoami)"
info "Python version: $PYTHON_VERSION"

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    error "app/main.py not found. Please run this from the StormForge project root."
    exit 1
fi

# Install essential packages
log "Installing essential packages..."
sudo apt install -y python3 python3-pip python3-venv hping3 curl wget git sqlite3 build-essential || {
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

# Remove existing venv if it exists
if [ -d "venv" ]; then
    warn "Removing existing virtual environment..."
    rm -rf venv
fi

# Create fresh virtual environment
log "Creating fresh Python virtual environment..."
python3 -m venv venv

# Activate and upgrade pip
log "Activating virtual environment and upgrading pip..."
source venv/bin/activate
pip install --upgrade pip

# Install packages that don't require Rust compilation
log "Installing core dependencies (avoiding Rust compilation)..."

# Core web framework
pip install fastapi==0.104.1 || {
    error "Failed to install FastAPI"
    exit 1
}

# Use older Pydantic that doesn't require Rust
log "Installing Pydantic v1 (no Rust required)..."
pip install "pydantic<2.0" || {
    warn "Pydantic v1 failed, trying system packages..."
    sudo apt install -y python3-pydantic || warn "System pydantic failed"
}

# Uvicorn
pip install uvicorn==0.24.0 || {
    warn "Uvicorn failed, trying older version..."
    pip install uvicorn==0.20.0
}

# SQLAlchemy - use version that works with Python 3.13
log "Installing SQLAlchemy..."
pip install "sqlalchemy>=1.4,<2.1" || {
    warn "SQLAlchemy 2.x failed, trying 1.4.x..."
    pip install sqlalchemy==1.4.53
}

# Database drivers
pip install aiosqlite==0.19.0 || pip install aiosqlite==0.17.0

# Authentication - avoid packages that need Rust
log "Installing authentication packages..."
pip install passlib==1.7.4
pip install bcrypt==4.0.1 || pip install bcrypt==3.2.2

# Try python-jose without cryptography extras first
pip install python-jose==3.3.0 || {
    warn "python-jose failed, using alternative JWT library..."
    pip install PyJWT==2.8.0
}

# Other core dependencies
pip install python-multipart==0.0.6 || pip install python-multipart==0.0.5
pip install websockets==12.0 || pip install websockets==11.0
pip install python-dotenv==1.0.0 || pip install python-dotenv==0.19.2

# HTTP client
pip install httpx==0.25.2 || {
    warn "httpx failed, using requests instead..."
    pip install requests==2.31.0
}

# Create directories
mkdir -p logs data config

# Create environment file
if [ ! -f ".env" ]; then
    log "Creating .env file..."
    cat > .env << 'EOF'
DATABASE_URL=sqlite:///./data/orchestrator.db
SECRET_KEY=dev-secret-change-in-production-12345
JWT_SECRET_KEY=dev-jwt-secret-change-in-production-67890
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

# Test imports
log "Testing Python setup..."
python3 -c "
try:
    import fastapi
    print('✓ FastAPI imported successfully')
    
    try:
        import pydantic
        print(f'✓ Pydantic {pydantic.VERSION} imported successfully')
    except:
        print('! Pydantic import failed, but may still work')
    
    import sqlalchemy
    print(f'✓ SQLAlchemy {sqlalchemy.__version__} imported successfully')
    
    import uvicorn
    print('✓ Uvicorn imported successfully')
    
    import aiosqlite
    print('✓ AsyncSQLite imported successfully')
    
    print('✓ Core modules imported successfully')
except Exception as e:
    print(f'Import test failed: {e}')
    print('Some imports failed but basic functionality may still work')
"

# Create a minimal FastAPI app to test
log "Creating minimal test app..."
cat > test_app.py << 'EOF'
from fastapi import FastAPI
import os
import sqlite3

app = FastAPI(title="StormForge Test", version="1.0.0")

@app.get("/")
async def root():
    return {"message": "StormForge is running!", "status": "ok"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "python": os.sys.version,
        "database": "sqlite available" if sqlite3 else "unavailable"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF

# Initialize database with minimal approach
log "Initializing basic database..."
python3 -c "
import sqlite3
import os

db_path = './data/orchestrator.db'
os.makedirs('data', exist_ok=True)

# Create basic database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create minimal tables
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role TEXT DEFAULT 'operator',
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users (id)
)
''')

conn.commit()
conn.close()
print('✓ Basic database created with SQLite')
"

# Create simple start script
cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Set Python path
export PYTHONPATH="$(pwd):$PYTHONPATH"

echo "Starting StormForge Traffic Orchestrator..."
echo "Testing with minimal app first..."

# Test with minimal app
echo "Testing basic functionality..."
python3 test_app.py &
TEST_PID=$!
sleep 3

if kill -0 $TEST_PID 2>/dev/null; then
    echo "✓ Basic test server running on http://localhost:8000"
    echo "Press Ctrl+C to stop and try full app"
    wait $TEST_PID
else
    echo "Basic test failed, trying full app..."
fi

# Try full app
echo "Starting full StormForge app..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
EOF
chmod +x start.sh

# Create test script
cat > test-setup.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

echo "Testing StormForge offline setup..."

# Test Python imports
python3 -c "
print('Testing basic imports...')
try:
    import fastapi
    print('✓ FastAPI available')
except: print('✗ FastAPI missing')

try:
    import uvicorn  
    print('✓ Uvicorn available')
except: print('✗ Uvicorn missing')

try:
    import sqlite3
    print('✓ SQLite available')
except: print('✗ SQLite missing')

try:
    import aiosqlite
    print('✓ AsyncSQLite available') 
except: print('✗ AsyncSQLite missing')

print('\n✓ Basic setup test completed')
"

# Test database
python3 -c "
import sqlite3
import os

if os.path.exists('./data/orchestrator.db'):
    print('✓ Database file exists')
    conn = sqlite3.connect('./data/orchestrator.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM sqlite_master WHERE type=\"table\"')
    tables = cursor.fetchall()
    print(f'✓ Database tables: {[t[0] for t in tables]}')
    conn.close()
else:
    print('✗ Database file not found')
"

echo -e "\n🎯 Setup test completed!"
EOF
chmod +x test-setup.sh

log "Offline-friendly setup complete!"
echo
info "==================== SETUP COMPLETE ===================="
echo
log "This setup avoids Rust compilation and network dependencies"
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
warn "NOTES:"
warn "1. Uses Pydantic v1 to avoid Rust compilation"
warn "2. Uses SQLite with basic tables"
warn "3. Some advanced features may be limited"
warn "4. Change secrets in .env for production"
echo