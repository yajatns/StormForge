"""
Job management service
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func, desc
from datetime import datetime, timedelta
import uuid
import asyncio
import structlog

from app.models.job import Job
from app.models.user import User, ApiKey
from app.models.audit_log import AuditLog
from app.api.schemas import JobCreateRequest, JobStatus, JobResponse
from app.utils.validation import network_validator
from app.utils.hping import generate_job_commands, validate_job_spec
from app.config import settings

logger = structlog.get_logger()


class QuotaExceededError(Exception):
    """Raised when user/API key quotas are exceeded"""
    pass


class JobValidationError(Exception):
    """Raised when job validation fails"""
    pass


class JobService:
    """Service for managing hping3 jobs"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = structlog.get_logger()
    
    async def create_job(
        self, 
        job_spec: JobCreateRequest, 
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Job:
        """Create a new job"""
        
        # Validate job specification
        validation_result = validate_job_spec(job_spec)
        if not validation_result["valid"]:
            raise JobValidationError(f"Job validation failed: {validation_result['errors']}")
        
        # Validate targets against allowlist/denylist
        targets_valid, target_errors = network_validator.validate_targets(job_spec.targets)
        if not targets_valid:
            raise JobValidationError(f"Target validation failed: {target_errors}")
        
        # Check quotas
        await self._check_quotas(user_id, api_key_id, job_spec)
        
        # Generate commands
        command_result = generate_job_commands(job_spec)
        if not command_result["success"]:
            raise JobValidationError(f"Command generation failed: {command_result.get('error')}")
        
        # Create job record
        job = Job(
            id=str(uuid.uuid4()),
            name=job_spec.name,
            user_id=user_id,
            api_key_id=api_key_id,
            targets=job_spec.targets,
            target_group=job_spec.target_group,
            traffic_type=job_spec.traffic_type.value,
            dst_port=job_spec.dst_port,
            src_port=job_spec.src_port,
            pps=job_spec.pps,
            packet_size=job_spec.packet_size,
            ttl=job_spec.ttl,
            iface=job_spec.iface,
            spoof_source=job_spec.spoof_source,
            source_ip=job_spec.source_ip,
            payload=job_spec.payload,
            hping_options=job_spec.hping_options,
            duration=job_spec.duration,
            dry_run=job_spec.dry_run,
            priority=job_spec.priority.value,
            tags=job_spec.tags,
            status=JobStatus.QUEUED.value,
            created_at=datetime.utcnow(),
            queued_at=datetime.utcnow(),
            client_ip=client_ip,
            user_agent=user_agent,
            command=str(command_result["command_strings"])
        )
        
        # Save to database
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        
        # Log audit event
        await self._log_audit_event(
            action="create",
            resource_type="job",
            resource_id=job.id,
            user_id=user_id,
            api_key_id=api_key_id,
            details={
                "job_name": job_spec.name,
                "targets": job_spec.targets,
                "traffic_type": job_spec.traffic_type.value,
                "pps": job_spec.pps,
                "dry_run": job_spec.dry_run
            },
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        self.logger.info("Job created", 
                        job_id=job.id, 
                        name=job.name,
                        user_id=user_id,
                        dry_run=job_spec.dry_run)
        
        return job
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()
    
    async def list_jobs(
        self,
        user_id: Optional[str] = None,
        status_filter: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """List jobs with filtering"""
        
        query = select(Job)
        
        # Apply filters
        conditions = []
        if user_id:
            conditions.append(Job.user_id == user_id)
        
        if status_filter:
            conditions.append(Job.status.in_(status_filter))
        
        if tags:
            # Filter by tags (JSON contains)
            for tag in tags:
                conditions.append(Job.tags.contains([tag]))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply ordering and pagination
        query = query.order_by(desc(Job.created_at)).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        jobs = result.scalars().all()
        
        return {
            "jobs": jobs,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    async def stop_job(
        self,
        job_id: str,
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        force: bool = False,
        reason: Optional[str] = None
    ) -> bool:
        """Stop a running job"""
        
        job = await self.get_job(job_id)
        if not job:
            return False
        
        # Check if user can stop this job
        if user_id and job.user_id != user_id:
            # Allow admins to stop any job (would need role check here)
            pass
        
        # Update job status
        if job.status in [JobStatus.QUEUED.value, JobStatus.STARTING.value]:
            job.status = JobStatus.CANCELLED.value
        elif job.status == JobStatus.RUNNING.value:
            job.status = JobStatus.STOPPING.value if not force else JobStatus.CANCELLED.value
        else:
            return False  # Job not in stoppable state
        
        job.completed_at = datetime.utcnow()
        
        await self.db.commit()
        
        # Log audit event
        await self._log_audit_event(
            action="stop" if not force else "force_stop",
            resource_type="job",
            resource_id=job_id,
            user_id=user_id,
            api_key_id=api_key_id,
            details={
                "reason": reason,
                "force": force,
                "previous_status": job.status
            }
        )
        
        self.logger.info("Job stopped", 
                        job_id=job_id, 
                        force=force,
                        reason=reason)
        
        return True
    
    async def update_job_status(
        self,
        job_id: str,
        status: str,
        pid: Optional[int] = None,
        error_message: Optional[str] = None,
        stdout_log: Optional[str] = None,
        stderr_log: Optional[str] = None,
        packets_sent: Optional[int] = None,
        bytes_sent: Optional[int] = None
    ) -> Optional[Job]:
        """Update job status and statistics"""
        
        job = await self.get_job(job_id)
        if not job:
            return None
        
        # Update fields
        job.status = status
        if pid is not None:
            job.pid = pid
        if error_message is not None:
            job.error_message = error_message
        if stdout_log is not None:
            job.stdout_log = stdout_log
        if stderr_log is not None:
            job.stderr_log = stderr_log
        if packets_sent is not None:
            job.packets_sent = str(packets_sent)
        if bytes_sent is not None:
            job.bytes_sent = str(bytes_sent)
        
        # Update timestamps
        if status == JobStatus.RUNNING.value and not job.started_at:
            job.started_at = datetime.utcnow()
        elif status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
            job.completed_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(job)  # Refresh to get updated values
        return job
    
    async def cleanup_old_jobs(self, days: int = 30) -> int:
        """Clean up old completed jobs"""
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Delete old completed jobs
        result = await self.db.execute(
            update(Job)
            .where(
                and_(
                    Job.completed_at < cutoff_date,
                    Job.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value])
                )
            )
            .values(
                stdout_log=None,  # Clear logs to save space
                stderr_log=None
            )
        )
        
        await self.db.commit()
        return result.rowcount
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a user"""
        
        # Current active jobs
        active_result = await self.db.execute(
            select(func.count())
            .where(
                and_(
                    Job.user_id == user_id,
                    Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value])
                )
            )
        )
        active_jobs = active_result.scalar()
        
        # Total jobs today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = await self.db.execute(
            select(func.count())
            .where(
                and_(
                    Job.user_id == user_id,
                    Job.created_at >= today_start
                )
            )
        )
        jobs_today = today_result.scalar()
        
        return {
            "active_jobs": active_jobs,
            "jobs_today": jobs_today
        }
    
    async def _check_quotas(
        self,
        user_id: Optional[str],
        api_key_id: Optional[str],
        job_spec: JobCreateRequest
    ):
        """Check if job would exceed quotas"""
        
        quotas = {}
        
        # Get quotas from user or API key
        if user_id:
            user_result = await self.db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user:
                quotas = user.quotas or {}
        
        if api_key_id:
            key_result = await self.db.execute(select(ApiKey).where(ApiKey.id == api_key_id))
            api_key = key_result.scalar_one_or_none()
            if api_key:
                quotas = api_key.quotas or {}
        
        # Check PPS quota
        max_pps = quotas.get("max_pps", settings.default_max_pps)
        if job_spec.pps > max_pps:
            raise QuotaExceededError(f"PPS {job_spec.pps} exceeds quota of {max_pps}")
        
        # Check concurrent jobs quota
        max_concurrent = quotas.get("max_concurrent_jobs", settings.default_max_concurrent_jobs)
        active_jobs = await self._get_active_job_count(user_id)
        if active_jobs >= max_concurrent:
            raise QuotaExceededError(f"Active jobs {active_jobs} would exceed quota of {max_concurrent}")
        
        # Check duration quota
        max_duration = quotas.get("max_job_duration", settings.default_max_job_duration)
        if job_spec.duration > max_duration:
            raise QuotaExceededError(f"Duration {job_spec.duration}s exceeds quota of {max_duration}s")
    
    async def _get_active_job_count(self, user_id: Optional[str]) -> int:
        """Get count of active jobs for user"""
        if not user_id:
            return 0
            
        result = await self.db.execute(
            select(func.count())
            .where(
                and_(
                    Job.user_id == user_id,
                    Job.status.in_([JobStatus.QUEUED.value, JobStatus.STARTING.value, JobStatus.RUNNING.value])
                )
            )
        )
        return result.scalar()
    
    async def _log_audit_event(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log an audit event"""
        
        audit_log = AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            api_key_id=api_key_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=client_ip,
            user_agent=user_agent,
            timestamp=datetime.utcnow()
        )
        
        self.db.add(audit_log)
        await self.db.commit()


async def get_job_service(db: AsyncSession) -> JobService:
    """Dependency to get job service"""
    return JobService(db)