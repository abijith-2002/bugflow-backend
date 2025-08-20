from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.api.db.supabase_client import get_supabase
from src.api.deps import get_current_user, require_role
from src.api.models import ProjectCreate, ProjectOut, ProjectUpdate, UserProfile
from src.api.services.audit import create_audit_log

router = APIRouter(prefix="", tags=["Projects"])


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[ProjectOut],
    summary="List projects",
    description="List all projects. All authenticated users can view projects.",
)
def list_projects(user: UserProfile = Depends(get_current_user)):
    supabase = get_supabase()
    result = supabase.table("projects").select("*").order("created_at", desc=True).execute()
    return result.data or []


# PUBLIC_INTERFACE
@router.post(
    "",
    response_model=ProjectOut,
    status_code=201,
    summary="Create project",
    description="Create a new project. Requires role 'manager' or 'admin'.",
    responses={403: {"description": "Forbidden"}},
)
def create_project(payload: ProjectCreate, user: UserProfile = Depends(require_role("manager"))):
    supabase = get_supabase()
    insert_data = {"name": payload.name, "description": payload.description, "owner_id": str(user.id)}
    result = supabase.table("projects").insert(insert_data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create project")
    project = result.data[0]
    create_audit_log(action="create", entity_type="project", entity_id=project["id"], actor_id=user.id, metadata={"name": project["name"]})
    return project


# PUBLIC_INTERFACE
@router.get(
    "/{project_id}",
    response_model=ProjectOut,
    summary="Get project",
    description="Get a single project by id.",
)
def get_project(project_id: UUID, user: UserProfile = Depends(get_current_user)):
    supabase = get_supabase()
    result = supabase.table("projects").select("*").eq("id", str(project_id)).maybe_single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    return result.data


# PUBLIC_INTERFACE
@router.put(
    "/{project_id}",
    response_model=ProjectOut,
    summary="Update project",
    description="Update project details. Requires role 'manager' or 'admin'.",
)
def update_project(project_id: UUID, payload: ProjectUpdate, user: UserProfile = Depends(require_role("manager"))):
    supabase = get_supabase()
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_data:
        result = supabase.table("projects").select("*").eq("id", str(project_id)).maybe_single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Project not found")
        return result.data

    result = supabase.table("projects").update(update_data).eq("id", str(project_id)).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    updated = result.data[0]
    create_audit_log(action="update", entity_type="project", entity_id=updated["id"], actor_id=user.id, metadata=update_data)
    return updated


# PUBLIC_INTERFACE
@router.delete(
    "/{project_id}",
    status_code=204,
    summary="Delete project",
    description="Delete a project. Requires role 'admin' or 'manager'.",
)
def delete_project(project_id: UUID, user: UserProfile = Depends(require_role("manager"))):
    supabase = get_supabase()
    # Ensure exists
    existed = supabase.table("projects").select("id").eq("id", str(project_id)).maybe_single().execute()
    if not existed.data:
        raise HTTPException(status_code=404, detail="Project not found")
    supabase.table("projects").delete().eq("id", str(project_id)).execute()
    create_audit_log(action="delete", entity_type="project", entity_id=project_id, actor_id=user.id)
    return
