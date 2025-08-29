from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
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


async def _select_projects_with_counts(supabase: SupabaseClient) -> list[dict]:
    """
    Fetch projects and compute counts from public.work_item.

    Implementation details:
    - Retrieve all projects, then for each project perform a grouped aggregate
      query via PostgREST selecting count:id grouped by item_type. This avoids
      ambiguity with head=True handling in some supabase-py versions and makes
      parsing explicit.
    - Robust defaulting: if rows are missing or parsing fails, default to 0.
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

    # 2) For each project, run a grouped aggregate by item_type with count:id
    for p in projects:
        pid = p.get("id")
        tasks_count = 0
        bugs_count = 0
        try:
            # Use postgrest client to request counts explicitly grouped by item_type
            # The "item_type,count:id" selection returns rows like:
            #   [{ "item_type": "task", "count": 3 }, { "item_type": "bug", "count": 1 }]
            # Note: group by via PostgREST is expressed by selecting columns; this relies
            # on PostgREST inferring implicit grouping. For explicit control one can use
            # rpc or a view; here we keep it simple and filter per project_id.
            resp = (
                supabase.postgrest.from_("work_item")
                .select("item_type,count:id")
                .eq("project_id", pid)
                .execute()
            )
            rows = resp.data or []
            # Some PostgREST setups may return numeric counts under key "count" or "count_id".
            # Normalize both possibilities.
            for r in rows:
                itype = r.get("item_type")
                cval = r.get("count")
                if cval is None:
                    # Fallback if backend returns alias as count_id
                    cval = r.get("count_id")
                try:
                    ival = int(cval) if cval is not None else 0
                except Exception:
                    ival = 0
                if itype == "task":
                    tasks_count = ival
                elif itype == "bug":
                    bugs_count = ival
        except Exception:
            # Default to zeros on any failure
            tasks_count = 0
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
        "This endpoint ignores all query parameters; no filters are forwarded to Supabase."
    ),
    responses={
        200: {"description": "List of projects"},
        500: {"description": "Unexpected server error"},
    },
)
async def list_projects(
    request: Request,
    supabase: SupabaseClient = Depends(get_supabase),
) -> List[Project]:
    """
    PUBLIC_INTERFACE
    Return all projects with aggregated task and bug counts sourced from public.work_item.
    """
    try:
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
