from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from ..core.database import get_database
from ..models.schemas import (
    DashboardStats, ActivityItem, UserResponse
)
from ..utils.security import get_current_active_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats, summary="Get dashboard statistics")
async def get_dashboard_stats(
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Get dashboard statistics for the current user.
    
    Returns project counts, bug counts, and recent activity.
    """
    try:
        # Initialize stats
        stats = {
            "total_projects": 0,
            "total_bugs": 0,
            "open_bugs": 0,
            "resolved_bugs": 0,
            "critical_bugs": 0,
            "my_assigned_bugs": 0,
            "recent_activity": []
        }
        
        # Get user's projects (owned or member)
        user_projects = []
        try:
            # Projects owned by user
            owned_projects = db.table("projects").select("id").eq("owner_id", current_user.id).execute()
            if owned_projects.data:
                user_projects.extend([p["id"] for p in owned_projects.data])
            
            # Projects where user is member
            member_projects = db.table("project_members").select("project_id").eq("user_id", current_user.id).execute()
            if member_projects.data:
                user_projects.extend([p["project_id"] for p in member_projects.data])
            
            # Remove duplicates
            user_projects = list(set(user_projects))
            
        except Exception:
            pass  # Continue with empty projects list
        
        # Count total projects
        stats["total_projects"] = len(user_projects)
        
        # Get bug statistics
        if user_projects:
            try:
                # Get all bugs in user's projects
                bugs_result = db.table("bugs").select("status, priority, assigned_to").in_("project_id", user_projects).execute()
                bugs = bugs_result.data if bugs_result.data else []
                
                stats["total_bugs"] = len(bugs)
                
                # Count by status
                for bug in bugs:
                    bug_status = bug.get("status", "")
                    priority = bug.get("priority", "")
                    assigned_to = bug.get("assigned_to", "")
                    
                    if bug_status == "open":
                        stats["open_bugs"] += 1
                    elif bug_status == "resolved":
                        stats["resolved_bugs"] += 1
                    
                    if priority == "critical":
                        stats["critical_bugs"] += 1
                    
                    if assigned_to == current_user.id:
                        stats["my_assigned_bugs"] += 1
                
            except Exception:
                pass  # Continue with default values
        
        # Get recent activity (last 10 items)
        try:
            activity_result = db.table("audit_logs").select(
                "id, action, resource_type, resource_id, created_at, users!user_id(full_name)"
            ).in_("resource_id", user_projects + [current_user.id]).order("created_at", desc=True).limit(10).execute()
            
            recent_activity = []
            if activity_result.data:
                for item in activity_result.data:
                    user_info = item.get("users", {})
                    activity_item = {
                        "id": item["id"],
                        "type": item["action"],
                        "description": f"{item['action'].replace('_', ' ').title()} {item['resource_type']}",
                        "user_name": user_info.get("full_name", "Unknown"),
                        "timestamp": item["created_at"],
                        "related_id": item["resource_id"]
                    }
                    recent_activity.append(activity_item)
            
            stats["recent_activity"] = recent_activity
            
        except Exception:
            stats["recent_activity"] = []
        
        return DashboardStats(**stats)
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard statistics"
        )


@router.get("/activity", response_model=List[ActivityItem], summary="Get recent activity")
async def get_recent_activity(
    limit: int = 50,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Get recent activity for projects accessible to the user.
    
    Returns recent actions performed in user's projects.
    """
    try:
        # Get user's projects
        user_projects = []
        try:
            # Projects owned by user
            owned_projects = db.table("projects").select("id").eq("owner_id", current_user.id).execute()
            if owned_projects.data:
                user_projects.extend([p["id"] for p in owned_projects.data])
            
            # Projects where user is member
            member_projects = db.table("project_members").select("project_id").eq("user_id", current_user.id).execute()
            if member_projects.data:
                user_projects.extend([p["project_id"] for p in member_projects.data])
            
            # Remove duplicates
            user_projects = list(set(user_projects))
            
        except Exception:
            user_projects = []
        
        # Get recent activity
        activity_items = []
        if user_projects:
            try:
                activity_result = db.table("audit_logs").select(
                    "id, action, resource_type, resource_id, created_at, users!user_id(full_name)"
                ).in_("resource_id", user_projects + [current_user.id]).order("created_at", desc=True).limit(limit).execute()
                
                if activity_result.data:
                    for item in activity_result.data:
                        user_info = item.get("users", {})
                        activity_item = ActivityItem(
                            id=item["id"],
                            type=item["action"],
                            description=f"{item['action'].replace('_', ' ').title()} {item['resource_type']}",
                            user_name=user_info.get("full_name", "Unknown"),
                            timestamp=item["created_at"],
                            related_id=item["resource_id"]
                        )
                        activity_items.append(activity_item)
                
            except Exception:
                pass  # Continue with empty activity
        
        return activity_items
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch recent activity"
        )
