"""
Metrics API endpoints
"""

from fastapi import APIRouter, Depends, Response, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from prometheus_client import (
    Counter, Gauge, Histogram, CollectorRegistry, 
    generate_latest, CONTENT_TYPE_LATEST
)
import structlog

from app.db.database import get_db
from app.models.job import Job
from app.models.user import User, ApiKey
from app.api.schemas import MetricsResponse
from app.auth import RequireAuth, AuthContext
from app.jobs import job_manager

logger = structlog.get_logger()
router = APIRouter()

# Prometheus metrics
registry = CollectorRegistry()

jobs_total = Counter(
    'hping_jobs_total', 
    'Total number of jobs created', 
    ['status', 'traffic_type'],
    registry=registry
)

jobs_active = Gauge(
    'hping_jobs_active', 
    'Number of currently active jobs',
    registry=registry
)

packets_sent_total = Counter(
    'hping_packets_sent_total',
    'Total packets sent by all jobs',
    ['traffic_type'],
    registry=registry
)

bytes_sent_total = Counter(
    'hping_bytes_sent_total',
    'Total bytes sent by all jobs', 
    ['traffic_type'],
    registry=registry
)

job_duration_seconds = Histogram(
    'hping_job_duration_seconds',
    'Job duration in seconds',
    ['status'],
    registry=registry
)


@router.get("/", response_model=MetricsResponse)
async def get_metrics_summary(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAuth
):
    """Get metrics summary"""
    
    try:
        # Total jobs
        total_jobs_result = await db.execute(select(func.count()).select_from(Job))
        jobs_total_count = total_jobs_result.scalar()
        
        # Running jobs
        running_jobs_result = await db.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.status.in_(["queued", "starting", "running"]))
        )
        jobs_running = running_jobs_result.scalar()
        
        # Completed jobs
        completed_jobs_result = await db.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.status == "completed")
        )
        jobs_completed = completed_jobs_result.scalar()
        
        # Failed jobs
        failed_jobs_result = await db.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.status == "failed")
        )
        jobs_failed = failed_jobs_result.scalar()
        
        # Total packets sent
        packets_result = await db.execute(
            select(func.sum(Job.packets_sent.cast(db.bind.dialect.name == 'sqlite' and 'INTEGER' or 'BIGINT')))
            .select_from(Job)
            .where(Job.packets_sent.isnot(None))
        )
        packets_total = packets_result.scalar() or 0
        
        # Total bytes sent
        bytes_result = await db.execute(
            select(func.sum(Job.bytes_sent.cast(db.bind.dialect.name == 'sqlite' and 'INTEGER' or 'BIGINT')))
            .select_from(Job)
            .where(Job.bytes_sent.isnot(None))
        )
        bytes_total = bytes_result.scalar() or 0
        
        # Total users
        users_result = await db.execute(select(func.count()).select_from(User))
        users_total = users_result.scalar()
        
        # Total API keys
        api_keys_result = await db.execute(select(func.count()).select_from(ApiKey))
        api_keys_total = api_keys_result.scalar()
        
        return MetricsResponse(
            jobs_total=jobs_total_count,
            jobs_running=jobs_running,
            jobs_completed=jobs_completed,
            jobs_failed=jobs_failed,
            packets_sent_total=packets_total,
            bytes_sent_total=bytes_total,
            users_total=users_total,
            api_keys_total=api_keys_total
        )
        
    except Exception as e:
        logger.error("Failed to get metrics summary", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get metrics"
        )


@router.get("/prometheus")
async def get_prometheus_metrics(
    db: AsyncSession = Depends(get_db)
):
    """Get Prometheus metrics in text format"""
    
    try:
        # Update Prometheus metrics from database
        await _update_prometheus_metrics(db)
        
        # Generate Prometheus format
        metrics_data = generate_latest(registry)
        
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )
        
    except Exception as e:
        logger.error("Failed to generate Prometheus metrics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate metrics"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    
    try:
        system_status = await job_manager.get_system_status()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "active_jobs": system_status["active_jobs"],
            "monitoring_active": system_status["monitoring_active"]
        }
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


async def _update_prometheus_metrics(db: AsyncSession):
    """Update Prometheus metrics from database"""
    
    try:
        # Clear existing metrics
        jobs_active.set(0)
        
        # Get job counts by status and traffic type
        jobs_by_status = await db.execute(
            select(Job.status, Job.traffic_type, func.count())
            .group_by(Job.status, Job.traffic_type)
        )
        
        for status, traffic_type, count in jobs_by_status:
            jobs_total.labels(status=status, traffic_type=traffic_type).inc(count)
            
            if status in ["queued", "starting", "running"]:
                jobs_active.inc(count)
        
        # Get packet/byte totals by traffic type
        packets_by_type = await db.execute(
            select(
                Job.traffic_type,
                func.sum(Job.packets_sent.cast(db.bind.dialect.name == 'sqlite' and 'INTEGER' or 'BIGINT')),
                func.sum(Job.bytes_sent.cast(db.bind.dialect.name == 'sqlite' and 'INTEGER' or 'BIGINT'))
            )
            .where(
                and_(
                    Job.packets_sent.isnot(None),
                    Job.bytes_sent.isnot(None)
                )
            )
            .group_by(Job.traffic_type)
        )
        
        for traffic_type, total_packets, total_bytes in packets_by_type:
            if total_packets:
                packets_sent_total.labels(traffic_type=traffic_type).inc(total_packets)
            if total_bytes:
                bytes_sent_total.labels(traffic_type=traffic_type).inc(total_bytes)
        
        # Job durations
        completed_jobs = await db.execute(
            select(Job.started_at, Job.completed_at, Job.status)
            .where(
                and_(
                    Job.started_at.isnot(None),
                    Job.completed_at.isnot(None),
                    Job.status.in_(["completed", "failed", "cancelled"])
                )
            )
        )
        
        for started_at, completed_at, status in completed_jobs:
            if started_at and completed_at:
                duration = (completed_at - started_at).total_seconds()
                job_duration_seconds.labels(status=status).observe(duration)
    
    except Exception as e:
        logger.error("Failed to update Prometheus metrics", error=str(e))