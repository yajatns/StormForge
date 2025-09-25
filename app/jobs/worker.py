"""
Job execution worker for managing hping3 processes
"""

import asyncio
import subprocess
import signal
import os
import time
import re
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import structlog
import psutil

from app.config import settings
from app.api.schemas import JobStatus
from app.utils.hping import command_builder

logger = structlog.get_logger()


@dataclass
class ProcessStats:
    """Statistics from a running process"""
    packets_sent: int = 0
    bytes_sent: int = 0
    packets_received: int = 0
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    cpu_percent: float = 0.0
    memory_mb: float = 0.0


class JobProcess:
    """Manages a single hping3 process"""
    
    def __init__(self, job_id: str, command: List[str], target: str):
        self.job_id = job_id
        self.command = command
        self.target = target
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.stats = ProcessStats()
        self.stdout_buffer: List[str] = []
        self.stderr_buffer: List[str] = []
        self.logger = structlog.get_logger().bind(job_id=job_id, target=target)
        
    async def start(self) -> bool:
        """Start the hping3 process"""
        try:
            self.logger.info("Starting hping3 process", command=self.command)
            
            # Start process with proper settings
            self.process = await asyncio.create_subprocess_exec(
                *self.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group for clean termination
            )
            
            self.pid = self.process.pid
            self.stats.start_time = datetime.utcnow()
            
            self.logger.info("Process started successfully", pid=self.pid)
            return True
            
        except Exception as e:
            self.logger.error("Failed to start process", error=str(e))
            return False
    
    async def stop(self, force: bool = False) -> bool:
        """Stop the process gracefully or forcefully"""
        if not self.process:
            return False
            
        try:
            if force:
                # Force kill the process group
                if self.pid:
                    os.killpg(os.getpgid(self.pid), signal.SIGKILL)
                self.logger.info("Process force killed")
            else:
                # Graceful termination
                if self.pid:
                    os.killpg(os.getpgid(self.pid), signal.SIGTERM)
                    
                # Wait for graceful shutdown
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                    self.logger.info("Process terminated gracefully")
                except asyncio.TimeoutError:
                    # Force kill if graceful termination fails
                    if self.pid:
                        os.killpg(os.getpgid(self.pid), signal.SIGKILL)
                    self.logger.warning("Process killed after timeout")
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to stop process", error=str(e))
            return False
    
    async def read_output(self) -> Tuple[Optional[str], Optional[str]]:
        """Read stdout and stderr from process"""
        if not self.process:
            return None, None
            
        stdout_data = None
        stderr_data = None
        
        try:
            # Read stdout
            if self.process.stdout:
                try:
                    stdout_bytes = await asyncio.wait_for(
                        self.process.stdout.read(1024), 
                        timeout=0.1
                    )
                    if stdout_bytes:
                        stdout_data = stdout_bytes.decode('utf-8', errors='ignore')
                        self.stdout_buffer.append(stdout_data)
                        self._parse_hping_output(stdout_data)
                except asyncio.TimeoutError:
                    pass
            
            # Read stderr
            if self.process.stderr:
                try:
                    stderr_bytes = await asyncio.wait_for(
                        self.process.stderr.read(1024),
                        timeout=0.1
                    )
                    if stderr_bytes:
                        stderr_data = stderr_bytes.decode('utf-8', errors='ignore')
                        self.stderr_buffer.append(stderr_data)
                except asyncio.TimeoutError:
                    pass
                    
        except Exception as e:
            self.logger.error("Error reading process output", error=str(e))
        
        return stdout_data, stderr_data
    
    def _parse_hping_output(self, output: str):
        """Parse hping3 output to extract statistics"""
        try:
            # Parse hping3 verbose output patterns
            # Example: "HPING 192.168.1.1 (eth0 192.168.1.1): S set, 40 headers + 0 data bytes"
            # Example: "len=46 ip=192.168.1.1 ttl=64 DF id=0 sport=80 flags=SA seq=0 win=65535 rtt=0.3 ms"
            
            lines = output.split('\n')
            for line in lines:
                line = line.strip()
                
                # Count sent packets (lines with "flags=" usually indicate responses)
                if 'flags=' in line and 'seq=' in line:
                    self.stats.packets_received += 1
                
                # Parse packet statistics from summary lines
                # Example: "--- 192.168.1.1 hping statistic ---"
                # Example: "3 packets transmitted, 3 received, 0% packet loss"
                if 'packets transmitted' in line:
                    match = re.search(r'(\d+) packets transmitted, (\d+) received', line)
                    if match:
                        self.stats.packets_sent = int(match.group(1))
                        self.stats.packets_received = int(match.group(2))
                
            self.stats.last_update = datetime.utcnow()
            
        except Exception as e:
            self.logger.error("Error parsing hping output", error=str(e))
    
    def get_system_stats(self) -> bool:
        """Get system resource usage for the process"""
        if not self.pid:
            return False
            
        try:
            process = psutil.Process(self.pid)
            self.stats.cpu_percent = process.cpu_percent()
            self.stats.memory_mb = process.memory_info().rss / 1024 / 1024
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def is_alive(self) -> bool:
        """Check if process is still running"""
        if not self.process:
            return False
        return self.process.poll() is None
    
    def get_exit_code(self) -> Optional[int]:
        """Get process exit code"""
        if self.process:
            return self.process.poll()
        return None
    
    def get_stdout_log(self) -> str:
        """Get accumulated stdout"""
        return ''.join(self.stdout_buffer)
    
    def get_stderr_log(self) -> str:
        """Get accumulated stderr"""
        return ''.join(self.stderr_buffer)


