from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from ..core.database import get_database
from ..models.schemas import (
    ProjectResponse, ProjectCreate, ProjectUpdate, ProjectMember, ProjectStats,
    UserResponse, UserRole, PaginatedResponse, SuccessResponse
)
from ..utils.security import get_current_active_user, require_role
from ..utils.helpers import (
    generate_uuid, create_pagination_params, create_paginated_response,
    create_activity_log, check_user_permission
)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/", response_model=PaginatedResponse, summary="List projects")
async def list_projects(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by project name"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    List projects accessible to the current user.
    
    Returns projects where user is owner or member, with pagination and filtering.
    """
    try:
        # Build base query - get projects where user is owner or member
        base_query = f"""
        SELECT DISTINCT p.*, u.full_name as owner_name,
               (SELECT COUNT(*) FROM project_members pm WHERE pm.project_id = p.id) as members_count,
               (SELECT COUNT(*) FROM bugs b WHERE b.project_id = p.id) as bugs_count,
               (SELECT COUNT(*) FROM bugs b WHERE b.project_id = p.id AND b.status = 'open') as open_bugs_count
        FROM projects p
        LEFT JOIN users u ON p.owner_id = u.id
        LEFT JOIN project_members pm ON p.id = pm.project_id
        WHERE p.owner_id = '{current_user.id}' OR pm.user_id = '{current_user.id}'
        """
        
        # Add filters
        conditions = []
        if search:
            conditions.append(f"p.name ILIKE '%{search}%'")
        if status:
            conditions.append(f"p.status = '{status}'")
            
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM ({base_query}) as counted"
        count_result = db.rpc('execute_sql', {'query': count_query}).execute()
        total = count_result.data[0]['total'] if count_result.data else 0
        
        # Apply pagination and ordering
        pagination = create_pagination_params(page, per_page)
        paginated_query = f"{base_query} ORDER BY p.created_at DESC LIMIT {pagination['limit']} OFFSET {pagination['offset']}"
        
        result = db.rpc('execute_sql', {'query': paginated_query}).execute()
        projects = result.data if result.data else []
        
        return create_paginated_response(projects, total, page, per_page)
        
    except Exception:
        # Fallback to simple query if SQL RPC fails
        try:
            query = db.table("projects").select("*, users!owner_id(full_name)")
            
            if search:
                query = query.ilike("name", f"%{search}%")
            if status:
                query = query.eq("status", status)
            
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
            projects = result.data if result.data else []
            
            return create_paginated_response(projects, total, page, per_page)
            
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch projects"
            )


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project by ID")
async def get_project(
    project_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Get detailed project information by ID.
    
    Returns project details with statistics and member information.
    """
    try:
        # Check project access permission
        has_access = await check_user_permission(current_user.id, "project", project_id, db)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this project"
            )
        
        # Get project details
        result = db.table("projects").select("*, users!owner_id(full_name)").eq("id", project_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        project = result.data[0]
        
        # Get project statistics
        try:
            # Count members
            members_result = db.table("project_members").select("user_id").eq("project_id", project_id).execute()
            members_count = len(members_result.data) if members_result.data else 0
            
            # Count bugs
            bugs_result = db.table("bugs").select("id, status").eq("project_id", project_id).execute()
            bugs_count = len(bugs_result.data) if bugs_result.data else 0
            
            # Count open bugs
            open_bugs_count = 0
            if bugs_result.data:
                open_bugs_count = sum(1 for bug in bugs_result.data if bug.get("status") == "open")
            
            project["members_count"] = members_count
            project["bugs_count"] = bugs_count
            project["open_bugs_count"] = open_bugs_count
            
        except Exception:
            project["members_count"] = 0
            project["bugs_count"] = 0
            project["open_bugs_count"] = 0
        
        return ProjectResponse(**project)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch project"
        )


