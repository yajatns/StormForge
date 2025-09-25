"""
Audit log model
"""

from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db.database import Base


class AuditLog(Base):
    """Audit log model for tracking all system actions"""
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Who performed the action
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=True, index=True)
    
    # What action was performed
    action = Column(String(50), nullable=False, index=True)  # create, update, delete, start, stop, etc.
    resource_type = Column(String(50), nullable=False, index=True)  # job, user, target_group, etc.
    resource_id = Column(String, index=True)  # ID of the resource affected
    
    # Action details
    details = Column(JSON)  # Additional context about the action
    
    # Request metadata
    ip_address = Column(String(45))  # Client IP address
    user_agent = Column(String(512))  # Client user agent
    request_id = Column(String(50))  # Request tracking ID
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    api_key = relationship("ApiKey", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, resource_type={self.resource_type})>"

    def to_dict(self):
        """Convert audit log to dictionary representation"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "user_id": self.user_id,
            "api_key_id": self.api_key_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details or {},
            "ip_address": self.ip_address,
            "user_agent": self.user_agent
        }