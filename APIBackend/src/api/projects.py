from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

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

    async def select_projects(self) -> list[dict]:
        """
        Fetch all projects ordered by created_at desc.
        """
        url = f"{self.base_url}/projects"
        params = {
            "select": "id,name,description,created_at",
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
            # On success, Supabase returns a JSON array
            return resp.json()

    async def insert_project(self, *, name: str, description: Optional[str]) -> dict:
        """
        Insert a new project row and return the created record.
        """
        url = f"{self.base_url}/projects"
        payload = [{"name": name, "description": description}]
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
            return {"name": name, "description": description}


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
    description: Optional[str] = Field(default=None, description="Project description")
    created_at: datetime = Field(..., description="Creation timestamp")


class CreateProjectRequest(BaseModel):
    """Payload to create a new project."""
    name: str = Field(..., min_length=1, max_length=200, description="Project name")
    description: Optional[str] = Field(default=None, description="Project description")


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[Project],
    status_code=status.HTTP_200_OK,
    summary="List projects",
    description="Fetch the list of projects from Supabase ordered by creation time (most recent first).",
    responses={
        200: {"description": "List of projects"},
        500: {"description": "Unexpected server error"},
    },
)
async def list_projects(db: SupabaseDBClient = Depends(get_db_client)) -> List[Project]:
    """
    Get all projects.

    Returns:
    - A list of Project objects fetched from Supabase.
    """
    try:
        rows = await db.select_projects()
        # Pydantic will coerce to the Project schema, raising if invalid
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
    description="Create a new project in Supabase with the provided name and description.",
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
    - name: Project name
    - description: Optional description

    Returns:
    - The created Project object including id and created_at.
    """
    try:
        created = await db.insert_project(name=payload.name, description=payload.description)
        # Ensure required fields exist; Supabase should return id and created_at
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
