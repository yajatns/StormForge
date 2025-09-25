# StormForge Traffic Orchestrator

A secure, web-based tool for orchestrating controlled hping3 traffic generation with comprehensive monitoring, RBAC, and safety controls.

## Features

- **Secure by Default**: Comprehensive allowlist/denylist system, quota enforcement, and safety controls
- **REST API**: Complete API for job management with OpenAPI documentation
- **Web UI**: React-based interface for creating and monitoring jobs
- **Real-time Updates**: WebSocket support for live job status updates
- **RBAC**: Role-based access control with admin, operator, and read-only roles
- **Audit Trail**: Complete logging of all actions and API calls
- **Metrics**: Prometheus metrics export for monitoring
- **Multi-target Support**: Target single IPs, CIDR ranges, or predefined groups
- **Traffic Types**: Support for TCP SYN, UDP, and ICMP traffic
- **Dry Run Mode**: Test job configurations without executing

## Quick Start

### Prerequisites

- Python 3.9+
- hping3 installed on the system
- Docker (optional, for containerized deployment)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd FunTrafficGen
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy and configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Install and setup frontend (optional):
```bash
cd frontend
npm install
cd ..
```

6. Initialize database:
```bash
python -c "
import asyncio
from app.db.database import init_db
asyncio.run(init_db())
"
```

6. Create admin user:
```bash
python -c "
import asyncio
from app.db.database import AsyncSessionLocal
from app.models.user import User
from app.auth.security import hash_password
from datetime import datetime

async def create_admin():
    async with AsyncSessionLocal() as db:
        admin = User(
            username='admin',
            email='admin@example.com',
            hashed_password=hash_password('admin123'),
            role='admin',
            created_at=datetime.utcnow()
        )
        db.add(admin)
        await db.commit()
        print('Admin user created: admin/admin123')

asyncio.run(create_admin())
"
```

7. Start the backend API:
```bash
python app/main.py
```

8. Start the frontend (in a new terminal):
```bash
cd frontend
npm start
```

The API will be available at `http://localhost:8000` with documentation at `http://localhost:8000/docs`.
The web interface will be available at `http://localhost:3000`.

## Configuration

Key configuration options in `.env`:

```bash
# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Database
DATABASE_URL=sqlite+aiosqlite:///./hping_orchestrator.db

# Safety Limits
DEFAULT_MAX_PPS=100
DEFAULT_MAX_CONCURRENT_JOBS=5
DEFAULT_MAX_JOB_DURATION=3600

# Network Safety
ALLOWED_BROADCAST_RANGES=["224.0.0.0/8", "ff00::/8"]
```

## API Usage

### Authentication

Get JWT token:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

### Create Job

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Job",
    "targets": ["192.168.1.100"],
    "traffic_type": "tcp-syn",
    "dst_port": 80,
    "pps": 10,
    "duration": 60,
    "dry_run": true
  }'
```

### List Jobs

```bash
curl -X GET "http://localhost:8000/api/v1/jobs/" \
  -H "Authorization: Bearer <token>"
```

### WebSocket Real-time Updates

The system provides WebSocket endpoints for real-time job monitoring and system events:

#### Global System Monitor

Connect to receive all system events (admin/operator/read-only access):
```javascript
// Connect with JWT token
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/monitor?token=<your_jwt_token>');

// Connect with API key
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/monitor?api_key=<your_api_key>');

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    console.log('System event:', message);
    
    switch(message.type) {
        case 'job_status_update':
            // Handle job status change
            console.log(`Job ${message.job_id} is now ${message.data.status}`);
            break;
        case 'system_event':
            // Handle system events (job creation, etc.)
            console.log(`System event: ${message.event_type}`);
            break;
        case 'admin_action':
            // Handle admin actions (admin only)
            console.log(`Admin action: ${message.action}`);
            break;
    }
};

