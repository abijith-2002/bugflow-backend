from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from ..core.database import get_database
from ..models.schemas import (
    BugResponse, BugCreate, BugUpdate, BugComment, BugCommentCreate,
    BugStatus, BugPriority, UserResponse, PaginatedResponse, SuccessResponse
)
from ..utils.security import get_current_active_user
from ..utils.helpers import (
    generate_uuid, create_pagination_params, create_paginated_response,
    create_activity_log, check_user_permission
)

router = APIRouter(prefix="/bugs", tags=["Bugs"])


@router.get("/", response_model=PaginatedResponse, summary="List bugs")
async def list_bugs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by title or description"),
    status: Optional[BugStatus] = Query(None, description="Filter by status"),
    priority: Optional[BugPriority] = Query(None, description="Filter by priority"),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee"),
    reported_by: Optional[str] = Query(None, description="Filter by reporter"),
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    List bugs with filtering and pagination.
    
    Returns bugs accessible to the current user based on project membership.
    """
    try:
        # Build query with user access control
        query = db.table("bugs").select(
            "*, projects!project_id(name), "
            "reporter:users!reported_by(full_name), "
            "assignee:users!assigned_to(full_name)"
        )
        
        # Apply filters
        if search:
            query = query.or_(f"title.ilike.%{search}%,description.ilike.%{search}%")
        
        if status:
            query = query.eq("status", status.value)
            
        if priority:
            query = query.eq("priority", priority.value)
            
        if project_id:
            # Check project access
            has_access = await check_user_permission(current_user.id, "project", project_id, db)
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this project"
                )
            query = query.eq("project_id", project_id)
        else:
            # Filter to only projects user has access to
            user_projects = db.table("projects").select("id").eq("owner_id", current_user.id).execute()
            member_projects = db.table("project_members").select("project_id").eq("user_id", current_user.id).execute()
            
            project_ids = []
            if user_projects.data:
                project_ids.extend([p["id"] for p in user_projects.data])
            if member_projects.data:
                project_ids.extend([p["project_id"] for p in member_projects.data])
            
            if project_ids:
                query = query.in_("project_id", project_ids)
            else:
                # User has no project access, return empty result
                return create_paginated_response([], 0, page, per_page)
        
        if assigned_to:
            query = query.eq("assigned_to", assigned_to)
            
        if reported_by:
            query = query.eq("reported_by", reported_by)
        
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
        bugs = result.data if result.data else []
        
        # Process bug data for response
        processed_bugs = []
        for bug in bugs:
            processed_bug = dict(bug)
            
            # Add related names
            if bug.get("projects"):
                processed_bug["project_name"] = bug["projects"].get("name", "")
            if bug.get("reporter"):
                processed_bug["reported_by_name"] = bug["reporter"].get("full_name", "")
            if bug.get("assignee"):
                processed_bug["assigned_to_name"] = bug["assignee"].get("full_name", "")
            
            # Get comments count
            try:
                comments_result = db.table("bug_comments").select("id").eq("bug_id", bug["id"]).execute()
                processed_bug["comments_count"] = len(comments_result.data) if comments_result.data else 0
            except Exception:
                processed_bug["comments_count"] = 0
            
            processed_bugs.append(processed_bug)
        
        return create_paginated_response(processed_bugs, total, page, per_page)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch bugs"
        )


@router.get("/{bug_id}", response_model=BugResponse, summary="Get bug by ID")
async def get_bug(
    bug_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Get detailed bug information by ID.
    
    Returns bug details with related project and user information.
    """
    try:
        # Get bug with related data
        result = db.table("bugs").select(
            "*, projects!project_id(name), "
            "reporter:users!reported_by(full_name), "
            "assignee:users!assigned_to(full_name)"
        ).eq("id", bug_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bug not found"
            )
        
        bug = result.data[0]
        
        # Check access permission
        has_access = await check_user_permission(current_user.id, "bug", bug_id, db)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this bug"
            )
        
        # Process bug data
        processed_bug = dict(bug)
        
        # Add related names
        if bug.get("projects"):
            processed_bug["project_name"] = bug["projects"].get("name", "")
        if bug.get("reporter"):
            processed_bug["reported_by_name"] = bug["reporter"].get("full_name", "")
        if bug.get("assignee"):
            processed_bug["assigned_to_name"] = bug["assignee"].get("full_name", "")
        
        # Get comments count
        try:
            comments_result = db.table("bug_comments").select("id").eq("bug_id", bug_id).execute()
            processed_bug["comments_count"] = len(comments_result.data) if comments_result.data else 0
        except Exception:
            processed_bug["comments_count"] = 0
        
        return BugResponse(**processed_bug)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch bug"
        )


