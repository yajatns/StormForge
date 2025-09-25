"""
StormForge Traffic Orchestrator

A secure, web-based tool for orchestrating controlled hping3 traffic generation
with comprehensive monitoring, RBAC, and safety controls.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Application
    app_name: str = "StormForge Traffic Orchestrator"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # API
    api_prefix: str = "/api/v1"
    cors_origins: List[str] = ["*"]
    
    # Security
    secret_key: str = "your-secret-key-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    api_key_expire_days: int = 365
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./hping_orchestrator.db"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    
    # Safety & Limits
    default_max_pps: int = 100
    default_max_concurrent_jobs: int = 5
    default_max_job_duration: int = 3600  # 1 hour
    global_max_pps: int = 10000
    global_max_concurrent_jobs: int = 50
    
    # Network Safety
    allowed_broadcast_ranges: List[str] = [
        "224.0.0.0/8",  # IPv4 multicast
        "ff00::/8"      # IPv6 multicast
    ]
    
    # Default blocked ranges (RFC1918 + loopback protection)
    default_blocked_ranges: List[str] = [
        "127.0.0.0/8",      # Loopback
        "169.254.0.0/16",   # Link-local
        "224.0.0.0/4",      # Multicast (unless explicitly allowed)
        "240.0.0.0/4"       # Reserved
    ]
    
    # Job Management
    job_cleanup_interval: int = 300  # 5 minutes
    job_history_retention_days: int = 30
    max_job_output_size: int = 1024 * 1024  # 1MB
    
    # Monitoring
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # WebSocket
    websocket_heartbeat_interval: int = 30
    
    # Process Management
    hping_timeout: int = 300  # 5 minutes default timeout
    process_check_interval: int = 1  # Check processes every second
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()