// Keep connection alive
setInterval(() => {
    ws.send(JSON.stringify({type: 'ping'}));
}, 30000);
```

#### Job-specific Monitor

Monitor a specific job in real-time:
```javascript
const jobId = 'your-job-id-here';
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/job/${jobId}?token=<your_jwt_token>`);

ws.onmessage = function(event) {
    const message = JSON.parse(event.data);
    if (message.type === 'job_status_update') {
        const job = message.data;
        console.log(`Job progress: ${job.progress}%`);
        console.log(`Packets sent: ${job.packets_sent}`);
        console.log(`Status: ${job.status}`);
    }
};
```

#### WebSocket Message Types

- `connection_established`: Sent when connection is successful
- `job_status_update`: Real-time job status and progress updates
- `system_event`: System-wide events (job creation, completion, etc.)
- `admin_action`: Administrative actions (admin users only)
- `pong`: Response to ping keepalive messages

## Security Considerations

### Network Permissions

hping3 requires raw socket permissions. Options:

1. **Recommended**: Grant CAP_NET_RAW capability:
```bash
sudo setcap cap_net_raw+ep $(which hping3)
```

2. **Alternative**: Run application as root (not recommended for production)

### Safety Features

- **Allowlist/Denylist**: Admin-managed IP/CIDR filtering
- **Quotas**: Per-user limits on PPS, concurrent jobs, and duration  
- **Command Sanitization**: All hping3 commands built safely without shell injection
- **Dry Run Mode**: Test configurations without execution
- **Emergency Stop**: Global kill switch for all jobs
- **Audit Logging**: Complete trail of all actions

### Default Blocked Ranges

- `127.0.0.0/8` (Loopback)
- `169.254.0.0/16` (Link-local)
- `224.0.0.0/4` (Multicast, unless explicitly allowed)
- `240.0.0.0/4` (Reserved)

## Deployment

### Docker

```bash
# Build image
docker build -f docker/Dockerfile -t hping-orchestrator .

# Run with docker-compose
docker-compose -f docker/docker-compose.yml up -d
```

### Systemd Service

```bash
# Copy service file
sudo cp scripts/hping-orchestrator.service /etc/systemd/system/

# Enable and start
sudo systemctl enable hping-orchestrator
sudo systemctl start hping-orchestrator
```

## Monitoring

### Prometheus Metrics

Available at `/api/v1/metrics/prometheus`:

- `hping_jobs_total{status, traffic_type}` - Total jobs by status and type
- `hping_jobs_active` - Currently active jobs  
- `hping_packets_sent_total{traffic_type}` - Total packets sent
- `hping_bytes_sent_total{traffic_type}` - Total bytes sent
- `hping_job_duration_seconds{status}` - Job duration histogram

### Health Checks

- `/health` - Basic health check
- `/api/v1/metrics/health` - Detailed system status

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock

# Run tests
pytest tests/
```

### Code Quality

```bash
# Format code
black app/ tests/

# Type checking  
mypy app/

# Linting
flake8 app/ tests/
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web UI        │    │   REST API       │    │  Job Manager    │
│   (React)       │◄──►│   (FastAPI)      │◄──►│                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                         │
                                ▼                         ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │    Database      │    │  Job Worker     │
                       │   (SQLAlchemy)   │    │  (hping3 proc)  │
                       └──────────────────┘    └─────────────────┘
```

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit pull request

## License

[License information here]

## Security Notice

This tool is designed for authorized network testing only. Users must:

- Have explicit permission for all target networks
- Comply with applicable laws and regulations  
- Use responsibly and ethically
- Not use for malicious purposes

The tool includes safety features but cannot prevent misuse. Administrators are responsible for proper configuration and access control.

## Support

- Documentation: `/docs` endpoint when running
- Issues: [GitHub Issues]
- Security Issues: Contact maintainers privately

## Changelog

### v1.0.0
- Initial release
- Core hping3 orchestration functionality
- REST API with OpenAPI documentation
- Web UI for job management
- RBAC and security features
- Prometheus metrics
- Docker deployment support