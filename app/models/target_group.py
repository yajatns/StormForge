"""
Target group model
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
import uuid

from app.db.database import Base


class TargetGroup(Base):
    """Target group model for managing collections of targets"""
    __tablename__ = "target_groups"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    targets = Column(JSON, nullable=False)  # List of IPs/CIDRs
    enabled = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String)  # User ID who created this group
    
    # Usage statistics
    usage_count = Column(String, default="0")  # Times this group has been used
    last_used = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<TargetGroup(id={self.id}, name={self.name})>"


class AllowlistEntry(Base):
    """Allowlist/denylist entries for network access control"""
    __tablename__ = "allowlist_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    cidr = Column(String(45), nullable=False, unique=True, index=True)
    description = Column(Text)
    entry_type = Column(String(10), nullable=False, default="allow")  # allow, deny
    enabled = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String)  # User ID who created this entry
    
    # Usage tracking
    match_count = Column(String, default="0")  # Times this rule has been matched
    last_matched = Column(DateTime(timezone=True))

    def __repr__(self):
        return f"<AllowlistEntry(id={self.id}, cidr={self.cidr}, type={self.entry_type})>"