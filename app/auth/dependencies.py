"""
Authentication dependencies and middleware
"""

from fastapi import Depends, HTTPException, status, Request, WebSocket, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import datetime
import structlog

from app.db.database import get_db
from app.models.user import User, ApiKey
from app.auth.security import decode_access_token, verify_api_key
from app.api.schemas import UserRole

logger = structlog.get_logger()

# Security scheme for JWT tokens
security = HTTPBearer()


class AuthContext:
    """Authentication context containing user/API key info"""
    def __init__(
        self,
        user: Optional[User] = None,
        api_key: Optional[ApiKey] = None,
        scopes: Optional[List[str]] = None
    ):
        self.user = user
        self.api_key = api_key
        self.scopes = scopes or []
        
    @property
    def user_id(self) -> Optional[str]:
        """Get the effective user ID"""
        if self.user:
            return self.user.id
        elif self.api_key:
            return self.api_key.user_id
        return None
        
    @property
    def role(self) -> Optional[str]:
        """Get the user role"""
        if self.user:
            return self.user.role
        elif self.api_key and self.api_key.user:
            return self.api_key.user.role
        return None
        
    @property
    def quotas(self) -> dict:
        """Get effective quotas"""
        if self.user:
            return self.user.quotas or {}
        elif self.api_key:
            return self.api_key.quotas or {}
        return {}


async def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user from JWT token"""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        return None
        
    user_id = payload.get("sub")
    if not user_id:
        return None
        
    result = await db.execute(select(User).where(User.id == user_id, User.enabled == True))
    user = result.scalar_one_or_none()
    
    if user:
        logger.info("User authenticated via JWT", user_id=user.id, username=user.username)
    
    return user


async def get_current_user_from_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[ApiKey]:
    """Get current user from API key header"""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return None
        
    # Find API key in database
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.enabled == True)
        .join(User)
        .where(User.enabled == True)
    )
    
    for key_record in result.scalars():
        if verify_api_key(api_key, key_record.key_hash):
            # Update last used timestamp
            key_record.last_used = datetime.utcnow()
            await db.commit()
            
            logger.info(
                "User authenticated via API key", 
                api_key_id=key_record.id, 
                user_id=key_record.user_id
            )
            return key_record
    
    return None


async def get_auth_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthContext:
    """Get authentication context from JWT token or API key"""
    # Try JWT token first
    user = None
    api_key = None
    
    if credentials:
        user = await get_current_user_from_token(credentials, db)
    
    # Try API key if no JWT
    if not user:
        api_key = await get_current_user_from_api_key(request, db)
    
    if not user and not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    scopes = []
    if api_key:
        scopes = api_key.scopes or []
    
    return AuthContext(user=user, api_key=api_key, scopes=scopes)


def require_role(required_role: UserRole):
    """Dependency to require specific role"""
    async def role_checker(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        user_role = auth.role
        
        # Role hierarchy: admin > operator > read_only
        role_hierarchy = {
            UserRole.READ_ONLY: 0,
            UserRole.OPERATOR: 1,
            UserRole.ADMIN: 2
        }
        
        required_level = role_hierarchy.get(required_role, 0)
        user_level = role_hierarchy.get(user_role, -1)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role.value}"
            )
        
        return auth
    
    return role_checker


def require_scope(required_scope: str):
    """Dependency to require specific scope (for API keys)"""
    async def scope_checker(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        # JWT tokens have all permissions based on user role
        if auth.user:
            return auth
            
        # API keys need explicit scopes
        if auth.api_key and required_scope not in auth.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {required_scope}"
            )
        
        return auth
    
    return scope_checker


# WebSocket authentication
async def get_current_user_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    api_key: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Authenticate user for WebSocket connections using query parameters"""
    user = None
    
    # Try JWT token first
    if token:
        payload = decode_access_token(token)
        if payload:
            user_id = payload.get("sub")
            if user_id:
                result = await db.execute(select(User).where(User.id == user_id, User.enabled == True))
                user = result.scalar_one_or_none()
    
    # Try API key if no JWT
    if not user and api_key:
        result = await db.execute(
            select(ApiKey)
            .where(ApiKey.enabled == True)
            .join(User)
            .where(User.enabled == True)
        )
        
        for key_record in result.scalars():
            if verify_api_key(api_key, key_record.key_hash):
                # Update last used timestamp
                key_record.last_used = datetime.utcnow()
                await db.commit()
                user = key_record.user
                break
    
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    return user


# Common dependencies
RequireAuth = Depends(get_auth_context)
RequireAdmin = Depends(require_role(UserRole.ADMIN))
RequireOperator = Depends(require_role(UserRole.OPERATOR))

# Scope-based dependencies
RequireJobRead = Depends(require_scope("jobs:read"))
RequireJobWrite = Depends(require_scope("jobs:write"))
RequireTargetRead = Depends(require_scope("targets:read"))
RequireTargetWrite = Depends(require_scope("targets:write"))
RequireAdminAccess = Depends(require_scope("admin:access"))