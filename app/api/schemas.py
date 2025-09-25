"""
Common API schemas and models
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum
import uuid


class TrafficType(str, Enum):
    """Supported traffic types"""
    TCP_SYN = "tcp-syn"
    UDP = "udp"  
    ICMP = "icmp"


class JobStatus(str, Enum):
    """Job execution status"""
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Job priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class UserRole(str, Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    OPERATOR = "operator"
    READ_ONLY = "read_only"


# Request/Response Schemas
class JobCreateRequest(BaseModel):
    """Job creation request schema"""
    name: str = Field(..., min_length=1, max_length=100)
    targets: List[str] = Field(..., min_items=1, max_items=1000)
    target_group: Optional[str] = None
    traffic_type: TrafficType
    dst_port: Optional[int] = Field(None, ge=1, le=65535)
    src_port: Optional[int] = Field(0, ge=0, le=65535)
    pps: int = Field(10, ge=1, le=10000)
    packet_size: int = Field(64, ge=1, le=65507)
    ttl: int = Field(64, ge=1, le=255)
    iface: Optional[str] = None
    spoof_source: bool = False
    source_ip: Optional[str] = None
    payload: Optional[str] = None
    hping_options: List[str] = Field(default_factory=list)
    duration: int = Field(60, ge=0, le=86400)  # Max 24 hours
    dry_run: bool = False
    priority: JobPriority = JobPriority.NORMAL
    tags: List[str] = Field(default_factory=list, max_items=10)

    @validator('targets')
    def validate_targets(cls, v):
        """Validate target format"""
        if not v:
            raise ValueError('At least one target must be specified')
        return v

    @validator('hping_options')
    def validate_hping_options(cls, v):
        """Validate hping3 options for safety"""
        allowed_options = {
            '--fast', '--faster', '--flood',
            '-V', '--verbose', '-q', '--quiet',
            '--baseport', '--destport', '--keep'
        }
        for option in v:
            if not any(option.startswith(allowed) for allowed in allowed_options):
                raise ValueError(f'Hping option not allowed: {option}')
        return v


class JobResponse(BaseModel):
    """Job response schema"""
    job_id: str
    name: str
    status: JobStatus
    command: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    user_id: str
    targets: List[str]
    traffic_type: TrafficType
    pps: int
    duration: int
    dry_run: bool
    priority: JobPriority
    tags: List[str]
    packets_sent: int = 0
    bytes_sent: int = 0
    error_message: Optional[str] = None


class JobStopRequest(BaseModel):
    """Job stop request schema"""
    force: bool = False
    reason: Optional[str] = None


class JobListResponse(BaseModel):
    """Job list response schema"""
    jobs: List[JobResponse]
    total: int
    page: int
    per_page: int


class TargetGroupRequest(BaseModel):
    """Target group creation/update request"""
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    targets: List[str] = Field(..., min_items=1)
    enabled: bool = True


class TargetGroupResponse(BaseModel):
    """Target group response schema"""
    id: str
    name: str
    description: Optional[str]
    targets: List[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class AllowlistEntry(BaseModel):
    """Allowlist/denylist entry"""
    cidr: str
    description: Optional[str] = None
    enabled: bool = True


class QuotaSettings(BaseModel):
    """User/API key quota settings"""
    max_pps: int = Field(100, ge=1, le=10000)
    max_concurrent_jobs: int = Field(5, ge=1, le=50)
    max_job_duration: int = Field(3600, ge=60, le=86400)


class UserCreateRequest(BaseModel):
    """User creation request"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.OPERATOR
    quotas: QuotaSettings = Field(default_factory=QuotaSettings)


class UserResponse(BaseModel):
    """User response schema"""
    id: str
    username: str
    email: str
    role: UserRole
    enabled: bool
    created_at: datetime
    last_login: Optional[datetime]
    quotas: QuotaSettings


class ApiKeyCreateRequest(BaseModel):
    """API key creation request"""
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = Field(default_factory=lambda: ["jobs:read", "jobs:write"])
    expires_in_days: int = Field(365, ge=1, le=3650)
    quotas: QuotaSettings = Field(default_factory=QuotaSettings)


class ApiKeyResponse(BaseModel):
    """API key response schema"""
    id: str
    name: str
    key: Optional[str] = None  # Only returned on creation
    scopes: List[str]
    enabled: bool
    created_at: datetime
    expires_at: datetime
    last_used: Optional[datetime]
    quotas: QuotaSettings


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    """Login request schema"""
    username: str
    password: str


class MetricsResponse(BaseModel):
    """Metrics response schema"""
    jobs_total: int
    jobs_running: int
    jobs_completed: int
    jobs_failed: int
    packets_sent_total: int
    bytes_sent_total: int
    users_total: int
    api_keys_total: int


class WebSocketMessage(BaseModel):
    """WebSocket message schema"""
    type: str
    job_id: Optional[str] = None
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AuditLogResponse(BaseModel):
    """Audit log entry response"""
    id: str
    timestamp: datetime
    user_id: Optional[str]
    api_key_id: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]


# Error response schemas
class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationErrorResponse(BaseModel):
    """Validation error response"""
    error: str = "validation_error"
    message: str
    errors: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.utcnow)