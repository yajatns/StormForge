"""
Target management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import structlog

from app.db.database import get_db
from app.models.target_group import TargetGroup, AllowlistEntry
from app.api.schemas import (
    TargetGroupRequest, TargetGroupResponse, AllowlistEntry as AllowlistEntrySchema
)
from app.auth import RequireTargetRead, RequireTargetWrite, RequireAdmin, AuthContext
from app.utils.validation import network_validator, validate_cidr

logger = structlog.get_logger()
router = APIRouter()


@router.get("/", response_model=List[TargetGroupResponse])
async def list_target_groups(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireTargetRead
):
    """List all target groups"""
    
    try:
        result = await db.execute(
            select(TargetGroup)
            .where(TargetGroup.enabled == True)
            .order_by(TargetGroup.name)
        )
        target_groups = result.scalars().all()
        
        return [
            TargetGroupResponse(
                id=tg.id,
                name=tg.name,
                description=tg.description,
                targets=tg.targets,
                enabled=tg.enabled,
                created_at=tg.created_at,
                updated_at=tg.updated_at
            )
            for tg in target_groups
        ]
        
    except Exception as e:
        logger.error("Failed to list target groups", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list target groups"
        )


@router.post("/", response_model=TargetGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_target_group(
    target_group_request: TargetGroupRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireTargetWrite
):
    """Create a new target group"""
    
    try:
        # Check if name already exists
        existing_result = await db.execute(
            select(TargetGroup).where(TargetGroup.name == target_group_request.name)
        )
        existing_group = existing_result.scalar_one_or_none()
        
        if existing_group:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Target group name already exists"
            )
        
        # Validate targets
        targets_valid, target_errors = network_validator.validate_targets(target_group_request.targets)
        if not targets_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid targets: {target_errors}"
            )
        
        # Create target group
        target_group = TargetGroup(
            name=target_group_request.name,
            description=target_group_request.description,
            targets=target_group_request.targets,
            enabled=target_group_request.enabled,
            created_by=auth.user_id
        )
        
        db.add(target_group)
        await db.commit()
        await db.refresh(target_group)
        
        logger.info("Target group created",
                   target_group_id=target_group.id,
                   name=target_group_request.name,
                   created_by=auth.user_id)
        
        return TargetGroupResponse(
            id=target_group.id,
            name=target_group.name,
            description=target_group.description,
            targets=target_group.targets,
            enabled=target_group.enabled,
            created_at=target_group.created_at,
            updated_at=target_group.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create target group", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create target group"
        )


@router.get("/{group_id}", response_model=TargetGroupResponse)
async def get_target_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireTargetRead
):
    """Get target group by ID"""
    
    try:
        result = await db.execute(
            select(TargetGroup).where(TargetGroup.id == group_id)
        )
        target_group = result.scalar_one_or_none()
        
        if not target_group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target group not found"
            )
        
        return TargetGroupResponse(
            id=target_group.id,
            name=target_group.name,
            description=target_group.description,
            targets=target_group.targets,
            enabled=target_group.enabled,
            created_at=target_group.created_at,
            updated_at=target_group.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get target group", group_id=group_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get target group"
        )


@router.put("/{group_id}", response_model=TargetGroupResponse)
async def update_target_group(
    group_id: str,
    target_group_request: TargetGroupRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireTargetWrite
):
    """Update target group"""
    
    try:
        # Get existing target group
        result = await db.execute(
            select(TargetGroup).where(TargetGroup.id == group_id)
        )
        target_group = result.scalar_one_or_none()
        
        if not target_group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target group not found"
            )
        
        # Check if name conflicts with another group
        if target_group_request.name != target_group.name:
            existing_result = await db.execute(
                select(TargetGroup).where(
                    TargetGroup.name == target_group_request.name,
                    TargetGroup.id != group_id
                )
            )
            existing_group = existing_result.scalar_one_or_none()
            
            if existing_group:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Target group name already exists"
                )
        
        # Validate targets
        targets_valid, target_errors = network_validator.validate_targets(target_group_request.targets)
        if not targets_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid targets: {target_errors}"
            )
        
        # Update target group
        target_group.name = target_group_request.name
        target_group.description = target_group_request.description
        target_group.targets = target_group_request.targets
        target_group.enabled = target_group_request.enabled
        
        await db.commit()
        await db.refresh(target_group)
        
        logger.info("Target group updated",
                   target_group_id=group_id,
                   name=target_group_request.name,
                   updated_by=auth.user_id)
        
        return TargetGroupResponse(
            id=target_group.id,
            name=target_group.name,
            description=target_group.description,
            targets=target_group.targets,
            enabled=target_group.enabled,
            created_at=target_group.created_at,
            updated_at=target_group.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update target group", group_id=group_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update target group"
        )


@router.delete("/{group_id}")
async def delete_target_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireTargetWrite
):
    """Delete target group"""
    
    try:
        result = await db.execute(
            select(TargetGroup).where(TargetGroup.id == group_id)
        )
        target_group = result.scalar_one_or_none()
        
        if not target_group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target group not found"
            )
        
        await db.delete(target_group)
        await db.commit()
        
        logger.info("Target group deleted",
                   target_group_id=group_id,
                   name=target_group.name,
                   deleted_by=auth.user_id)
        
        return {"message": "Target group deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete target group", group_id=group_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete target group"
        )


@router.get("/allowlist/entries", response_model=List[AllowlistEntrySchema])
async def get_allowlist(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireTargetRead
):
    """Get allowlist/denylist entries"""
    
    try:
        result = await db.execute(
            select(AllowlistEntry)
            .where(AllowlistEntry.enabled == True)
            .order_by(AllowlistEntry.entry_type, AllowlistEntry.cidr)
        )
        entries = result.scalars().all()
        
        return [
            AllowlistEntrySchema(
                cidr=entry.cidr,
                description=entry.description,
                enabled=entry.enabled
            )
            for entry in entries
        ]
        
    except Exception as e:
        logger.error("Failed to get allowlist", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get allowlist"
        )


@router.post("/allowlist/entries", status_code=status.HTTP_201_CREATED)
async def add_allowlist_entry(
    entry_request: AllowlistEntrySchema,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = RequireAdmin
):
    """Add allowlist/denylist entry (admin only)"""
    
    try:
        # Validate CIDR format
        if not validate_cidr(entry_request.cidr):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid CIDR format"
            )
        
        # Check if entry already exists
        existing_result = await db.execute(
            select(AllowlistEntry).where(AllowlistEntry.cidr == entry_request.cidr)
        )
        existing_entry = existing_result.scalar_one_or_none()
        
        if existing_entry:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Allowlist entry already exists"
            )
        
        # Create entry
        entry = AllowlistEntry(
            cidr=entry_request.cidr,
            description=entry_request.description,
            enabled=entry_request.enabled,
            entry_type="allow",  # Default to allow
            created_by=auth.user_id
        )
        
        db.add(entry)
        await db.commit()
        
        # Update network validator
        # This would need to reload allowlist from database
        
        logger.info("Allowlist entry added",
                   cidr=entry_request.cidr,
                   created_by=auth.user_id)
        
        return {"message": "Allowlist entry added successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to add allowlist entry", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add allowlist entry"
        )