@router.post("/", response_model=BugResponse, summary="Create new bug")
async def create_bug(
    bug_data: BugCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Create a new bug report.
    
    Creates a new bug in the specified project.
    """
    try:
        # Check project access
        has_access = await check_user_permission(current_user.id, "project", bug_data.project_id, db)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to create bugs in this project"
            )
        
        # Validate assigned user if provided
        if bug_data.assigned_to:
            assigned_user = db.table("users").select("id").eq("id", bug_data.assigned_to).execute()
            if not assigned_user.data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found"
                )
        
        # Create new bug
        bug_id = generate_uuid()
        
        new_bug = {
            "id": bug_id,
            "title": bug_data.title,
            "description": bug_data.description,
            "status": bug_data.status.value,
            "priority": bug_data.priority.value,
            "project_id": bug_data.project_id,
            "reported_by": current_user.id,
            "assigned_to": bug_data.assigned_to
        }
        
        result = db.table("bugs").insert(new_bug).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create bug"
            )
        
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="bug_created",
            resource_type="bug",
            resource_id=bug_id,
            details={"bug_title": bug_data.title, "project_id": bug_data.project_id}
        )
        db.table("audit_logs").insert(activity).execute()
        
        # Create notification for assigned user
        if bug_data.assigned_to and bug_data.assigned_to != current_user.id:
            notification_data = {
                "id": generate_uuid(),
                "user_id": bug_data.assigned_to,
                "type": "bug_assigned",
                "title": "New Bug Assigned",
                "message": f"You have been assigned a new bug: {bug_data.title}",
                "related_id": bug_id,
                "is_read": False
            }
            db.table("notifications").insert(notification_data).execute()
        
        # Get created bug with related data
        created_result = db.table("bugs").select(
            "*, projects!project_id(name), "
            "reporter:users!reported_by(full_name), "
            "assignee:users!assigned_to(full_name)"
        ).eq("id", bug_id).execute()
        
        if created_result.data:
            bug = created_result.data[0]
            processed_bug = dict(bug)
            
            if bug.get("projects"):
                processed_bug["project_name"] = bug["projects"].get("name", "")
            if bug.get("reporter"):
                processed_bug["reported_by_name"] = bug["reporter"].get("full_name", "")
            if bug.get("assignee"):
                processed_bug["assigned_to_name"] = bug["assignee"].get("full_name", "")
            
            processed_bug["comments_count"] = 0
            
            return BugResponse(**processed_bug)
        
        return BugResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bug creation failed"
        )


@router.put("/{bug_id}", response_model=BugResponse, summary="Update bug")
async def update_bug(
    bug_id: str,
    bug_data: BugUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Update bug information.
    
    Updates bug details with proper access control and notifications.
    """
    try:
        # Check if bug exists
        existing_bug = db.table("bugs").select("*").eq("id", bug_id).execute()
        if not existing_bug.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bug not found"
            )
        
        bug = existing_bug.data[0]
        
        # Check access permission
        has_access = await check_user_permission(current_user.id, "bug", bug_id, db)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this bug"
            )
        
        # Prepare update data
        update_data = {}
        for field, value in bug_data.dict(exclude_unset=True).items():
            if value is not None:
                if field in ["status", "priority"] and hasattr(value, 'value'):
                    update_data[field] = value.value
                else:
                    update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid update data provided"
            )
        
        # Validate assigned user if being updated
        if "assigned_to" in update_data and update_data["assigned_to"]:
            assigned_user = db.table("users").select("id").eq("id", update_data["assigned_to"]).execute()
            if not assigned_user.data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found"
                )
        
        # Track status changes for resolved_at field
        if "status" in update_data:
            if update_data["status"] == "resolved" and bug.get("status") != "resolved":
                update_data["resolved_at"] = "now()"
            elif update_data["status"] != "resolved" and bug.get("status") == "resolved":
                update_data["resolved_at"] = None
        
        # Update bug
        result = db.table("bugs").update(update_data).eq("id", bug_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update bug"
            )
        
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="bug_updated",
            resource_type="bug",
            resource_id=bug_id,
            details={"updated_fields": list(update_data.keys())}
        )
        db.table("audit_logs").insert(activity).execute()
        
        # Create notifications for relevant users
        notification_users = set()
        
        # Notify assigned user if assignment changed
        if "assigned_to" in update_data and update_data["assigned_to"] != current_user.id:
            notification_users.add(update_data["assigned_to"])
        
        # Notify reporter if status changed
        if "status" in update_data and bug.get("reported_by") != current_user.id:
            notification_users.add(bug.get("reported_by"))
        
        # Create notifications
        for user_id in notification_users:
            if user_id:
                notification_data = {
                    "id": generate_uuid(),
                    "user_id": user_id,
                    "type": "bug_updated",
                    "title": "Bug Updated",
                    "message": f"Bug '{bug.get('title', '')}' has been updated",
                    "related_id": bug_id,
                    "is_read": False
                }
                try:
                    db.table("notifications").insert(notification_data).execute()
                except Exception:
                    pass  # Continue if notification fails
        
        # Get updated bug with related data
        updated_result = db.table("bugs").select(
            "*, projects!project_id(name), "
            "reporter:users!reported_by(full_name), "
            "assignee:users!assigned_to(full_name)"
        ).eq("id", bug_id).execute()
        
        if updated_result.data:
            bug = updated_result.data[0]
            processed_bug = dict(bug)
            
            if bug.get("projects"):
                processed_bug["project_name"] = bug["projects"].get("name", "")
            if bug.get("reporter"):
                processed_bug["reported_by_name"] = bug["reporter"].get("full_name", "")
            if bug.get("assignee"):
                processed_bug["assigned_to_name"] = bug["assignee"].get("full_name", "")
            
            # Get comments count
            try:
                comments_result = db.table("bug_comments").select("id").eq("bug_id", bug_id).execute()
                processed_bug["comments_count"] = len(comments_result.data) if comments_result.data else 0
            except Exception:
                processed_bug["comments_count"] = 0
            
            return BugResponse(**processed_bug)
        
        return BugResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bug update failed"
        )


