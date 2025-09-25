"""
API router configuration
"""

from fastapi import APIRouter
from app.api.endpoints import jobs, auth, targets, metrics, admin
from app.api import websocket

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"]
)

api_router.include_router(
    jobs.router,
    prefix="/jobs",
    tags=["jobs"]
)

api_router.include_router(
    targets.router,
    prefix="/targets",
    tags=["targets"]
)

api_router.include_router(
    metrics.router,
    prefix="/metrics",
    tags=["metrics"]
)

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["administration"]
)

api_router.include_router(
    websocket.router,
    tags=["websocket"]
)