from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
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
    """

    def __init__(self, supabase_url: str, supabase_key: str):
        if not supabase_url or not supabase_key:
            raise ValueError(
                "Supabase URL and Key must be provided via environment variables."
            )
        self.base_url = supabase_url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # 'Prefer: return=representation' ensures created rows are returned
            "Prefer": "return=representation",
        }

    async def select_projects_with_counts(self) -> list[dict]:
        """
        Fetch all projects with aggregated counts for tasks and bugs, ordered by created_at desc.

        This assumes you have tables 'tasks' and 'bugs' with a foreign key column 'project_id' referencing projects.id.
        Supabase PostgREST supports count via a related subselect using the form:
          related_table!foreign_key(count)
        and aliasing via count:alias.

        If your schema uses different table names or foreign key names, adjust the select parameter accordingly.
        """
        url = f"{self.base_url}/projects"
        # Using PostgREST embedded resources with count aggregation.
        # Format: related_table!fk(count) and alias counts via count:tasks and count:bugs
        params = {
            "select": (
                "id,name,project_key,description,colour,created_at,"
                "tasks:tasks!tasks_project_id_fkey(count),"
                "bugs:bugs!bugs_project_id_fkey(count)"
            ),
            "order": "created_at.desc",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers, params=params, timeout=20.0)
            if resp.status_code >= 400:
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    ex.args = (*ex.args, f"Body: {resp.text}")
                    raise
            data = resp.json()
            # Normalize counts: Supabase returns objects like {"count": 3} for each alias.
            for row in data:
                # When there are no related rows, PostgREST may return null. Coerce to 0.
                tasks_obj = row.get("tasks")
                bugs_obj = row.get("bugs")
                row["tasks"] = (tasks_obj or {}).get("count", 0) if isinstance(tasks_obj, dict) else (0 if tasks_obj is None else tasks_obj)
                row["bugs"] = (bugs_obj or {}).get("count", 0) if isinstance(bugs_obj, dict) else (0 if bugs_obj is None else bugs_obj)
            return data

    async def insert_project(
        self,
        *,
        name: str,
        project_key: str,
        description: Optional[str],
        colour: Optional[str],
        created_at: Optional[str],
    ) -> dict:
        """
        Insert a new project row and return the created record.
        """
        url = f"{self.base_url}/projects"
        body: dict = {
            "name": name,
            "project_key": project_key,
            "description": description,
            "colour": colour,
        }
        # Allow client-provided created_at if present (ISO 8601 string). Otherwise DB default will populate.
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
            # With Prefer: return=representation, result is a list with the created row
            if isinstance(data, list) and data:
                return data[0]
            if isinstance(data, dict):
                return data
            # Fallback if nothing returned
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
    # Add counts for dashboard cards
    tasks: int = Field(default=0, description="Total tasks count associated with this project")
    bugs: int = Field(default=0, description="Total bugs count associated with this project")


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
        # Basic format: letters, numbers, dashes and underscores only; uppercase recommended but not enforced
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        if not v or any(ch not in allowed for ch in v):
            raise ValueError("project_key may contain only letters, numbers, '-' and '_'")
        return v


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[Project],
    status_code=status.HTTP_200_OK,
    summary="List projects",
    description="Fetch the list of projects from Supabase ordered by creation time (most recent first), including aggregated 'tasks' and 'bugs' counts.",
    responses={
        200: {"description": "List of projects"},
        500: {"description": "Unexpected server error"},
    },
)
async def list_projects(db: SupabaseDBClient = Depends(get_db_client)) -> List[Project]:
    """
    Get all projects with tasks and bugs counts aggregated from related tables.

    Returns:
    - A list of Project objects fetched from Supabase with fields:
      id, name, project_key, description, colour, created_at, tasks, bugs
    """
    try:
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
    Create a new project.

    Parameters:
    - name: Project name (required)
    - project_key: Short unique project key (required)
    - description: Optional description
    - colour: Optional colour (CSS/hex)
    - created_at: Optional creation timestamp; if omitted DB default is used

    Returns:
    - The created Project object including id and created_at.

    Error handling:
    - 400 for validation or upstream Supabase errors
    - 502 for network errors
    - 500 for unexpected server errors
    """
    try:
        created = await db.insert_project(
            name=payload.name,
            project_key=payload.project_key,
            description=payload.description,
            colour=payload.colour,
            created_at=payload.created_at.isoformat() if payload.created_at else None,
        )
        # When creating, tasks/bugs counts default to 0
        created.setdefault("tasks", 0)
        created.setdefault("bugs", 0)
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
