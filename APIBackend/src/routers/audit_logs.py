from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from ..core.database import get_database
from ..models.schemas import (
    AuditLogResponse, UserResponse, UserRole, PaginatedResponse
)
from ..utils.security import require_role
from ..utils.helpers import create_pagination_params, create_paginated_response

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("/", response_model=PaginatedResponse, summary="List audit logs")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    action: Optional[str] = Query(None, description="Filter by action"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    current_user: UserResponse = Depends(require_role(UserRole.PROJECT_MANAGER)),
    db = Depends(get_database)
):
    """
    List audit logs with filtering and pagination.
    
    Accessible to project managers and admins.
    """
    try:
        # Build query
        query = db.table("audit_logs").select("*, users!user_id(full_name)")
        
        # Apply filters
        if action:
            query = query.eq("action", action)
        
        if resource_type:
            query = query.eq("resource_type", resource_type)
            
        if resource_id:
            query = query.eq("resource_id", resource_id)
            
        if user_id:
            query = query.eq("user_id", user_id)
        
        # If not admin, filter to user's accessible resources
        if current_user.role != UserRole.ADMIN:
            # Get user's projects
            user_projects = []
            try:
                owned_projects = db.table("projects").select("id").eq("owner_id", current_user.id).execute()
                if owned_projects.data:
                    user_projects.extend([p["id"] for p in owned_projects.data])
                
                member_projects = db.table("project_members").select("project_id").eq("user_id", current_user.id).execute()
                if member_projects.data:
                    user_projects.extend([p["project_id"] for p in member_projects.data])
                
                user_projects = list(set(user_projects))
                
                if user_projects:
                    query = query.in_("resource_id", user_projects + [current_user.id])
                else:
                    # User has no accessible resources
                    return create_paginated_response([], 0, page, per_page)
                    
            except Exception:
                # If error getting projects, limit to user's own actions
                query = query.eq("user_id", current_user.id)
        
        # Get total count
        count_result = query.execute()
        total = len(count_result.data) if count_result.data else 0
        
        # Apply pagination
        pagination = create_pagination_params(page, per_page)
        paginated_query = query.range(
            pagination["offset"], 
            pagination["offset"] + pagination["limit"] - 1
        ).order("created_at", desc=True)
        
        result = paginated_query.execute()
        logs = result.data if result.data else []
        
        # Process logs for response
        processed_logs = []
        for log in logs:
            processed_log = dict(log)
            
            # Add user name
            if log.get("users"):
                processed_log["user_name"] = log["users"].get("full_name", "Unknown")
            
            processed_logs.append(processed_log)
        
        return create_paginated_response(processed_logs, total, page, per_page)
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch audit logs"
        )


@router.get("/{log_id}", response_model=AuditLogResponse, summary="Get audit log by ID")
async def get_audit_log(
    log_id: str,
    current_user: UserResponse = Depends(require_role(UserRole.PROJECT_MANAGER)),
    db = Depends(get_database)
):
    """
    Get detailed audit log information by ID.
    
    Accessible to project managers and admins.
    """
    try:
        # Get audit log with user details
        result = db.table("audit_logs").select("*, users!user_id(full_name)").eq("id", log_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit log not found"
            )
        
        log = result.data[0]
        
        # Check access permissions (non-admins can only see logs from their projects)
        if current_user.role != UserRole.ADMIN:
            # Check if log is for user's accessible resources
            resource_id = log.get("resource_id")
            
            # If it's the user's own action, allow access
            if log.get("user_id") == current_user.id:
                pass  # Allow access
            else:
                # Check if resource is in user's projects
                try:
                    user_projects = []
                    owned_projects = db.table("projects").select("id").eq("owner_id", current_user.id).execute()
                    if owned_projects.data:
                        user_projects.extend([p["id"] for p in owned_projects.data])
                    
                    member_projects = db.table("project_members").select("project_id").eq("user_id", current_user.id).execute()
                    if member_projects.data:
                        user_projects.extend([p["project_id"] for p in member_projects.data])
                    
                    if resource_id not in user_projects:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not authorized to access this audit log"
                        )
                        
                except HTTPException:
                    raise
                except Exception:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not authorized to access this audit log"
                    )
        
        # Process log data
        processed_log = dict(log)
        
        # Add user name
        if log.get("users"):
            processed_log["user_name"] = log["users"].get("full_name", "Unknown")
        
        return AuditLogResponse(**processed_log)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch audit log"
        )