@router.post("/", response_model=ProjectResponse, summary="Create new project")
async def create_project(
    project_data: ProjectCreate,
    current_user: UserResponse = Depends(require_role(UserRole.PROJECT_MANAGER)),
    db = Depends(get_database)
):
    """
    Create a new project.
    
    Creates a new project with the current user as owner.
    """
    try:
        # Create new project
        project_id = generate_uuid()
        
        new_project = {
            "id": project_id,
            "name": project_data.name,
            "description": project_data.description,
            "status": project_data.status.value,
            "owner_id": current_user.id
        }
        
        result = db.table("projects").insert(new_project).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create project"
            )
        
        # Add owner as project member
        member_data = {
            "id": generate_uuid(),
            "project_id": project_id,
            "user_id": current_user.id,
            "role": current_user.role.value
        }
        db.table("project_members").insert(member_data).execute()
        
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="project_created",
            resource_type="project",
            resource_id=project_id,
            details={"project_name": project_data.name}
        )
        db.table("audit_logs").insert(activity).execute()
        
        # Get created project with owner info
        created_result = db.table("projects").select("*, users!owner_id(full_name)").eq("id", project_id).execute()
        project = created_result.data[0] if created_result.data else result.data[0]
        
        return ProjectResponse(**project)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Project creation failed"
        )


@router.put("/{project_id}", response_model=ProjectResponse, summary="Update project")
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Update project information.
    
    Only project owner or admins can update project details.
    """
    try:
        # Check if project exists and get owner info
        existing_project = db.table("projects").select("*").eq("id", project_id).execute()
        if not existing_project.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        project = existing_project.data[0]
        
        # Check permissions (owner or admin)
        if project["owner_id"] != current_user.id and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this project"
            )
        
        # Prepare update data
        update_data = {}
        for field, value in project_data.dict(exclude_unset=True).items():
            if value is not None:
                if field == "status" and hasattr(value, 'value'):
                    update_data[field] = value.value
                else:
                    update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid update data provided"
            )
        
        # Update project
        result = db.table("projects").update(update_data).eq("id", project_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update project"
            )
        
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="project_updated",
            resource_type="project",
            resource_id=project_id,
            details={"updated_fields": list(update_data.keys())}
        )
        db.table("audit_logs").insert(activity).execute()
        
        return ProjectResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Project update failed"
        )


@router.delete("/{project_id}", response_model=SuccessResponse, summary="Delete project")
async def delete_project(
    project_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Delete project.
    
    Only project owner or admins can delete projects.
    """
    try:
        # Check if project exists
        existing_project = db.table("projects").select("*").eq("id", project_id).execute()
        if not existing_project.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        project = existing_project.data[0]
        
        # Check permissions (owner or admin)
        if project["owner_id"] != current_user.id and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this project"
            )
        
        # Delete related data first (foreign key constraints)
        try:
            db.table("project_members").delete().eq("project_id", project_id).execute()
            db.table("bugs").delete().eq("project_id", project_id).execute()
        except Exception:
            pass  # Continue even if cleanup fails
        
        # Delete project
        db.table("projects").delete().eq("id", project_id).execute()
        
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="project_deleted",
            resource_type="project",
            resource_id=project_id,
            details={"project_name": project["name"]}
        )
        db.table("audit_logs").insert(activity).execute()
        
        return SuccessResponse(message="Project deleted successfully")
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Project deletion failed"
        )