@router.delete("/{bug_id}", response_model=SuccessResponse, summary="Delete bug")
async def delete_bug(
    bug_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Delete bug.
    
    Only bug reporter, project owner, or admins can delete bugs.
    """
    try:
        # Check if bug exists
        existing_bug = db.table("bugs").select("*").eq("id", bug_id).execute()
        if not existing_bug.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bug not found"
            )
        
        bug = existing_bug.data[0]
        
        # Check if user can delete this bug
        can_delete = False
        if bug.get("reported_by") == current_user.id:
            can_delete = True
        elif current_user.role.value in ["admin", "project_manager"]:
            # Check if user is project owner
            project_result = db.table("projects").select("owner_id").eq("id", bug["project_id"]).execute()
            if project_result.data and project_result.data[0]["owner_id"] == current_user.id:
                can_delete = True
            elif current_user.role.value == "admin":
                can_delete = True
        
        if not can_delete:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this bug"
            )
        
        # Delete related data first
        try:
            db.table("bug_comments").delete().eq("bug_id", bug_id).execute()
            db.table("notifications").delete().eq("related_id", bug_id).execute()
        except Exception:
            pass  # Continue even if cleanup fails
        
        # Delete bug
        db.table("bugs").delete().eq("id", bug_id).execute()
        
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="bug_deleted",
            resource_type="bug",
            resource_id=bug_id,
            details={"bug_title": bug.get("title", "")}
        )
        db.table("audit_logs").insert(activity).execute()
        
        return SuccessResponse(message="Bug deleted successfully")
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bug deletion failed"
        )


@router.get("/{bug_id}/comments", response_model=List[BugComment], summary="Get bug comments")
async def get_bug_comments(
    bug_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Get all comments for a bug.
    
    Returns comments with user information.
    """
    try:
        # Check access permission
        has_access = await check_user_permission(current_user.id, "bug", bug_id, db)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this bug"
            )
        
        # Get comments with user details
        result = db.table("bug_comments").select(
            "*, users!user_id(full_name)"
        ).eq("bug_id", bug_id).order("created_at", desc=False).execute()
        
        comments = []
        if result.data:
            for comment in result.data:
                user_info = comment.get("users", {})
                comments.append(BugComment(
                    id=comment.get("id"),
                    bug_id=comment["bug_id"],
                    user_id=comment["user_id"],
                    user_name=user_info.get("full_name", "Unknown"),
                    content=comment["content"],
                    created_at=comment.get("created_at"),
                    updated_at=comment.get("updated_at")
                ))
        
        return comments
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch bug comments"
        )


