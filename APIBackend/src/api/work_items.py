from datetime import datetime
from typing import List, Optional, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from .config import get_settings

router = APIRouter(prefix="/work-items", tags=["Work Items"])


class SettingsAdapter(BaseModel):
    """Adapter to type the expected settings."""
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str


class SupabaseDBClient:
    """
    Minimal Supabase PostgREST client to access work_item and projects tables.
    """

    def __init__(self, supabase_url: str, supabase_key: str):
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL and Key must be provided via environment variables.")
        self.base_url = supabase_url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=representation",
        }

    async def list_work_items(self, project_id: Optional[str] = None) -> list[dict]:
        """
        Fetch work items, optionally filtered by project_id, newest first.
        """
        url = f"{self.base_url}/work_item"

        # Build params carefully to avoid PostgREST filter parsing issues.
        # PostgREST expects project_id=eq.<uuid> as a string query value.
        # Using a list of tuples preserves ordering and avoids accidental coercion.
        params: list[tuple[str, str]] = [("order", "created_at.desc")]

        # Only add filter if project_id looks like a non-empty string.
        if isinstance(project_id, str) and project_id.strip():
            params.append(("project_id", f"eq.{project_id.strip()}"))

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers, params=params, timeout=20.0)
            if resp.status_code >= 400:
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    ex.args = (*ex.args, f"Body: {resp.text}")
                    raise
            return resp.json()

    async def create_work_item(
        self,
        *,
        project_id: str,
        item_type: str,
        title: str,
        description: Optional[str],
        status: Optional[str],
        priority: Optional[str],
        created_at_iso: Optional[str],
    ) -> dict:
        """
        Insert a new work_item row. The database trigger assigns the next incremental id for the project.
        The item_key (<PROJECT_KEY>-<id>) is a generated column and will be returned by PostgREST.
        """
        url = f"{self.base_url}/work_item"
        body: dict = {
            "project_id": project_id,
            "item_type": item_type,
            "title": title,
            "description": description,
        }
        if status:
            body["status"] = status
        if priority:
            body["priority"] = priority
        if created_at_iso:
            body["created_at"] = created_at_iso

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
    """
    try:
        return SupabaseDBClient(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_ANON_KEY,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")


class WorkItem(BaseModel):
    """Unified Work Item entity that covers both tasks and bugs."""
    # Composite PK is (project_id, id). item_key is unique and exposed for clients.
    project_id: str = Field(..., description="UUID of the project this item belongs to")
    id: int = Field(..., description="Incremental number unique within the project")
    item_key: str = Field(..., description="Public ID in the form <PROJECT_KEY>-<NUMBER> (e.g., KAI-1)")
    item_type: Literal["task", "bug"] = Field(..., description="Type of work item")
    title: str = Field(..., description="Short title of the work item")
    description: Optional[str] = Field(default=None, description="Detailed description")
    status: str = Field(default="open", description="Workflow status")
    priority: Optional[str] = Field(default=None, description="Priority label")
    created_at: datetime = Field(..., description="Creation timestamp")


class CreateWorkItemRequest(BaseModel):
    """Payload to create a new unified work item."""
    project_id: str = Field(..., description="UUID of the project")
    item_type: Literal["task", "bug"] = Field(..., description="Type of work item")
    title: str = Field(..., min_length=1, max_length=200, description="Title of the work item")
    description: Optional[str] = Field(default=None, description="Description of the work item")
    status: Optional[str] = Field(default=None, description="Initial status (default 'open')")
    priority: Optional[str] = Field(default=None, description="Priority label (e.g., low, medium, high)")
    created_at: Optional[datetime] = Field(default=None, description="Creation time; if omitted, database default is used")

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title cannot be blank")
        return v


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[WorkItem],
    status_code=status.HTTP_200_OK,
    summary="List work items",
    description="List all work items, optionally filtered by project_id. Results are ordered by creation time (newest first).",
    responses={
        200: {"description": "List of work items"},
        500: {"description": "Unexpected server error"},
    },
)
async def list_work_items(
    project_id: Optional[str] = None,
    db: SupabaseDBClient = Depends(get_db_client),
) -> List[WorkItem]:
    """
    Retrieve unified work items from Supabase. Filter by project_id if provided.
    """
    try:
        rows = await db.list_work_items(project_id=project_id)
        return [WorkItem(**row) for row in rows]
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
    response_model=WorkItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a work item (task or bug)",
    description="Create a new work item within a project. The database assigns the next numeric id per project, and item_key is generated as <PROJECT_KEY>-<id>.",
    responses={
        201: {"description": "Work item created"},
        400: {"description": "Validation or Supabase error"},
        500: {"description": "Unexpected server error"},
    },
)
async def create_work_item(
    payload: CreateWorkItemRequest,
    db: SupabaseDBClient = Depends(get_db_client),
) -> WorkItem:
    """
    Create a new unified work item. The ID generation is handled in the database trigger to ensure correct sequencing.
    """
    try:
        created = await db.create_work_item(
            project_id=payload.project_id,
            item_type=payload.item_type,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            created_at_iso=payload.created_at.isoformat() if payload.created_at else None,
        )
        return WorkItem(**created)
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
