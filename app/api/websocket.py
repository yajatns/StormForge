"""
WebSocket endpoints for real-time job monitoring and system events.
"""
import json
import asyncio
from typing import Dict, Set, List, Optional
from datetime import datetime
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.routing import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from ..auth.dependencies import get_current_user_websocket, get_auth_context, AuthContext
from ..models.user import User
from ..models.job import Job, JobStatus
from ..db.database import get_db
from ..config import get_config

logger = structlog.get_logger(__name__)
config = get_config()

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        # Map websocket to user info for authorization
        self.active_connections: Dict[WebSocket, Dict] = {}
        # Job-specific subscriptions
        self.job_subscribers: Dict[str, Set[WebSocket]] = {}
        # Global subscribers for all events
        self.global_subscribers: Set[WebSocket] = set()
        
    async def connect(self, websocket: WebSocket, user: User, subscription_type: str = "global", job_id: Optional[str] = None):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        # Store connection metadata
        connection_info = {
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "subscription_type": subscription_type,
            "job_id": job_id,
            "connected_at": datetime.utcnow()
        }
        
        self.active_connections[websocket] = connection_info
        
        # Add to appropriate subscriber list
        if subscription_type == "job" and job_id:
            if job_id not in self.job_subscribers:
                self.job_subscribers[job_id] = set()
            self.job_subscribers[job_id].add(websocket)
        else:
            self.global_subscribers.add(websocket)
            
        logger.info("WebSocket connection established", 
                   user_id=user.id, 
                   username=user.username,
                   subscription_type=subscription_type,
                   job_id=job_id)
        
        # Send welcome message
        await self.send_personal_message(websocket, {
            "type": "connection_established",
            "message": "Connected successfully",
            "subscription_type": subscription_type,
            "job_id": job_id,
            "server_time": datetime.utcnow().isoformat()
        })
    
    async def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection."""
        if websocket not in self.active_connections:
            return
            
        connection_info = self.active_connections[websocket]
        
        # Remove from subscriber lists
        if connection_info["subscription_type"] == "job":
            job_id = connection_info["job_id"]
            if job_id in self.job_subscribers:
                self.job_subscribers[job_id].discard(websocket)
                if not self.job_subscribers[job_id]:
                    del self.job_subscribers[job_id]
        else:
            self.global_subscribers.discard(websocket)
            
        # Remove connection record
        del self.active_connections[websocket]
        
        logger.info("WebSocket connection closed", 
                   user_id=connection_info["user_id"],
                   username=connection_info["username"])
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error("Failed to send personal message", error=str(e))
            await self.disconnect(websocket)
    
    async def broadcast_to_job_subscribers(self, job_id: str, message: dict):
        """Broadcast a message to all subscribers of a specific job."""
        if job_id not in self.job_subscribers:
            return
            
        disconnected = []
        for websocket in self.job_subscribers[job_id]:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error("Failed to broadcast to job subscriber", 
                           job_id=job_id, error=str(e))
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected:
            await self.disconnect(websocket)
    
    async def broadcast_to_global_subscribers(self, message: dict):
        """Broadcast a message to all global subscribers."""
        disconnected = []
        for websocket in self.global_subscribers:
            try:
                # Check if user has permission for this message type
                connection_info = self.active_connections[websocket]
                if self._user_can_receive_message(connection_info, message):
                    await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error("Failed to broadcast to global subscriber", error=str(e))
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected:
            await self.disconnect(websocket)
    
    def _user_can_receive_message(self, connection_info: dict, message: dict) -> bool:
        """Check if user has permission to receive a specific message."""
        user_role = connection_info["role"]
        message_type = message.get("type", "")
        
        # Admin can see everything
        if user_role == "admin":
            return True
            
        # Operators can see job events but not admin events
        if user_role == "operator":
            return message_type not in ["admin_action", "user_management"]
            
        # Read-only users can only see job status updates for jobs they can view
        if user_role == "read_only":
            return message_type in ["job_status_update", "system_stats"]
            
        return False
    
    def get_connection_stats(self) -> dict:
        """Get statistics about active connections."""
        stats = {
            "total_connections": len(self.active_connections),
            "global_subscribers": len(self.global_subscribers),
            "job_subscriptions": len(self.job_subscribers),
            "connections_by_role": {"admin": 0, "operator": 0, "read_only": 0}
        }
        
        for connection_info in self.active_connections.values():
            role = connection_info["role"]
            if role in stats["connections_by_role"]:
                stats["connections_by_role"][role] += 1
                
        return stats


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/monitor")
async def websocket_global_monitor(
    websocket: WebSocket,
    user: User = Depends(get_current_user_websocket)
):
    """WebSocket endpoint for global system monitoring."""
    await manager.connect(websocket, user, "global")
    
    try:
        while True:
            # Keep connection alive and handle ping/pong
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await manager.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif message.get("type") == "request_stats":
                # Send current system stats
                stats = manager.get_connection_stats()
                await manager.send_personal_message(websocket, {
                    "type": "system_stats",
                    "data": stats,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket global monitor error", error=str(e))
        await manager.disconnect(websocket)


@router.websocket("/job/{job_id}")
async def websocket_job_monitor(
    websocket: WebSocket,
    job_id: UUID,
    user: User = Depends(get_current_user_websocket),
    session: AsyncSession = Depends(get_db)
):
    """WebSocket endpoint for monitoring a specific job."""
    job_id_str = str(job_id)
    
    # Verify job exists and user has access
    job = await session.get(Job, job_id)
    if not job:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Job not found")
        return
        
    # Check if user can view this job
    if user.role == "read_only" and job.created_by != user.id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Access denied")
        return
    
    await manager.connect(websocket, user, "job", job_id_str)
    
    try:
        # Send initial job status
        await manager.send_personal_message(websocket, {
            "type": "job_status_update",
            "job_id": job_id_str,
            "data": {
                "status": job.status.value,
                "progress": job.progress,
                "output_lines": job.output_lines,
                "error_message": job.error_message,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "pid": job.pid
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await manager.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket job monitor error", job_id=job_id_str, error=str(e))
        await manager.disconnect(websocket)


# Event broadcasting functions (to be called from job management code)
async def broadcast_job_update(job: Job):
    """Broadcast job status update to subscribers."""
    message = {
        "type": "job_status_update",
        "job_id": str(job.id),
        "data": {
            "status": job.status.value,
            "progress": job.progress,
            "output_lines": job.output_lines,
            "error_message": job.error_message,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "pid": job.pid
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Broadcast to job-specific subscribers
    await manager.broadcast_to_job_subscribers(str(job.id), message)
    
    # Also broadcast to global subscribers
    await manager.broadcast_to_global_subscribers(message)


async def broadcast_system_event(event_type: str, data: dict, level: str = "info"):
    """Broadcast system-wide events."""
    message = {
        "type": "system_event",
        "event_type": event_type,
        "level": level,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await manager.broadcast_to_global_subscribers(message)


async def broadcast_admin_action(action: str, details: dict, user_id: int):
    """Broadcast admin actions to subscribers."""
    message = {
        "type": "admin_action",
        "action": action,
        "details": details,
        "performed_by": user_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await manager.broadcast_to_global_subscribers(message)


# Helper endpoint to get WebSocket connection stats (REST API)
@router.get("/stats") 
async def get_websocket_stats(auth: AuthContext = Depends(get_auth_context)):
    """Get WebSocket connection statistics."""
    if auth.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return manager.get_connection_stats()