@router.get("/{project_id}/members", response_model=List[ProjectMember], summary="Get project members")
async def get_project_members(
    project_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Get list of project members.
    
    Returns all members of the specified project.
    """
    try:
        # Check project access permission
        has_access = await check_user_permission(current_user.id, "project", project_id, db)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this project"
            )
        
        # Get project members with user details
        result = db.table("project_members").select(
            "*, users!user_id(full_name, email)"
        ).eq("project_id", project_id).execute()
        
        members = []
        if result.data:
            for member in result.data:
                user_info = member.get("users", {})
                members.append(ProjectMember(
                    user_id=member["user_id"],
                    user_name=user_info.get("full_name", "Unknown"),
                    user_email=user_info.get("email", ""),
                    role=member.get("role", "developer"),
                    joined_at=member.get("created_at")
                ))
        
        return members
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch project members"
        )


@router.post("/{project_id}/members/{user_id}", response_model=SuccessResponse, summary="Add project member")
async def add_project_member(
    project_id: str,
    user_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Add user to project as member.
    
    Only project owner or admins can add members.
    """
    try:
        # Check if project exists and get owner info
        project_result = db.table("projects").select("owner_id, name").eq("id", project_id).execute()
        if not project_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        project = project_result.data[0]
        
        # Check permissions (owner or admin)
        if project["owner_id"] != current_user.id and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to add members to this project"
            )
        
        # Check if user exists
        user_result = db.table("users").select("id, full_name, role").eq("id", user_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user = user_result.data[0]
        
        # Check if user is already a member
        existing_member = db.table("project_members").select("id").eq("project_id", project_id).eq("user_id", user_id).execute()
        if existing_member.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a project member"
            )
        
        # Add member
        member_data = {
            "id": generate_uuid(),
            "project_id": project_id,
            "user_id": user_id,
            "role": user.get("role", "developer")
        }
        
        result = db.table("project_members").insert(member_data).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add project member"
            )
        
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="member_added",
            resource_type="project",
            resource_id=project_id,
            details={
                "added_user_id": user_id,
                "added_user_name": user.get("full_name", ""),
                "project_name": project["name"]
            }
        )
        db.table("audit_logs").insert(activity).execute()
        
        return SuccessResponse(message="Member added successfully")
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add project member"
        )


@router.delete("/{project_id}/members/{user_id}", response_model=SuccessResponse, summary="Remove project member")
async def remove_project_member(
    project_id: str,
    user_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Remove user from project.
    
    Only project owner or admins can remove members.
    """
    try:
        # Check if project exists and get owner info
        project_result = db.table("projects").select("owner_id, name").eq("id", project_id).execute()
        if not project_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        project = project_result.data[0]
        
        # Check permissions (owner or admin)
        if project["owner_id"] != current_user.id and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to remove members from this project"
            )
        
        # Cannot remove project owner
        if user_id == project["owner_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove project owner"
            )
        
        # Check if user is a member
        member_result = db.table("project_members").select("*").eq("project_id", project_id).eq("user_id", user_id).execute()
        if not member_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not a project member"
            )
        
        # Remove member
        db.table("project_members").delete().eq("project_id", project_id).eq("user_id", user_id).execute()
        
        # Get user name for logging
        user_result = db.table("users").select("full_name").eq("id", user_id).execute()
        user_name = user_result.data[0]["full_name"] if user_result.data else ""
        
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="member_removed",
            resource_type="project",
            resource_id=project_id,
            details={
                "removed_user_id": user_id,
                "removed_user_name": user_name,
                "project_name": project["name"]
            }
        )
        db.table("audit_logs").insert(activity).execute()
        
        return SuccessResponse(message="Member removed successfully")
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove project member"
        )


@router.get("/{project_id}/stats", response_model=ProjectStats, summary="Get project statistics")
async def get_project_stats(
    project_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Get detailed project statistics.
    
    Returns bug counts by status and priority for the project.
    """
    try:
        # Check project access permission
        has_access = await check_user_permission(current_user.id, "project", project_id, db)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this project"
            )
        
        # Get all bugs for the project
        bugs_result = db.table("bugs").select("status, priority").eq("project_id", project_id).execute()
        bugs = bugs_result.data if bugs_result.data else []
        
        # Calculate statistics
        stats = {
            "total_bugs": len(bugs),
            "open_bugs": 0,
            "in_progress_bugs": 0,
            "resolved_bugs": 0,
            "closed_bugs": 0,
            "critical_bugs": 0,
            "high_priority_bugs": 0
        }
        
        for bug in bugs:
            bug_status = bug.get("status", "")
            priority = bug.get("priority", "")
            
            # Count by status
            if bug_status == "open":
                stats["open_bugs"] += 1
            elif bug_status == "in_progress":
                stats["in_progress_bugs"] += 1
            elif bug_status == "resolved":
                stats["resolved_bugs"] += 1
            elif bug_status == "closed":
                stats["closed_bugs"] += 1
            
            # Count by priority
            if priority == "critical":
                stats["critical_bugs"] += 1
            elif priority == "high":
                stats["high_priority_bugs"] += 1
        
        return ProjectStats(**stats)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch project statistics"
        )