@router.post("/{bug_id}/comments", response_model=BugComment, summary="Add bug comment")
async def add_bug_comment(
    bug_id: str,
    comment_data: BugCommentCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Add a comment to a bug.
    
    Creates a new comment and notifies relevant users.
    """
    try:
        # Check access permission
        has_access = await check_user_permission(current_user.id, "bug", bug_id, db)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to comment on this bug"
            )
        
        # Get bug details for notifications
        bug_result = db.table("bugs").select("title, reported_by, assigned_to").eq("id", bug_id).execute()
        if not bug_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bug not found"
            )
        
        bug = bug_result.data[0]
        
        # Create comment
        comment_id = generate_uuid()
        
        new_comment = {
            "id": comment_id,
            "bug_id": bug_id,
            "user_id": current_user.id,
            "content": comment_data.content
        }
        
        result = db.table("bug_comments").insert(new_comment).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create comment"
            )
        
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="comment_added",
            resource_type="bug",
            resource_id=bug_id,
            details={"comment_id": comment_id}
        )
        db.table("audit_logs").insert(activity).execute()
        
        # Create notifications for relevant users
        notification_users = set()
        
        # Notify bug reporter
        if bug.get("reported_by") and bug["reported_by"] != current_user.id:
            notification_users.add(bug["reported_by"])
        
        # Notify assigned user
        if bug.get("assigned_to") and bug["assigned_to"] != current_user.id:
            notification_users.add(bug["assigned_to"])
        
        # Create notifications
        for user_id in notification_users:
            notification_data = {
                "id": generate_uuid(),
                "user_id": user_id,
                "type": "comment_added",
                "title": "New Comment Added",
                "message": f"A new comment was added to bug '{bug.get('title', '')}'",
                "related_id": bug_id,
                "is_read": False
            }
            try:
                db.table("notifications").insert(notification_data).execute()
            except Exception:
                pass  # Continue if notification fails
        
        # Return comment with user info
        return BugComment(
            id=comment_id,
            bug_id=bug_id,
            user_id=current_user.id,
            user_name=current_user.full_name,
            content=comment_data.content,
            created_at=result.data[0].get("created_at"),
            updated_at=result.data[0].get("updated_at")
        )
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add comment"
        )