class JobWorker:
    """Manages multiple job processes"""
    
    def __init__(self):
        self.active_jobs: Dict[str, JobProcess] = {}
        self.logger = structlog.get_logger()
        self._shutdown = False
    
    async def start_job(self, job_id: str, command: List[str], target: str, dry_run: bool = False) -> bool:
        """Start a new job process"""
        
        if dry_run:
            self.logger.info("Dry run - would execute command", 
                           job_id=job_id, 
                           command=command_builder.get_command_string(command))
            return True
        
        if job_id in self.active_jobs:
            self.logger.warning("Job already running", job_id=job_id)
            return False
        
        job_process = JobProcess(job_id, command, target)
        success = await job_process.start()
        
        if success:
            self.active_jobs[job_id] = job_process
            self.logger.info("Job started successfully", 
                           job_id=job_id, 
                           pid=job_process.pid)
        
        return success
    
    async def stop_job(self, job_id: str, force: bool = False) -> bool:
        """Stop a job process"""
        
        job_process = self.active_jobs.get(job_id)
        if not job_process:
            self.logger.warning("Job not found", job_id=job_id)
            return False
        
        success = await job_process.stop(force)
        
        if success:
            del self.active_jobs[job_id]
            self.logger.info("Job stopped", job_id=job_id, force=force)
        
        return success
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a job"""
        
        job_process = self.active_jobs.get(job_id)
        if not job_process:
            return None
        
        is_alive = job_process.is_alive()
        job_process.get_system_stats()
        
        return {
            "job_id": job_id,
            "pid": job_process.pid,
            "target": job_process.target,
            "is_alive": is_alive,
            "exit_code": job_process.get_exit_code(),
            "stats": {
                "packets_sent": job_process.stats.packets_sent,
                "bytes_sent": job_process.stats.bytes_sent,
                "packets_received": job_process.stats.packets_received,
                "start_time": job_process.stats.start_time.isoformat() if job_process.stats.start_time else None,
                "last_update": job_process.stats.last_update.isoformat() if job_process.stats.last_update else None,
                "cpu_percent": job_process.stats.cpu_percent,
                "memory_mb": job_process.stats.memory_mb
            },
            "stdout_log": job_process.get_stdout_log(),
            "stderr_log": job_process.get_stderr_log()
        }
    
    async def monitor_jobs(self) -> List[Dict[str, Any]]:
        """Monitor all active jobs and return status updates"""
        
        updates = []
        completed_jobs = []
        
        for job_id, job_process in self.active_jobs.items():
            # Read output
            stdout, stderr = await job_process.read_output()
            
            # Check if process is still alive
            if not job_process.is_alive():
                exit_code = job_process.get_exit_code()
                status = JobStatus.COMPLETED if exit_code == 0 else JobStatus.FAILED
                
                updates.append({
                    "job_id": job_id,
                    "status": status.value,
                    "exit_code": exit_code,
                    "stdout_log": job_process.get_stdout_log(),
                    "stderr_log": job_process.get_stderr_log(),
                    "packets_sent": job_process.stats.packets_sent,
                    "bytes_sent": job_process.stats.bytes_sent
                })
                
                completed_jobs.append(job_id)
            else:
                # Process is running, update stats
                job_process.get_system_stats()
                
                updates.append({
                    "job_id": job_id,
                    "status": JobStatus.RUNNING.value,
                    "packets_sent": job_process.stats.packets_sent,
                    "bytes_sent": job_process.stats.bytes_sent,
                    "cpu_percent": job_process.stats.cpu_percent,
                    "memory_mb": job_process.stats.memory_mb
                })
        
        # Remove completed jobs
        for job_id in completed_jobs:
            del self.active_jobs[job_id]
        
        return updates
    
    async def stop_all_jobs(self, force: bool = False):
        """Emergency stop all jobs"""
        
        self.logger.info("Stopping all jobs", force=force, count=len(self.active_jobs))
        
        stop_tasks = []
        for job_id in list(self.active_jobs.keys()):
            task = asyncio.create_task(self.stop_job(job_id, force))
            stop_tasks.append(task)
        
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        self.logger.info("All jobs stopped")
    
    async def cleanup_zombie_processes(self):
        """Clean up any zombie processes"""
        try:
            # Find any hping3 processes that might be orphaned
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'hping3':
                        pid = proc.info['pid']
                        
                        # Check if this PID is managed by us
                        is_managed = any(
                            job_process.pid == pid 
                            for job_process in self.active_jobs.values()
                        )
                        
                        if not is_managed:
                            self.logger.warning("Found orphaned hping3 process", pid=pid)
                            # Could optionally kill orphaned processes here
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            self.logger.error("Error during zombie cleanup", error=str(e))
    
    def get_active_job_count(self) -> int:
        """Get number of active jobs"""
        return len(self.active_jobs)
    
    def get_active_job_ids(self) -> List[str]:
        """Get list of active job IDs"""
        return list(self.active_jobs.keys())
    
    async def shutdown(self):
        """Graceful shutdown"""
        self._shutdown = True
        await self.stop_all_jobs(force=True)


# Global job worker instance
job_worker = JobWorker()