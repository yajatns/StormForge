"""
Job model
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db.database import Base


class Job(Base):
    """Job model for hping3 traffic generation jobs"""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    
    # Relationships
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=True, index=True)
    
    # Job configuration
    targets = Column(JSON, nullable=False)  # List of target IPs/CIDRs
    target_group = Column(String(50))  # Optional target group name
    traffic_type = Column(String(20), nullable=False)  # tcp-syn, udp, icmp
    dst_port = Column(Integer)
    src_port = Column(Integer, default=0)
    pps = Column(Integer, nullable=False, default=10)
    packet_size = Column(Integer, nullable=False, default=64)
    ttl = Column(Integer, default=64)
    iface = Column(String(50))
    spoof_source = Column(Boolean, default=False)
    source_ip = Column(String(45))  # IPv4/IPv6 address
    payload = Column(Text)
    hping_options = Column(JSON, default=[])  # Additional hping3 options
    duration = Column(Integer, default=60)  # seconds, 0 = infinite
    dry_run = Column(Boolean, default=False)
    priority = Column(String(10), default="normal")  # low, normal, high
    tags = Column(JSON, default=[])  # List of tags
    
    # Execution state
    status = Column(String(20), default="queued", nullable=False, index=True)
    pid = Column(Integer)  # Process ID when running
    command = Column(Text)  # Generated hping3 command
    exit_code = Column(Integer)
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    queued_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Statistics
    packets_sent = Column(String, default="0")  # Use string for big numbers
    bytes_sent = Column(String, default="0")
    packets_received = Column(String, default="0")
    
    # Output and logs
    stdout_log = Column(Text)  # Captured stdout
    stderr_log = Column(Text)  # Captured stderr
    
    # Metadata
    client_ip = Column(String(45))  # IP of client that created job
    user_agent = Column(String(512))
    
    # Relationships
    user = relationship("User", back_populates="jobs")
    api_key = relationship("ApiKey", back_populates="jobs")

    def __repr__(self):
        return f"<Job(id={self.id}, name={self.name}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        """Check if job is in an active state"""
        return self.status in ["queued", "starting", "running", "stopping"]

    @property
    def is_completed(self) -> bool:
        """Check if job has completed (success or failure)"""
        return self.status in ["completed", "failed", "cancelled"]

    def to_dict(self):
        """Convert job to dictionary representation"""
        return {
            "job_id": self.id,
            "name": self.name,
            "status": self.status,
            "command": self.command,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "user_id": self.user_id,
            "targets": self.targets,
            "traffic_type": self.traffic_type,
            "pps": self.pps,
            "duration": self.duration,
            "dry_run": self.dry_run,
            "priority": self.priority,
            "tags": self.tags,
            "packets_sent": int(self.packets_sent) if self.packets_sent else 0,
            "bytes_sent": int(self.bytes_sent) if self.bytes_sent else 0,
            "error_message": self.error_message
        }