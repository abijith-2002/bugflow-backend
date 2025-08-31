from datetime import datetime
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, status, Path
from pydantic import BaseModel, Field, field_validator
from supabase import Client as SupabaseClient

from .config import get_settings
from .supabase_client import SupabaseClientProvider

router = APIRouter(prefix="/work-items", tags=["Work Items"])


def get_supabase(settings=Depends(get_settings)) -> SupabaseClient:
    """PUBLIC_INTERFACE: Provide supabase client from settings."""
    try:
        provider = SupabaseClientProvider(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_ANON_KEY,
        )
        return provider.client()
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


class UpdateWorkItemStatusRequest(BaseModel):
    """Request payload to update the status of a work item."""
    status: str = Field(..., min_length=1, max_length=40, description="New workflow status")

    @field_validator("status")
    @classmethod
    def status_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("status cannot be blank")
        return v.strip()


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
    supabase: SupabaseClient = Depends(get_supabase),
) -> List[WorkItem]:
    """
    Retrieve unified work items from Supabase. Filter by project_id if provided.
    """
    try:
        query = supabase.table("work_item").select("*").order("created_at", desc=True)
        if isinstance(project_id, str) and project_id.strip():
            query = query.eq("project_id", project_id.strip())
        resp = query.execute()
        rows = resp.data or []
        return [WorkItem(**row) for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    supabase: SupabaseClient = Depends(get_supabase),
) -> WorkItem:
    """
    Create a new unified work item. The ID generation is handled in the database trigger to ensure correct sequencing.
    """
    try:
        body = {
            "project_id": payload.project_id,
            "item_type": payload.item_type,
            "title": payload.title,
            "description": payload.description,
        }
        if payload.status:
            body["status"] = payload.status
        if payload.priority:
            body["priority"] = payload.priority
        if payload.created_at:
            body["created_at"] = payload.created_at.isoformat()

        # In supabase-py v2, insert() may return a builder without .select().
        # Use PostgREST returning='representation' to fetch the inserted row directly.
        resp = (
            supabase.table("work_item")
            .insert(body, returning="representation")
            .execute()
        )
        data = resp.data or []
        # For supabase-py v2, returning='representation' usually yields a list
        if isinstance(data, list):
            created = data[0] if data else None
        else:
            created = data  # fallback if a dict is returned
        if not created:
            raise HTTPException(status_code=502, detail="Supabase did not return inserted work item")
        return WorkItem(**created)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# PUBLIC_INTERFACE
@router.patch(
    "/{project_id}/{id}/status",
    response_model=WorkItem,
    status_code=status.HTTP_200_OK,
    summary="Update work item status",
    description="Update the status field of a work item identified by project_id and id. Returns the updated work item.",
    responses={
        200: {"description": "Work item status updated"},
        400: {"description": "Validation or Supabase error"},
        404: {"description": "Work item not found"},
        500: {"description": "Unexpected server error"},
    },
)
async def update_work_item_status(
    project_id: str = Path(..., description="UUID of the project"),
    id: int = Path(..., description="Numeric item id within the project"),
    payload: UpdateWorkItemStatusRequest = ...,
    supabase: SupabaseClient = Depends(get_supabase),
) -> WorkItem:
    """
    PUBLIC_INTERFACE
    Update the status of a work item.

    Parameters:
    - project_id: UUID of the project the item belongs to.
    - id: Incremental numeric id of the item within the project.
    - payload.status: New status value.

    Returns:
    - The updated WorkItem.
    """
    try:
        # Perform update with returning representation to fetch the updated row.
        resp = (
            supabase.table("work_item")
            .update({"status": payload.status}, returning="representation")
            .eq("project_id", project_id)
            .eq("id", id)
            .execute()
        )
        data = resp.data or []
        updated = data[0] if isinstance(data, list) and data else (data if data else None)
        if not updated:
            # No rows matched the filters
            raise HTTPException(status_code=404, detail="Work item not found")
        return WorkItem(**updated)
    except HTTPException:
        raise
    except Exception as e:
        # Map SDK or constraint errors to 400 by default
        raise HTTPException(status_code=400, detail=str(e))
