# StormForge Traffic Orchestrator - Linux Deployment Guide

A secure, web-based traffic generation tool for network testing and monitoring using hping3.

## Quick Start

### Prerequisites

- Linux system (Ubuntu 18.04+, CentOS 7+, RHEL 7+, Fedora 30+)
- Python 3.8+ 
- Node.js 16+ (will be installed automatically)
- hping3 package (will be installed automatically)
- Sudo access for initial setup

### Automated Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url> ~/StormForge
   cd ~/StormForge
   ```

2. **Run the setup script:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Start the service:**
   ```bash
   sudo systemctl start hping3-orchestrator.service
   ```

4. **Access the web interface:**
   - Open http://localhost:8000 in your browser
   - Default credentials: `admin` / `admin123`
   - **Change the password immediately!**

## Manual Setup

If you prefer manual installation or the automated script fails:

### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv hping3 curl wget git sqlite3 build-essential
```

**CentOS/RHEL/Fedora:**
```bash
sudo dnf install -y python3 python3-pip python3-virtualenv hping3 curl wget git sqlite gcc gcc-c++ make
```

### 2. Install Node.js
```bash
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs  # Ubuntu/Debian
# OR
sudo dnf install -y nodejs npm  # Fedora/CentOS
```

### 3. Setup Python Environment
```bash
cd ~/StormForge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Setup Frontend
```bash
cd frontend
npm install
npm run build
cd ..
```

### 5. Configure hping3 Capabilities
```bash
sudo setcap cap_net_raw=eip $(which hping3)
```

### 6. Initialize Database
```bash
source venv/bin/activate
python3 -c "
from app.database import engine, Base
from app.models import User, Job, TargetGroup, APIKey, AuditLog, Quota
Base.metadata.create_all(bind=engine)
"
```

### 7. Create Environment Configuration
```bash
cp .env.example .env
# Edit .env with your preferred settings
```

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Clone and enter directory
git clone <repository-url> ~/StormForge
cd ~/StormForge

# Start with Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f stormforge
```

### Using Docker directly

```bash
# Build image
docker build -t stormforge .

# Run container
docker run -d \
  --name stormforge \
  --cap-add=NET_RAW \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  stormforge
```

## Configuration

### Environment Variables (.env file)

```bash
# Database Configuration
DATABASE_URL=sqlite:///./data/orchestrator.db

# Security Configuration  
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here
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
```

### Security Configuration

1. **Change Default Credentials:**
   - Login with admin/admin123
   - Go to Profile settings
   - Change password immediately

2. **Review Target Allowlists:**
   - Configure allowed IP ranges in Admin panel
   - Set up target groups for organized access
   - Enable IP validation and rate limiting

3. **Configure User Roles:**
   - Admin: Full system access
   - Operator: Create and manage jobs
   - Read-only: View jobs and results only

## System Service Management

### Start/Stop/Status Commands
```bash
# Start service
sudo systemctl start hping3-orchestrator.service

# Stop service  
sudo systemctl stop hping3-orchestrator.service

# Restart service
sudo systemctl restart hping3-orchestrator.service

# Check status
sudo systemctl status hping3-orchestrator.service

# Enable auto-start on boot
sudo systemctl enable hping3-orchestrator.service

# View logs
sudo journalctl -u hping3-orchestrator.service -f
```

### Development Mode
```bash
# Run in development with auto-reload
cd ~/Stormforge
./start.sh
```

## API Usage

### Authentication
```bash
# Get access token
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"

# Use token in subsequent requests
curl -X GET "http://localhost:8000/jobs/" \
  -H "Authorization: Bearer <your-token>"
```

### Create Job
```bash
curl -X POST "http://localhost:8000/jobs/" \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Job",
    "targets": ["192.168.1.1"],
    "hping_options": {
      "count": 10,
      "interval": 1000,
      "packet_size": 64
    }
  }'
```

## Monitoring and Logs

### Application Logs
```bash
# View application logs
tail -f logs/orchestrator.log

# View systemd logs
sudo journalctl -u hping3-orchestrator.service -f

# View specific log level
grep "ERROR" logs/orchestrator.log
```

### Health Check
```bash
# Check application health
curl http://localhost:8000/health

# Check metrics endpoint
curl http://localhost:8000/metrics
```

## Troubleshooting

### Common Issues

**1. Permission Denied for hping3:**
```bash
# Check capabilities
getcap $(which hping3)

# Reset capabilities
sudo setcap cap_net_raw=eip $(which hping3)
```

**2. Port Already in Use:**
```bash
# Check what's using port 8000
sudo lsof -i :8000

# Kill process using port
sudo kill -9 <PID>
```

**3. Database Locked:**
```bash
# Check database permissions
ls -la data/orchestrator.db

# Fix permissions
sudo chown $(whoami):$(whoami) data/orchestrator.db
```

**4. Frontend Build Issues:**
```bash
# Clean and rebuild
cd frontend
rm -rf node_modules build
npm install
npm run build
```

### Logs and Debugging

**Enable Debug Mode:**
```bash
# Edit .env file
DEBUG=true
LOG_LEVEL=DEBUG

# Restart service
sudo systemctl restart hping3-orchestrator.service
```

**Check Service Dependencies:**
```bash
# Verify hping3
hping3 --version

# Verify Python environment
source venv/bin/activate
python3 -c "import fastapi, sqlalchemy; print('Dependencies OK')"

# Verify Node.js
node --version
npm --version
```

## Security Considerations

### Network Security
- Configure firewall rules to limit access
- Use reverse proxy (nginx/apache) for SSL termination
- Enable rate limiting and DDoS protection

### Application Security
- Change default credentials immediately
- Use strong JWT secrets
- Configure proper user roles and permissions
- Enable audit logging
- Regularly update dependencies

### System Security
- Run service as non-root user
- Use minimal required capabilities
- Enable SELinux/AppArmor if available
- Regular security updates

## Performance Tuning

### System Resources
```bash
# Increase file limits for high job concurrency
echo "orchestrator soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "orchestrator hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Tune network parameters
echo "net.core.rmem_max = 16777216" | sudo tee -a /etc/sysctl.conf
echo "net.core.wmem_max = 16777216" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Application Settings
```bash
# Increase worker processes
MAX_CONCURRENT_JOBS=50

# Adjust timeouts
DEFAULT_TIMEOUT=60
```

## Backup and Recovery

### Database Backup
```bash
# Backup SQLite database
cp data/orchestrator.db data/orchestrator.db.backup.$(date +%Y%m%d)

# For PostgreSQL
pg_dump orchestrator > orchestrator_backup.sql
```

### Configuration Backup
```bash
# Backup entire configuration
tar -czf orchestrator_backup.tar.gz .env config/ data/ logs/
```

## Support

- **Documentation:** Available at http://localhost:8000/docs
- **API Reference:** Interactive docs at http://localhost:8000/redoc
- **Logs:** Check `logs/orchestrator.log` for application logs
- **System Logs:** Use `journalctl -u hping3-orchestrator.service`

## License

[Add your license information here]