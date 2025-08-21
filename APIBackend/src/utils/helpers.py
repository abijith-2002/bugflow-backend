from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


# PUBLIC_INTERFACE
def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


# PUBLIC_INTERFACE
def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime to ISO string."""
    if dt:
        return dt.isoformat()
    return None


# PUBLIC_INTERFACE
def create_pagination_params(page: int = 1, per_page: int = 20) -> Dict[str, int]:
    """Create pagination parameters for database queries."""
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20
        
    offset = (page - 1) * per_page
    
    return {
        "page": page,
        "per_page": per_page,
        "offset": offset,
        "limit": per_page
    }


# PUBLIC_INTERFACE
def create_paginated_response(
    items: List[Dict[str, Any]], 
    total: int, 
    page: int, 
    per_page: int
) -> Dict[str, Any]:
    """Create paginated response structure."""
    pages = (total + per_page - 1) // per_page
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1
    }


# PUBLIC_INTERFACE
def sanitize_input(text: Optional[str]) -> Optional[str]:
    """Sanitize user input text."""
    if not text:
        return text
    return text.strip()[:1000]  # Limit length and strip whitespace


# PUBLIC_INTERFACE
async def check_user_permission(
    user_id: str, 
    resource_type: str, 
    resource_id: str, 
    db
) -> bool:
    """Check if user has permission to access a resource."""
    try:
        if resource_type == "project":
            # Check if user is project owner or member
            result = db.table("projects").select("owner_id").eq("id", resource_id).execute()
            if result.data and result.data[0]["owner_id"] == user_id:
                return True
                
            # Check project membership
            member_result = db.table("project_members").select("user_id").eq("project_id", resource_id).eq("user_id", user_id).execute()
            return bool(member_result.data)
            
        elif resource_type == "bug":
            # Check if user is bug reporter, assignee, or project member
            result = db.table("bugs").select("reported_by, assigned_to, project_id").eq("id", resource_id).execute()
            if not result.data:
                return False
                
            bug = result.data[0]
            if bug["reported_by"] == user_id or bug["assigned_to"] == user_id:
                return True
                
            # Check project access
            return await check_user_permission(user_id, "project", bug["project_id"], db)
            
        return False
        
    except Exception:
        return False


# PUBLIC_INTERFACE
def create_activity_log(
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create activity log entry."""
    return {
        "id": generate_uuid(),
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
        "created_at": datetime.utcnow().isoformat()
    }
