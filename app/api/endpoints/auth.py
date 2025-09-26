"""
Authentication API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta, datetime
import structlog

from app.db.database import get_db
from app.models.user import User, ApiKey
from app.api.schemas import (
    LoginRequest, TokenResponse, UserCreateRequest, UserResponse, 
    ApiKeyCreateRequest, ApiKeyResponse, ErrorResponse
)
from app.auth import (
    hash_password, verify_password, create_access_token,
    generate_api_key, hash_api_key, RequireAdmin, AuthContext, get_auth_context
)
from app.config import settings

logger = structlog.get_logger()
router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return JWT token"""
    
    # Find user by username
    result = await db.execute(
        select(User).where(
            User.username == form_data.username,
            User.enabled == True
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    
    logger.info("User logged in successfully", user_id=user.id, username=user.username)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60
    }


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_request: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin
):
    """Create a new user (admin only)"""
    
    # Check if username or email already exists
    existing_result = await db.execute(
        select(User).where(
            (User.username == user_request.username) |
            (User.email == user_request.email)
        )
    )
    existing_user = existing_result.scalar_one_or_none()
    
    if existing_user:
        if existing_user.username == user_request.username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists"
            )
    
    # Create new user
    user = User(
        username=user_request.username,
        email=user_request.email,
        hashed_password=hash_password(user_request.password),
        role=user_request.role.value,
        quotas=user_request.quotas.dict(),
        created_at=datetime.utcnow()
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    logger.info("User created", 
               user_id=user.id, 
               username=user.username, 
               created_by=auth.user_id)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        enabled=user.enabled,
        created_at=user.created_at,
        last_login=user.last_login,
        quotas=user.quotas
    )


@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key(
    key_request: ApiKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin
):
    """Create a new API key"""
    
    # Generate API key
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    
    # Calculate expiration
    expires_at = datetime.utcnow() + timedelta(days=key_request.expires_in_days)
    
    # Create API key record
    api_key_record = ApiKey(
        user_id=auth.user_id,
        name=key_request.name,
        key_hash=key_hash,
        scopes=key_request.scopes,
        quotas=key_request.quotas.dict(),
        expires_at=expires_at,
        created_at=datetime.utcnow()
    )
    
    db.add(api_key_record)
    await db.commit()
    await db.refresh(api_key_record)
    
    logger.info("API key created",
               api_key_id=api_key_record.id,
               name=key_request.name,
               user_id=auth.user_id)
    
    return ApiKeyResponse(
        id=api_key_record.id,
        name=api_key_record.name,
        key=api_key,  # Only returned on creation
        scopes=api_key_record.scopes,
        enabled=api_key_record.enabled,
        created_at=api_key_record.created_at,
        expires_at=api_key_record.expires_at,
        last_used=api_key_record.last_used,
        quotas=api_key_record.quotas
    )


@router.get("/api-keys")
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin
):
    """List API keys for current user or all (admin only)"""
    
    query = select(ApiKey)
    
    # Non-admin users can only see their own keys
    if auth.role != "admin":
        query = query.where(ApiKey.user_id == auth.user_id)
    
    result = await db.execute(query)
    api_keys = result.scalars().all()
    
    return [
        ApiKeyResponse(
            id=key.id,
            name=key.name,
            key=None,  # Never return the actual key
            scopes=key.scopes,
            enabled=key.enabled,
            created_at=key.created_at,
            expires_at=key.expires_at,
            last_used=key.last_used,
            quotas=key.quotas
        )
        for key in api_keys
    ]


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin
):
    """Delete an API key"""
    
    # Find API key
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # Check permissions
    if auth.role != "admin" and api_key.user_id != auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete another user's API key"
        )
    
    await db.delete(api_key)
    await db.commit()
    
    logger.info("API key deleted",
               api_key_id=key_id,
               deleted_by=auth.user_id)
    
    return {"message": "API key deleted successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context)
):
    """Get current user info"""
    
    if not auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication"
        )
    
    # Get user details
    result = await db.execute(select(User).where(User.id == auth.user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        enabled=user.enabled,
        created_at=user.created_at,
        last_login=user.last_login,
        quotas=user.quotas
    )