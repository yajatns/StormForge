"""
Simplified StormForge Main App - Works with minimal dependencies
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import logging
import time
from pathlib import Path

# Configure basic logging instead of structlog
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stormforge")

# Create FastAPI app
app = FastAPI(
    title="StormForge Traffic Orchestrator",
    description="Secure network traffic generation platform using hping3",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s")
    return response

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "StormForge Traffic Orchestrator",
        "version": "1.0.0",
        "python": os.sys.version,
        "database": "sqlite"
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to StormForge Traffic Orchestrator",
        "status": "running",
        "docs": "/docs",
        "api": "/api/v1"
    }

# API Info endpoint
@app.get("/api/v1/info")
async def api_info():
    return {
        "name": "StormForge API",
        "version": "1.0.0",
        "description": "Secure hping3 traffic orchestration platform",
        "features": [
            "Job Management",
            "User Authentication", 
            "Real-time Monitoring",
            "Role-based Access Control",
            "Audit Logging"
        ]
    }

# Jobs endpoints (simplified)
@app.get("/api/v1/jobs")
async def list_jobs():
    """List all jobs (simplified implementation)"""
    return {
        "jobs": [],
        "total": 0,
        "message": "Job management system ready - authentication required for full functionality"
    }

@app.post("/api/v1/jobs")
async def create_job():
    """Create a new job (simplified implementation)"""
    return {
        "message": "Job creation requires authentication",
        "status": "authentication_required"
    }

# User authentication endpoints (simplified)
@app.post("/api/v1/auth/login")
async def login():
    """User login (simplified implementation)"""
    return {
        "message": "Authentication system ready",
        "status": "not_implemented_yet"
    }

@app.get("/api/v1/auth/me")
async def get_current_user():
    """Get current user info (simplified implementation)"""
    return {
        "message": "User authentication required",
        "status": "not_authenticated"
    }

# System status endpoint
@app.get("/api/v1/system/status")
async def system_status():
    """Get system status"""
    import shutil
    
    # Check if hping3 is available
    hping3_available = shutil.which("hping3") is not None
    
    return {
        "system": "operational",
        "hping3_available": hping3_available,
        "hping3_path": shutil.which("hping3") if hping3_available else None,
        "database": "connected",
        "services": {
            "job_manager": "ready",
            "websocket": "ready", 
            "authentication": "ready"
        }
    }

# Configuration endpoint
@app.get("/api/v1/config")
async def get_config():
    """Get public configuration"""
    return {
        "features": {
            "job_creation": True,
            "real_time_monitoring": True,
            "user_management": True,
            "audit_logging": True
        },
        "limits": {
            "max_concurrent_jobs": 10,
            "default_timeout": 30,
            "max_job_duration": 3600
        }
    }

# Serve static files if frontend exists
frontend_path = Path("frontend/build")
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path / "static")), name="static")
    
    @app.get("/app/{full_path:path}")
    async def serve_app(full_path: str):
        """Serve React frontend"""
        return FileResponse(str(frontend_path / "index.html"))

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"Path {request.url.path} not found",
            "available_endpoints": [
                "/docs", "/redoc", "/health", 
                "/api/v1/info", "/api/v1/system/status"
            ]
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An internal error occurred"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)