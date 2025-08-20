from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.api.db.supabase_client import get_supabase
from src.api.deps import get_current_user, require_role
from src.api.models import BugCreate, BugOut, BugUpdate, UserProfile
from src.api.services.audit import create_audit_log
from src.api.services.notifications import create_notification

router = APIRouter(prefix="", tags=["Bugs"])


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[BugOut],
    summary="List bugs",
    description="List bugs optionally filtered by project_id.",
)
def list_bugs(project_id: Optional[UUID] = None, user: UserProfile = Depends(get_current_user)):
    supabase = get_supabase()
    query = supabase.table("bugs").select("*").order("created_at", desc=True)
    if project_id:
        query = query.eq("project_id", str(project_id))
    result = query.execute()
    return result.data or []


# PUBLIC_INTERFACE
@router.post(
    "",
    response_model=BugOut,
    status_code=201,
    summary="Create bug",
    description="Create a new bug report. Any authenticated user can create.",
)
def create_bug(payload: BugCreate, user: UserProfile = Depends(get_current_user)):
    supabase = get_supabase()
    insert_data = {
        "project_id": str(payload.project_id),
        "title": payload.title,
        "description": payload.description,
        "priority": payload.priority,
        "status": "open",
        "reporter_id": str(user.id),
        "assignee_id": str(payload.assignee_id) if payload.assignee_id else None,
    }
    result = supabase.table("bugs").insert(insert_data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create bug")
    bug = result.data[0]
    create_audit_log(action="create", entity_type="bug", entity_id=bug["id"], actor_id=user.id, metadata={"title": bug["title"]})

    # Notify assignee if set
    if bug.get("assignee_id"):
        create_notification(UUID(bug["assignee_id"]), f"You have been assigned bug '{bug['title']}'")

    return bug


# PUBLIC_INTERFACE
@router.get(
    "/{bug_id}",
    response_model=BugOut,
    summary="Get bug",
    description="Get a single bug by id.",
)
def get_bug(bug_id: UUID, user: UserProfile = Depends(get_current_user)):
    supabase = get_supabase()
    result = supabase.table("bugs").select("*").eq("id", str(bug_id)).maybe_single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Bug not found")
    return result.data


# PUBLIC_INTERFACE
@router.put(
    "/{bug_id}",
    response_model=BugOut,
    summary="Update bug",
    description="Update a bug. Allowed for assignee, managers, or admins.",
)
def update_bug(bug_id: UUID, payload: BugUpdate, user: UserProfile = Depends(get_current_user)):
    supabase = get_supabase()
    existing = supabase.table("bugs").select("*").eq("id", str(bug_id)).maybe_single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Bug not found")
    bug = existing.data

    is_assignee = bug.get("assignee_id") == str(user.id)
    is_manager = user.role in ("manager", "admin")
    if not (is_assignee or is_manager):
        raise HTTPException(status_code=403, detail="Not allowed to update this bug")

    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_data:
        return bug

    result = supabase.table("bugs").update(update_data).eq("id", str(bug_id)).execute()
    updated = result.data[0]

    create_audit_log(action="update", entity_type="bug", entity_id=bug_id, actor_id=user.id, metadata=update_data)

    # If assignee changed, notify the new assignee
    if "assignee_id" in update_data and update_data["assignee_id"]:
        try:
            new_assignee = UUID(update_data["assignee_id"])
            create_notification(new_assignee, f"You have been assigned bug '{updated['title']}'")
        except Exception:
            pass

    return updated


# PUBLIC_INTERFACE
@router.delete(
    "/{bug_id}",
    status_code=204,
    summary="Delete bug",
    description="Delete a bug. Requires role 'manager' or 'admin'.",
)
def delete_bug(bug_id: UUID, user: UserProfile = Depends(require_role("manager"))):
    supabase = get_supabase()
    existed = supabase.table("bugs").select("id").eq("id", str(bug_id)).maybe_single().execute()
    if not existed.data:
        raise HTTPException(status_code=404, detail="Bug not found")

    supabase.table("bugs").delete().eq("id", str(bug_id)).execute()
    create_audit_log(action="delete", entity_type="bug", entity_id=bug_id, actor_id=user.id)
    return
