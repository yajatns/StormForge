"""
Job manager that coordinates between service and worker
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog

from app.jobs.service import JobService
from app.jobs.worker import job_worker
from app.api.schemas import JobStatus, JobCreateRequest
from app.models.job import Job
from app.utils.hping import generate_job_commands
from app.config import settings

logger = structlog.get_logger()


class JobManager:
    """High-level job management coordinating service and worker"""
    
    def __init__(self):
        self.logger = structlog.get_logger()
        self._monitoring_task: Optional[asyncio.Task] = None
        self._shutdown = False
    
    async def start_monitoring(self):
        """Start the job monitoring loop"""
        if self._monitoring_task and not self._monitoring_task.done():
            return
        
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Job monitoring started")
    
    async def stop_monitoring(self):
        """Stop the job monitoring loop"""
        self._shutdown = True
        
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        await job_worker.shutdown()
        self.logger.info("Job monitoring stopped")
    
    async def submit_job(
        self,
        job_service: JobService,
        job_spec: JobCreateRequest,
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Job:
        """Submit a new job for execution"""
        
        # Create job record
        job = await job_service.create_job(
            job_spec=job_spec,
            user_id=user_id,
            api_key_id=api_key_id,
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        # If not dry run, start execution immediately
        if not job_spec.dry_run:
            await self._start_job_execution(job_service, job)
        
        return job
    
    async def stop_job(
        self,
        job_service: JobService,
        job_id: str,
        user_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        force: bool = False
    ) -> bool:
        """Stop a running job"""
        
        # Stop in worker
        worker_stopped = await job_worker.stop_job(job_id, force)
        
        # Update database
        service_stopped = await job_service.stop_job(
            job_id=job_id,
            user_id=user_id,
            api_key_id=api_key_id,
            force=force
        )
        
        return worker_stopped or service_stopped
    
    async def emergency_stop_all(self, job_service: JobService):
        """Emergency stop all running jobs"""
        
        self.logger.warning("Emergency stop activated - stopping all jobs")
        
        # Stop all jobs in worker
        await job_worker.stop_all_jobs(force=True)
        
        # Update all active jobs in database
        from app.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            service = JobService(db)
            
            # Get all active jobs
            result = await service.list_jobs(
                status_filter=[JobStatus.QUEUED.value, JobStatus.RUNNING.value, JobStatus.STARTING.value]
            )
            
            # Mark them as cancelled
            for job in result["jobs"]:
                await service.update_job_status(
                    job_id=job.id,
                    status=JobStatus.CANCELLED.value,
                    error_message="Emergency stop activated"
                )
        
        self.logger.info("Emergency stop completed")
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        
        active_jobs = job_worker.get_active_job_count()
        
        return {
            "active_jobs": active_jobs,
            "max_jobs": settings.global_max_concurrent_jobs,
            "monitoring_active": self._monitoring_task and not self._monitoring_task.done(),
            "last_check": datetime.utcnow().isoformat()
        }
    
    async def _start_job_execution(self, job_service: JobService, job: Job):
        """Start actual job execution"""
        
        try:
            # Generate commands for all targets
            job_spec = JobCreateRequest(
                name=job.name,
                targets=job.targets,
                target_group=job.target_group,
                traffic_type=job.traffic_type,
                dst_port=job.dst_port,
                src_port=job.src_port,
                pps=job.pps,
                packet_size=job.packet_size,
                ttl=job.ttl,
                iface=job.iface,
                spoof_source=job.spoof_source,
                source_ip=job.source_ip,
                payload=job.payload,
                hping_options=job.hping_options,
                duration=job.duration,
                dry_run=job.dry_run,
                priority=job.priority,
                tags=job.tags
            )
            
            command_result = generate_job_commands(job_spec)
            if not command_result["success"]:
                await job_service.update_job_status(
                    job_id=job.id,
                    status=JobStatus.FAILED.value,
                    error_message=f"Command generation failed: {command_result.get('error')}"
                )
                return
            
            # For now, start job for first target (could be extended to handle multiple targets)
            first_target = job.targets[0] if job.targets else None
            if first_target and first_target in command_result["commands"]:
                command = command_result["commands"][first_target]
                
                # Update status to starting
                await job_service.update_job_status(
                    job_id=job.id,
                    status=JobStatus.STARTING.value
                )
                
                # Start in worker
                success = await job_worker.start_job(
                    job_id=job.id,
                    command=command,
                    target=first_target,
                    dry_run=job.dry_run
                )
                
                if success:
                    await job_service.update_job_status(
                        job_id=job.id,
                        status=JobStatus.RUNNING.value
                    )
                else:
                    await job_service.update_job_status(
                        job_id=job.id,
                        status=JobStatus.FAILED.value,
                        error_message="Failed to start hping3 process"
                    )
            else:
                await job_service.update_job_status(
                    job_id=job.id,
                    status=JobStatus.FAILED.value,
                    error_message="No valid targets found"
                )
        
        except Exception as e:
            self.logger.error("Failed to start job execution", 
                            job_id=job.id, 
                            error=str(e))
            
            await job_service.update_job_status(
                job_id=job.id,
                status=JobStatus.FAILED.value,
                error_message=f"Execution failed: {str(e)}"
            )
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        
        from app.db.database import AsyncSessionLocal
        from app.api.websocket import broadcast_job_update
        
        while not self._shutdown:
            try:
                # Get updates from worker
                updates = await job_worker.monitor_jobs()
                
                if updates:
                    # Update database with job status
                    async with AsyncSessionLocal() as db:
                        service = JobService(db)
                        
                        for update in updates:
                            # Update job in database
                            job = await service.update_job_status(
                                job_id=update["job_id"],
                                status=update["status"],
                                packets_sent=update.get("packets_sent"),
                                bytes_sent=update.get("bytes_sent"),
                                stdout_log=update.get("stdout_log"),
                                stderr_log=update.get("stderr_log"),
                                error_message=update.get("error_message")
                            )
                            
                            # Broadcast update via websocket
                            if job:
                                try:
                                    await broadcast_job_update(job)
                                except Exception as e:
                                    logger.error("Failed to broadcast job update", 
                                               job_id=job.id, error=str(e))
                
                # Clean up zombie processes periodically
                await job_worker.cleanup_zombie_processes()
                
                # Wait before next check
                await asyncio.sleep(settings.process_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in monitoring loop", error=str(e))
                await asyncio.sleep(5)  # Wait longer on error


# Global job manager instance
job_manager = JobManager()