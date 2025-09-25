"""
User model
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.database import Base


class User(Base):
    """User model for authentication and RBAC"""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="operator")  # admin, operator, read_only
    enabled = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Quotas (stored as JSON)
    quotas = Column(JSON, nullable=False, default={
        "max_pps": 100,
        "max_concurrent_jobs": 5,
        "max_job_duration": 3600
    })
    
    # Profile info
    full_name = Column(String(255))
    department = Column(String(100))
    
    # Relationships
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"


class ApiKey(Base):
    """API key model for programmatic access"""
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    scopes = Column(JSON, nullable=False)  # List of scopes like ["jobs:read", "jobs:write"]
    enabled = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_used = Column(DateTime(timezone=True))
    
    # Quotas (stored as JSON)
    quotas = Column(JSON, nullable=False, default={
        "max_pps": 100,
        "max_concurrent_jobs": 5,
        "max_job_duration": 3600
    })
    
    # Usage tracking
    total_requests = Column(String, default="0")  # Use string for big numbers
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    jobs = relationship("Job", back_populates="api_key")
    audit_logs = relationship("AuditLog", back_populates="api_key")

    def __repr__(self):
        return f"<ApiKey(id={self.id}, name={self.name}, user_id={self.user_id})>"