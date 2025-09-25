"""
Admin API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from datetime import datetime, timedelta
import structlog

from app.db.database import get_db
from app.models.user import User, ApiKey
from app.models.job import Job
from app.models.audit_log import AuditLog
from app.api.schemas import (
    UserResponse, QuotaSettings, AuditLogResponse
)
from app.auth import RequireAdmin, AuthContext
from app.jobs import job_manager

logger = structlog.get_logger()
router = APIRouter()


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin,
    limit: int = 100,
    offset: int = 0
):
    """List all users (admin only)"""
    
    try:
        result = await db.execute(
            select(User)
            .order_by(desc(User.created_at))
            .limit(limit)
            .offset(offset)
        )
        users = result.scalars().all()
        
        return [
            UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                role=user.role,
                enabled=user.enabled,
                created_at=user.created_at,
                last_login=user.last_login,
                quotas=user.quotas
            )
            for user in users
        ]
        
    except Exception as e:
        logger.error("Failed to list users", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@router.put("/users/{user_id}/quotas")
async def update_user_quotas(
    user_id: str,
    quotas: QuotaSettings,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin
):
    """Update user quotas (admin only)"""
    
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.quotas = quotas.dict()
        await db.commit()
        
        logger.info("User quotas updated",
                   user_id=user_id,
                   quotas=quotas.dict(),
                   updated_by=auth.user_id)
        
        return {"message": "User quotas updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update user quotas", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user quotas"
        )


@router.post("/users/{user_id}/disable")
async def disable_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin
):
    """Disable a user (admin only)"""
    
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.id == auth.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot disable your own account"
            )
        
        user.enabled = False
        await db.commit()
        
        logger.info("User disabled",
                   user_id=user_id,
                   username=user.username,
                   disabled_by=auth.user_id)
        
        return {"message": "User disabled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to disable user", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable user"
        )


@router.post("/users/{user_id}/enable")
async def enable_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin
):
    """Enable a user (admin only)"""
    
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.enabled = True
        await db.commit()
        
        logger.info("User enabled",
                   user_id=user_id,
                   username=user.username,
                   enabled_by=auth.user_id)
        
        return {"message": "User enabled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to enable user", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enable user"
        )


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin,
    limit: int = 100,
    offset: int = 0,
    action_filter: Optional[str] = None,
    resource_type_filter: Optional[str] = None,
    user_id_filter: Optional[str] = None
):
    """List audit logs (admin only)"""
    
    try:
        query = select(AuditLog)
        
        # Apply filters
        conditions = []
        if action_filter:
            conditions.append(AuditLog.action == action_filter)
        if resource_type_filter:
            conditions.append(AuditLog.resource_type == resource_type_filter)
        if user_id_filter:
            conditions.append(AuditLog.user_id == user_id_filter)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(AuditLog.timestamp)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        audit_logs = result.scalars().all()
        
        return [
            AuditLogResponse(
                id=log.id,
                timestamp=log.timestamp,
                user_id=log.user_id,
                api_key_id=log.api_key_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                user_agent=log.user_agent
            )
            for log in audit_logs
        ]
        
    except Exception as e:
        logger.error("Failed to list audit logs", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list audit logs"
        )


@router.get("/system-stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin
):
    """Get system statistics (admin only)"""
    
    try:
        # Get system status from job manager
        system_status = await job_manager.get_system_status()
        
        # Get user count
        users_result = await db.execute(select(func.count()).select_from(User))
        total_users = users_result.scalar()
        
        # Get active users (logged in last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_users_result = await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.last_login >= thirty_days_ago)
        )
        active_users = active_users_result.scalar()
        
        # Get job stats
        total_jobs_result = await db.execute(select(func.count()).select_from(Job))
        total_jobs = total_jobs_result.scalar()
        
        jobs_today_result = await db.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0))
        )
        jobs_today = jobs_today_result.scalar()
        
        # Get API key count
        api_keys_result = await db.execute(select(func.count()).select_from(ApiKey))
        total_api_keys = api_keys_result.scalar()
        
        return {
            "system": system_status,
            "users": {
                "total": total_users,
                "active_30_days": active_users
            },
            "jobs": {
                "total": total_jobs,
                "today": jobs_today,
                "active": system_status["active_jobs"]
            },
            "api_keys": {
                "total": total_api_keys
            }
        }
        
    except Exception as e:
        logger.error("Failed to get system stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system stats"
        )


@router.post("/emergency-stop")
async def emergency_stop_all_jobs(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin
):
    """Emergency stop all jobs (admin only)"""
    
    try:
        # Stop all jobs through job manager
        from app.jobs import JobService
        job_service = JobService(db)
        await job_manager.emergency_stop_all(job_service)
        
        logger.warning("Emergency stop activated by admin",
                      admin_user_id=auth.user_id)
        
        return {"message": "All jobs stopped successfully"}
        
    except Exception as e:
        logger.error("Failed emergency stop", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop all jobs"
        )


@router.post("/cleanup-jobs")
async def cleanup_old_jobs(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin,
    days: int = 30
):
    """Clean up old job records (admin only)"""
    
    try:
        from app.jobs import JobService
        job_service = JobService(db)
        
        cleaned_count = await job_service.cleanup_old_jobs(days)
        
        logger.info("Job cleanup completed",
                   days=days,
                   cleaned_count=cleaned_count,
                   admin_user_id=auth.user_id)
        
        return {
            "message": f"Cleaned up {cleaned_count} old job records",
            "days": days,
            "cleaned_count": cleaned_count
        }
        
    except Exception as e:
        logger.error("Failed job cleanup", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup old jobs"
        )