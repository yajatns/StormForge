"""
Job management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import structlog

from app.db.database import get_db
from app.api.schemas import (
    JobCreateRequest, JobResponse, JobStopRequest, JobListResponse,
    ErrorResponse, JobStatus
)
from app.auth import RequireAuth, RequireJobRead, RequireJobWrite, AuthContext
from app.jobs import JobService, get_job_service, job_manager, QuotaExceededError, JobValidationError
from app.config import settings
from app.api.websocket import broadcast_job_update, broadcast_system_event

logger = structlog.get_logger()
router = APIRouter()


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_request: JobCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireJobWrite
):
    """Create and start a new hping3 job"""
    
    try:
        job_service = await get_job_service(db)
        
        # Submit job through manager
        job = await job_manager.submit_job(
            job_service=job_service,
            job_spec=job_request,
            user_id=auth.user_id,
            api_key_id=getattr(auth.api_key, 'id', None) if auth.api_key else None,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        logger.info("Job created via API",
                   job_id=job.id,
                   name=job.name,
                   user_id=auth.user_id,
                   dry_run=job_request.dry_run)
        
        # Broadcast job creation event
        try:
            await broadcast_job_update(job)
            await broadcast_system_event(
                "job_created",
                {
                    "job_id": str(job.id),
                    "name": job.name,
                    "user_id": auth.user_id,
                    "dry_run": job_request.dry_run
                },
                "info"
            )
        except Exception as e:
            logger.error("Failed to broadcast job creation event", 
                       job_id=job.id, error=str(e))
        
        return JobResponse(
            job_id=job.id,
            name=job.name,
            status=JobStatus(job.status),
            command=job.command,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            user_id=job.user_id,
            targets=job.targets,
            traffic_type=job.traffic_type,
            pps=job.pps,
            duration=job.duration,
            dry_run=job.dry_run,
            priority=job.priority,
            tags=job.tags,
            packets_sent=int(job.packets_sent) if job.packets_sent else 0,
            bytes_sent=int(job.bytes_sent) if job.bytes_sent else 0,
            error_message=job.error_message
        )
        
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except JobValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to create job", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job"
        )


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireJobRead,
    status_filter: Optional[List[str]] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    tags: Optional[List[str]] = Query(None)
):
    """List jobs with filtering"""
    
    try:
        job_service = await get_job_service(db)
        
        # Non-admin users can only see their own jobs
        user_filter = None if auth.role == "admin" else auth.user_id
        
        result = await job_service.list_jobs(
            user_id=user_filter,
            status_filter=status_filter,
            limit=limit,
            offset=offset,
            tags=tags
        )
        
        jobs = [
            JobResponse(
                job_id=job.id,
                name=job.name,
                status=JobStatus(job.status),
                command=job.command,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                user_id=job.user_id,
                targets=job.targets,
                traffic_type=job.traffic_type,
                pps=job.pps,
                duration=job.duration,
                dry_run=job.dry_run,
                priority=job.priority,
                tags=job.tags,
                packets_sent=int(job.packets_sent) if job.packets_sent else 0,
                bytes_sent=int(job.bytes_sent) if job.bytes_sent else 0,
                error_message=job.error_message
            )
            for job in result["jobs"]
        ]
        
        return JobListResponse(
            jobs=jobs,
            total=result["total"],
            page=offset // limit + 1,
            per_page=limit
        )
        
    except Exception as e:
        logger.error("Failed to list jobs", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list jobs"
        )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireJobRead
):
    """Get job details by ID"""
    
    try:
        job_service = await get_job_service(db)
        job = await job_service.get_job(job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        # Check permissions
        if auth.role != "admin" and job.user_id != auth.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return JobResponse(
            job_id=job.id,
            name=job.name,
            status=JobStatus(job.status),
            command=job.command,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            user_id=job.user_id,
            targets=job.targets,
            traffic_type=job.traffic_type,
            pps=job.pps,
            duration=job.duration,
            dry_run=job.dry_run,
            priority=job.priority,
            tags=job.tags,
            packets_sent=int(job.packets_sent) if job.packets_sent else 0,
            bytes_sent=int(job.bytes_sent) if job.bytes_sent else 0,
            error_message=job.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job"
        )


@router.post("/{job_id}/stop")
async def stop_job(
    job_id: str,
    stop_request: JobStopRequest = JobStopRequest(),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireJobWrite
):
    """Stop a running job"""
    
    try:
        job_service = await get_job_service(db)
        
        # Get job to check permissions
        job = await job_service.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        # Check permissions
        if auth.role != "admin" and job.user_id != auth.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Stop job through manager
        success = await job_manager.stop_job(
            job_service=job_service,
            job_id=job_id,
            user_id=auth.user_id,
            api_key_id=getattr(auth.api_key, 'id', None) if auth.api_key else None,
            force=stop_request.force
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job could not be stopped"
            )
        
        logger.info("Job stopped via API",
                   job_id=job_id,
                   force=stop_request.force,
                   stopped_by=auth.user_id)
        
        # Broadcast job stop event
        try:
            # Refresh job status and broadcast
            updated_job = await job_service.get_job(job_id)
            if updated_job:
                await broadcast_job_update(updated_job)
                await broadcast_system_event(
                    "job_stopped",
                    {
                        "job_id": job_id,
                        "force": stop_request.force,
                        "stopped_by": auth.user_id
                    },
                    "info"
                )
        except Exception as e:
            logger.error("Failed to broadcast job stop event", 
                       job_id=job_id, error=str(e))
        
        return {"message": "Job stopped successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to stop job", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop job"
        )


@router.post("/stop-all")
async def stop_all_jobs(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAuth
):
    """Emergency stop all jobs (admin only)"""
    
    if auth.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        job_service = await get_job_service(db)
        await job_manager.emergency_stop_all(job_service)
        
        logger.warning("All jobs stopped via emergency stop",
                      stopped_by=auth.user_id)
        
        return {"message": "All jobs stopped successfully"}
        
    except Exception as e:
        logger.error("Failed to stop all jobs", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop all jobs"
        )


@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireJobRead,
    tail: int = Query(100, ge=1, le=10000)
):
    """Get job logs (stdout/stderr)"""
    
    try:
        job_service = await get_job_service(db)
        job = await job_service.get_job(job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        # Check permissions
        if auth.role != "admin" and job.user_id != auth.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get logs and truncate if needed
        stdout_log = job.stdout_log or ""
        stderr_log = job.stderr_log or ""
        
        if tail > 0:
            stdout_lines = stdout_log.split('\n')
            stderr_lines = stderr_log.split('\n')
            
            stdout_log = '\n'.join(stdout_lines[-tail:])
            stderr_log = '\n'.join(stderr_lines[-tail:])
        
        return {
            "job_id": job_id,
            "stdout": stdout_log,
            "stderr": stderr_log,
            "truncated": tail < len(stdout_log.split('\n')) if stdout_log else False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job logs", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job logs"
        )