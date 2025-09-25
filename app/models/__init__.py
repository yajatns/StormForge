"""
Models package initialization
"""

# Import all models to ensure they are registered with SQLAlchemy
from app.models.user import User, ApiKey
from app.models.job import Job
from app.models.target_group import TargetGroup, AllowlistEntry
from app.models.audit_log import AuditLog

__all__ = [
    "User",
    "ApiKey", 
    "Job",
    "TargetGroup",
    "AllowlistEntry",
    "AuditLog"
]