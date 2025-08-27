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
        Fetch all projects and attach accurate tasks_count and bugs_count derived from
        public.work_item by grouping on (project_id, item_type). For each project:
          - tasks_count = count of rows where project_id = project.id AND item_type = 'task'
          - bugs_count  = count of rows where project_id = project.id AND item_type = 'bug'
        Defaults to 0 if there are no matching work_item rows. Results are ordered by created_at desc.
        """
        projects_url = f"{self.base_url}/projects"
        work_item_url = f"{self.base_url}/work_item"

        # Query projects (newest first)
        proj_params: list[tuple[str, str]] = [
            ("select", "id,name,project_key,description,colour,created_at"),
            ("order", "created_at.desc"),
        ]

        def _safe_uuid(v) -> Optional[str]:
            try:
                if isinstance(v, str) and v.strip():
                    return v
            except Exception:
                pass
            return None

        def _safe_int(v, default: int = 0) -> int:
            try:
                if v is None:
                    return default
                if isinstance(v, int):
                    return v
                if isinstance(v, float):
                    if v != v:  # NaN
                        return default
                    return int(v)
                if isinstance(v, str) and v.strip():
                    return int(float(v)) if "." in v else int(v)
            except Exception:
                return default
            return default

        async with httpx.AsyncClient() as client:
            # 1) Fetch all projects
            proj_resp = await client.get(
                projects_url, headers=self.headers, params=proj_params, timeout=20.0
            )
            if proj_resp.status_code >= 400:
                try:
                    proj_resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    ex.args = (*ex.args, f"Body: {proj_resp.text}")
                    raise

            projects_json = proj_resp.json()
            projects: list[dict] = projects_json if isinstance(projects_json, list) else []
            for p in projects:
                if isinstance(p, dict):
                    p["tasks_count"] = 0
                    p["bugs_count"] = 0

            if not projects:
                return []

            # 2) Aggregate counts in one request grouped by project_id and item_type
            # PostgREST aggregation syntax: select=project_id,item_type,count:id&group=project_id,item_type
            agg_params: list[tuple[str, str]] = [
                ("select", "project_id,item_type,count:id"),
                ("group", "project_id,item_type"),
            ]
            agg_resp = await client.get(
                work_item_url, headers=self.headers, params=agg_params, timeout=20.0
            )
            if agg_resp.status_code >= 400:
                try:
                    agg_resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    ex.args = (*ex.args, f"Body: {agg_resp.text}")
                    raise

            agg_rows = agg_resp.json()
            # Build mapping: project_id -> {"task": n, "bug": m}
            counts_by_pid: dict[str, dict[str, int]] = {}
            if isinstance(agg_rows, list):
                for row in agg_rows:
                    if not isinstance(row, dict):
                        continue
                    pid = _safe_uuid(row.get("project_id"))
                    item_type = row.get("item_type")
                    if not pid or item_type not in ("task", "bug"):
                        continue

                    # Normalize count key name variations
                    raw_count = (
                        row.get("count")
                        if "count" in row
                        else row.get("count_id", row.get("count_id()"))
                    )
                    n = _safe_int(raw_count, 0)
                    bucket = counts_by_pid.setdefault(pid, {})
                    bucket[item_type] = n

            # 3) Merge counts into projects, defaulting to 0
            for p in projects:
                if not isinstance(p, dict):
                    continue
                pid = _safe_uuid(p.get("id"))
                if not pid:
                    p["tasks_count"] = 0
                    p["bugs_count"] = 0
                    continue
                bucket = counts_by_pid.get(pid, {})
                p["tasks_count"] = _safe_int(bucket.get("task", 0), 0)
                p["bugs_count"] = _safe_int(bucket.get("bug", 0), 0)

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
