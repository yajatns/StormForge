"""
StormForge Traffic Orchestrator

A secure, web-based tool for orchestrating controlled hping3 traffic generation
with comprehensive monitoring, RBAC, and safety controls.
"""

from typing import List, Optional
import os


class Settings:
    """Application configuration settings"""
    
    def __init__(self):
        # Application
        self.app_name: str = "StormForge Traffic Orchestrator"
        self.app_version: str = "1.0.0"
        self.debug: bool = os.getenv("DEBUG", "false").lower() == "true"
        
        # API
        self.api_prefix: str = "/api/v1"
        self.cors_origins: List[str] = ["*"]
        
        # Security
        self.secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
        self.algorithm: str = "HS256"
        self.access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        self.api_key_expire_days: int = 365
        
        # Database
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/orchestrator.db")
        self.database_echo: bool = os.getenv("DATABASE_ECHO", "false").lower() == "true"
        
        # Hping3
        self.hping3_path: str = os.getenv("HPING3_PATH", "/usr/sbin/hping3")
        self.max_concurrent_jobs: int = int(os.getenv("MAX_CONCURRENT_JOBS", "10"))
        self.default_timeout: int = int(os.getenv("DEFAULT_TIMEOUT", "30"))
        self.max_targets_per_job: int = 100
        
        # Logging
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.log_format: str = os.getenv("LOG_FORMAT", "json")
        
        # Network Security
        self.default_blocked_ranges: List[str] = ["127.0.0.0/8", "169.254.0.0/16", "224.0.0.0/4", "0.0.0.0/8", "240.0.0.0/4"]
        self.default_allowlist: List[str] = ["192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"]
        self.default_denylist: List[str] = ["127.0.0.0/8", "169.254.0.0/16", "224.0.0.0/4"]
        self.allowed_broadcast_ranges: List[str] = ["192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"]


# Global settings instance
settings = Settings()


def get_config() -> Settings:
    """Get the global settings instance"""
    return settings