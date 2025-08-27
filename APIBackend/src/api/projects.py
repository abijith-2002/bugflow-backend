from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, field_validator

from .config import get_settings

router = APIRouter(prefix="/projects", tags=["Projects"])


class SettingsAdapter(BaseModel):
    """Adapter model to satisfy type checking for dependency return."""
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str


class SupabaseDBClient:
    """
    Minimal Supabase PostgREST client implemented with httpx.

    Uses Supabase REST endpoints exposed at {SUPABASE_URL}/rest/v1/{table} with 'apikey' and 'Authorization' headers.
    SECURITY INVARIANT: This client never accepts arbitrary query parameters for project listing.
    """

    def __init__(self, supabase_url: str, supabase_key: str):
        if not supabase_url or not supabase_key:
            raise ValueError(
                "Supabase URL and Key must be provided via environment variables."
            )
        self.base_url: str = supabase_url.rstrip("/") + "/rest/v1"
        self.headers: dict = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # 'Prefer: return=representation' ensures created rows are returned
            "Prefer": "return=representation",
        }

    async def select_projects_with_counts(self) -> list[dict]:
        """
        Fetch all project records from projects and compute tasks_count and bugs_count
        from work_item grouped by project_id. Ensure zero counts when none exist.
        Order projects by created_at desc.

        Optimization/robustness:
        - If work_item is empty, skip aggregation queries and return zero counts.
        """
        # Endpoints
        projects_url = f"{self.base_url}/projects"
        work_item_url = f"{self.base_url}/work_item"

        # Params for projects list
        proj_params: list[tuple[str, str]] = [
            ("select", "id,name,project_key,description,colour,created_at"),
            ("order", "created_at.desc"),
        ]

        async with httpx.AsyncClient() as client:
            # 1) Fetch projects
            proj_resp = await client.get(
                projects_url, headers=self.headers, params=proj_params, timeout=20.0
            )
            if proj_resp.status_code >= 400:
                try:
                    proj_resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    ex.args = (*ex.args, f"Body: {proj_resp.text}")
                    raise
            projects = proj_resp.json() or []

            # Helper to set zero counts on projects
            def attach_zero_counts() -> list[dict]:
                for p in projects:
                    p["tasks_count"] = 0
                    p["bugs_count"] = 0
                return projects

            # 2) Check if work_item has any rows; if none, return zero counts
            head_params: list[tuple[str, str]] = [
                ("select", "project_id"),
                ("limit", "1"),
            ]
            head_resp = await client.get(
                work_item_url, headers=self.headers, params=head_params, timeout=15.0
            )
            if head_resp.status_code >= 400:
                try:
                    head_resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    ex.args = (*ex.args, f"Body: {head_resp.text}")
                    raise
            head_rows = head_resp.json() or []
            if not head_rows:
                return attach_zero_counts()

            # 3) Perform aggregations only if table was not empty
            # Count tasks (item_type='task') grouped by project_id
            task_params: list[tuple[str, str]] = [
                ("select", "project_id,count:id"),
                ("item_type", "eq.task"),
                ("group", "project_id"),
            ]
            tasks_resp = await client.get(
                work_item_url, headers=self.headers, params=task_params, timeout=20.0
            )
            if tasks_resp.status_code >= 400:
                try:
                    tasks_resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    ex.args = (*ex.args, f"Body: {tasks_resp.text}")
                    raise
            task_rows = tasks_resp.json() or []
            tasks_map = {
                r["project_id"]: int(r.get("count", 0))
                for r in task_rows
                if isinstance(r, dict) and "project_id" in r
            }

            # Count bugs (item_type='bug') grouped by project_id
            bug_params: list[tuple[str, str]] = [
                ("select", "project_id,count:id"),
                ("item_type", "eq.bug"),
                ("group", "project_id"),
            ]
            bugs_resp = await client.get(
                work_item_url, headers=self.headers, params=bug_params, timeout=20.0
            )
            if bugs_resp.status_code >= 400:
                try:
                    bugs_resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    ex.args = (*ex.args, f"Body: {bugs_resp.text}")
                    raise
            bug_rows = bugs_resp.json() or []
            bugs_map = {
                r["project_id"]: int(r.get("count", 0))
                for r in bug_rows
                if isinstance(r, dict) and "project_id" in r
            }

        # Merge counts into each project; default to 0
        for p in projects:
            pid = p.get("id")
            p["tasks_count"] = tasks_map.get(pid, 0)
            p["bugs_count"] = bugs_map.get(pid, 0)
        return projects

    async def insert_project(
        self,
        *,
        name: str,
        project_key: str,
        description: Optional[str],
        colour: Optional[str],
        created_at: Optional[str],
    ) -> dict:
        """Insert a new project and return the created record."""
        url = f"{self.base_url}/projects"
        body: dict = {
            "name": name,
            "project_key": project_key,
            "description": description,
            "colour": colour,
        }
        if created_at:
            body["created_at"] = created_at

        payload = [body]
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json=payload, timeout=20.0)
            if resp.status_code >= 400:
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    ex.args = (*ex.args, f"Body: {resp.text}")
                    raise
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0]
            if isinstance(data, dict):
                return data
            return body


def get_db_client(settings: SettingsAdapter = Depends(get_settings)) -> SupabaseDBClient:
    """
    PUBLIC_INTERFACE
    Build a SupabaseDBClient using validated settings.
    Converts configuration errors into HTTPExceptions for clearer API responses.
    """
    try:
        return SupabaseDBClient(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_ANON_KEY,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")


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
    db: SupabaseDBClient = Depends(get_db_client),
) -> List[Project]:
    """
    PUBLIC_INTERFACE
    Return all projects with aggregated task and bug counts sourced from public.work_item.

    Parameters:
    - none (query parameters are ignored)

    Returns:
    - List[Project]: Each object includes tasks_count and bugs_count with zero defaults.
    """
    try:
        _ignore_query_params(request)
        rows = await db.select_projects_with_counts()
        return [Project(**row) for row in rows]
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response is not None else 500
        try:
            detail_json = e.response.json() if e.response is not None else None
        except Exception:
            detail_json = None
        if isinstance(detail_json, dict):
            detail = (
                detail_json.get("message")
                or detail_json.get("error")
                or detail_json.get("msg")
                or e.response.text
            )
        else:
            detail = e.response.text if e.response is not None else str(e)
        raise HTTPException(status_code=status_code, detail=detail)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supabase network error: {str(e)}")
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected server error")


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
    db: SupabaseDBClient = Depends(get_db_client),
) -> Project:
    """
    Create a new project. Counts default to zero for new projects.
    """
    try:
        created = await db.insert_project(
            name=payload.name,
            project_key=payload.project_key,
            description=payload.description,
            colour=payload.colour,
            created_at=payload.created_at.isoformat() if payload.created_at else None,
        )
        created.setdefault("tasks_count", 0)
        created.setdefault("bugs_count", 0)
        return Project(**created)
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response is not None else 400
        try:
            detail_json = e.response.json() if e.response is not None else None
        except Exception:
            detail_json = None
        if isinstance(detail_json, dict):
            detail = (
                detail_json.get("message")
                or detail_json.get("error_description")
                or detail_json.get("error")
                or detail_json.get("msg")
                or e.response.text
            )
        else:
            detail = e.response.text if e.response is not None else str(e)
        raise HTTPException(status_code=status_code, detail=detail)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supabase network error: {str(e)}")
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected server error")
