from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Path, Response, Header
from pydantic import BaseModel, Field, field_validator
from supabase import Client as SupabaseClient

from .config import get_settings
from .supabase_client import SupabaseClientProvider

router = APIRouter(prefix="/projects", tags=["Projects"])


def get_supabase(request_settings=Depends(get_settings)) -> SupabaseClient:
    """PUBLIC_INTERFACE: Provide supabase client from settings."""
    try:
        provider = SupabaseClientProvider(
            supabase_url=request_settings.SUPABASE_URL,
            supabase_key=request_settings.SUPABASE_ANON_KEY,
        )
        return provider.client()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")

async def _require_valid_bearer_user(
    supabase: SupabaseClient,
    authorization: Optional[str],
) -> str:
    """
    Validate Authorization: Bearer <jwt> header using Supabase and return user id.

    Raises:
        HTTPException(401): when header is missing, malformed, or token invalid.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    parts = authorization.split()
    if not (len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip()):
        raise HTTPException(status_code=401, detail="Invalid or malformed Authorization header")
    token = parts[1].strip()
    try:
        user_res = supabase.auth.get_user(token=token)
        user = getattr(user_res, "user", None)
        user_id = getattr(user, "id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return str(user_id)
    except HTTPException:
        raise
    except Exception:
        # Any SDK error should be treated as unauthorized for this protection
        raise HTTPException(status_code=401, detail="Unauthorized")


async def _select_projects_with_counts(supabase: SupabaseClient) -> list[dict]:
    """
    Fetch projects and compute tasks/bugs counts from public.work_item using head=True counts.

    Implementation details:
    - Retrieve all projects (newest first).
    - For each project, perform two separate count queries against public.work_item:
      * tasks_count: select('id', count='exact', head=True).eq('project_id', <id>).eq('item_type','task')
      * bugs_count:  select('id', count='exact', head=True).eq('project_id', <id>).eq('item_type','bug')
    - Use resp.count and default to 0 if it is missing or None.
    """
    # 1) Fetch base projects (newest first)
    proj_resp = (
        supabase.table("projects")
        .select("id,name,project_key,description,colour,created_at")
        .order("created_at", desc=True)
        .execute()
    )
    projects = proj_resp.data or []
    if not projects:
        return []

    # 2) For each project, run two head=True count queries
    for p in projects:
        pid = p.get("id")
     
        # tasks_count
        tasks_count = 0
        try:
            t_resp = (
                supabase.table("work_item")
                .select("id", count="exact")
                .eq("project_id", pid)
                .eq("item_type", "task")
                .execute()
            )
            # supabase-py returns .count on the response for head=True
        
            raw_t_count = getattr(t_resp, "count", None)
         
            tasks_count = int(raw_t_count) if raw_t_count is not None else 0
        except Exception:
            tasks_count = 0

        # bugs_count
        bugs_count = 0
        try:
            b_resp = (
                supabase.table("work_item")
                .select("id", count="exact")
                .eq("project_id", pid)
                .eq("item_type", "bug")
                .execute()
            )
            raw_b_count = getattr(b_resp, "count", None)
            bugs_count = int(raw_b_count) if raw_b_count is not None else 0
        except Exception:
            bugs_count = 0

        p["tasks_count"] = tasks_count
        p["bugs_count"] = bugs_count

    return projects


class Project(BaseModel):
    """Project entity returned by the API."""
    id: str = Field(..., description="Project unique identifier (UUID)")
    name: str = Field(..., description="Project name")
    project_key: str = Field(..., description="Short unique project key, e.g., BUG or APP")
    description: Optional[str] = Field(default=None, description="Project description")
    colour: Optional[str] = Field(default=None, description="Project colour (CSS color or hex code)")
    created_at: datetime = Field(..., description="Creation timestamp")
    tasks_count: int = Field(default=0, description="Total tasks count (item_type='task') for this project")
    bugs_count: int = Field(default=0, description="Total bugs count (item_type='bug') for this project")


class CreateProjectRequest(BaseModel):
    """Payload to create a new project."""
    name: str = Field(..., min_length=1, max_length=120, description="Project name")
    project_key: str = Field(..., min_length=1, max_length=20, description="Unique project key (short code)")
    description: Optional[str] = Field(default=None, description="Project description")
    colour: Optional[str] = Field(default=None, max_length=30, description="Project colour (CSS/hex)")
    created_at: Optional[datetime] = Field(
        default=None,
        description="Creation timestamp; if omitted, database default now() will be used",
    )

    @field_validator("project_key")
    @classmethod
    def project_key_format(cls, v: str) -> str:
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        if not v or any(ch not in allowed for ch in v):
            raise ValueError("project_key may contain only letters, numbers, '-' and '_'")
        return v


def _ignore_query_params(req: Request) -> None:
    """
    Ignore any incoming query params; this endpoint does not support filtering.
    This prevents accidental forwarding of client-supplied filters to Supabase.
    """
    _ = req  # explicitly unused


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[Project],
    status_code=status.HTTP_200_OK,
    summary="List projects",
    description=(
        "Fetch all projects from Supabase ordered by creation time (most recent first). "
        "This endpoint ignores all query parameters; no filters are forwarded to Supabase. "
        "Requires a valid Authorization bearer token."
    ),
    responses={
        200: {"description": "List of projects"},
        401: {"description": "Unauthorized"},
        500: {"description": "Unexpected server error"},
    },
)
async def list_projects(
    request: Request,
    supabase: SupabaseClient = Depends(get_supabase),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> List[Project]:
    """
    PUBLIC_INTERFACE
    Return all projects with task and bug counts sourced via head=True count queries on public.work_item.

    Authentication:
    - Requires Authorization: Bearer <token>. Returns 401 if missing or invalid.
    """
    try:
        # Enforce auth
        _ = await _require_valid_bearer_user(supabase, authorization)

        _ignore_query_params(request)
        rows = await _select_projects_with_counts(supabase)

        return [Project(**row) for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# PUBLIC_INTERFACE
@router.post(
    "",
    response_model=Project,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
    description="Create a new project in Supabase with the provided name, project_key, description, colour, and created_at.",
    responses={
        201: {"description": "Project created"},
        400: {"description": "Validation or Supabase error"},
        500: {"description": "Unexpected server error"},
    },
)
async def create_project(
    payload: CreateProjectRequest,
    supabase: SupabaseClient = Depends(get_supabase),
) -> Project:
    """
    Create a new project. Counts default to zero for new projects.
    """
    try:
        insert_payload = {
            "name": payload.name,
            "project_key": payload.project_key,
            "description": payload.description,
            "colour": payload.colour,
        }
        if payload.created_at:
            insert_payload["created_at"] = payload.created_at.isoformat()

        resp = (
            supabase.table("projects")
            .insert(insert_payload, returning="representation")
            .execute()
        )
        data = resp.data or []
        # In supabase-py v2, .data is typically a list when using returning='representation'
        if isinstance(data, list):
            created = data[0] if data else None
        else:
            created = data  # fallback if SDK returns a dict
        if not created:
            raise HTTPException(status_code=502, detail="Supabase did not return inserted project")
        created.setdefault("tasks_count", 0)
        created.setdefault("bugs_count", 0)
        return Project(**created)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# PUBLIC_INTERFACE
@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
    description=(
        "Delete a project by UUID. Returns 204 on successful deletion, "
        "404 if the project does not exist."
    ),
    responses={
        204: {"description": "Project deleted"},
        404: {"description": "Project not found"},
        400: {"description": "Validation or Supabase error"},
        500: {"description": "Unexpected server error"},
    },
)
async def delete_project(
    id: str = Path(..., description="Project UUID"),
    supabase: SupabaseClient = Depends(get_supabase),
) -> Response:
    """
    PUBLIC_INTERFACE
    Delete a project and return 204 No Content on success.

    Behavior:
    - Executes a delete on public.projects filtered by id.
    - Determines if any row was deleted by checking response.data length or response.count, if available.
    - Returns 404 if no rows were affected.

    Notes:
    - Related work items are expected to be deleted by ON DELETE CASCADE on foreign keys.
    """
    try:
        resp = (
            supabase.table("projects")
            .delete()
            .eq("id", id)
            .execute()
        )

        deleted_rows = 0
        if isinstance(resp.data, list):
            deleted_rows = len(resp.data)
        elif resp.data:
            deleted_rows = 1

        if deleted_rows == 0:
            affected = getattr(resp, "count", None)
            if not (isinstance(affected, int) and affected > 0):
                raise HTTPException(status_code=404, detail="Project not found")

        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
