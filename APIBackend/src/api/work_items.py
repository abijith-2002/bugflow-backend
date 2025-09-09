from datetime import datetime
from typing import List, Optional, Literal, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Path, Response
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
    # Optional creator field stored in DB as 'creator'
    creator: Optional[str] = Field(default=None, description="Display name of the user who created this item")
    created_at: datetime = Field(..., description="Creation timestamp")


class CreateWorkItemRequest(BaseModel):
    """Payload to create a new unified work item."""
    project_id: str = Field(..., description="UUID of the project")
    item_type: Literal["task", "bug"] = Field(..., description="Type of work item")
    title: str = Field(..., min_length=1, max_length=200, description="Title of the work item")
    description: Optional[str] = Field(default=None, description="Description of the work item")
    status: Optional[str] = Field(default=None, description="Initial status (default 'open')")
    priority: Optional[str] = Field(default=None, description="Priority label (e.g., low, medium, high)")
    # New optional field coming from client to store in DB column 'creator'
    created_by: Optional[str] = Field(default=None, description="Creator display name to store in 'creator' column")
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


class PatchWorkItemRequest(BaseModel):
    """
    Request payload to partially update a work item.
    Fields are optional; only provided fields will be updated.
    """
    title: Optional[str] = Field(default=None, min_length=1, max_length=200, description="New title")
    description: Optional[Optional[str]] = Field(default=None, description="New description (string or null)")
    status: Optional[str] = Field(default=None, min_length=1, max_length=40, description="New status")
    priority: Optional[Optional[str]] = Field(default=None, description="New priority label (string or null)")

    @field_validator("title")
    @classmethod
    def title_if_provided_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("title cannot be blank if provided")
        return v

    @field_validator("status")
    @classmethod
    def status_if_provided_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("status cannot be blank if provided")
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
        # Map created_by -> creator column if provided
        if isinstance(payload.created_by, str) and payload.created_by.strip():
            body["creator"] = payload.created_by.strip()
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
    "/{project_id}/{id}",
    response_model=WorkItem,
    status_code=status.HTTP_200_OK,
    summary="Partially update a work item",
    description="Update one or more fields (title, description, status, priority) of a work item identified by project_id and id. Returns the updated work item.",
    responses={
        200: {"description": "Work item updated"},
        400: {"description": "Validation or Supabase error"},
        404: {"description": "Work item not found"},
        500: {"description": "Unexpected server error"},
    },
)
async def patch_work_item(
    project_id: str = Path(..., description="UUID of the project"),
    id: int = Path(..., description="Numeric item id within the project"),
    payload: PatchWorkItemRequest = ...,
    supabase: SupabaseClient = Depends(get_supabase),
) -> WorkItem:
    """
    PUBLIC_INTERFACE
    Partially update a work item.

    Route:
    - PATCH /work-items/{project_id}/{id}

    Behavior:
    - Builds an update body with only provided fields.
    - If no fields are provided, returns 400.
    - Uses returning='representation' to fetch updated row; falls back to a follow-up select if needed.
    """
    try:
        update_body: Dict[str, Any] = {}

        if payload.title is not None:
            update_body["title"] = payload.title
        if payload.description is not None:
            # allow explicit null to clear the description
            update_body["description"] = payload.description
        if payload.status is not None:
            update_body["status"] = payload.status
        if payload.priority is not None:
            update_body["priority"] = payload.priority

        if not update_body:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        resp = (
            supabase.table("work_item")
            .update(update_body, returning="representation")
            .eq("project_id", project_id)
            .eq("id", id)
            .execute()
        )

        data = resp.data or []
        updated = data[0] if isinstance(data, list) and data else (data if data else None)

        if not updated:
            affected = getattr(resp, "count", None)
            if isinstance(affected, int) and affected > 0:
                fetch = (
                    supabase.table("work_item")
                    .select("*")
                    .eq("project_id", project_id)
                    .eq("id", id)
                    .limit(1)
                    .execute()
                )
                fetch_data = fetch.data or []
                updated = fetch_data[0] if isinstance(fetch_data, list) and fetch_data else None

        if not updated:
            raise HTTPException(status_code=404, detail="Work item not found")

        return WorkItem(**updated)
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

    Route:
    - PATCH /work-items/{project_id}/{id}/status

    Parameters:
    - project_id: UUID of the project the item belongs to.
    - id: Incremental numeric id of the item within the project.
    - payload.status: New status value.

    Behavior:
    - Executes an update with returning='representation'. Some Supabase configurations may
      return an empty 'data' array even when a row was updated (but 'count' gets populated).
      To avoid false 404s, if data is empty and count > 0, we perform a follow-up select to
      fetch the updated row.
    - Returns 404 only when both 'data' is empty and 'count' is 0 or None.

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
            # Some SDK responses may not include representation; check count as a fallback
            affected = getattr(resp, "count", None)
            if isinstance(affected, int) and affected > 0:
                # Follow-up read to fetch the updated item
                fetch = (
                    supabase.table("work_item")
                    .select("*")
                    .eq("project_id", project_id)
                    .eq("id", id)
                    .limit(1)
                    .execute()
                )
                fetch_data = fetch.data or []
                updated = fetch_data[0] if isinstance(fetch_data, list) and fetch_data else None

        if not updated:
            # No rows matched the filters
            raise HTTPException(status_code=404, detail="Work item not found")

        return WorkItem(**updated)
    except HTTPException:
        raise
    except Exception as e:
        # Map SDK or constraint errors to 400 by default
        raise HTTPException(status_code=400, detail=str(e))


# PUBLIC_INTERFACE
@router.delete(
    "/{project_id}/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a work item",
    description="Delete a work item identified by project_id and id. Returns 204 on success, 404 if not found.",
    responses={
        204: {"description": "Work item deleted"},
        404: {"description": "Work item not found"},
        400: {"description": "Validation or Supabase error"},
        500: {"description": "Unexpected server error"},
    },
)
async def delete_work_item(
    project_id: str = Path(..., description="UUID of the project"),
    id: int = Path(..., description="Numeric item id within the project"),
    supabase: SupabaseClient = Depends(get_supabase),
) -> Response:
    """
    PUBLIC_INTERFACE
    Delete a work item by composite key (project_id, id).

    Behavior:
    - Executes a delete with filters on project_id and id.
    - If the SDK response data is empty, uses resp.count (if available) to infer affected rows.
    - Returns 404 when no rows were affected; 204 No Content on successful deletion.
    """
    try:
        resp = (
            supabase.table("work_item")
            .delete()
            .eq("project_id", project_id)
            .eq("id", id)
            .execute()
        )

        # Determine if any row was deleted
        deleted_rows = 0
        if isinstance(resp.data, list):
            deleted_rows = len(resp.data)
        elif resp.data:
            deleted_rows = 1  # in case a dict is returned

        if deleted_rows == 0:
            affected = getattr(resp, "count", None)
            if not (isinstance(affected, int) and affected > 0):
                # Not found
                raise HTTPException(status_code=404, detail="Work item not found")

        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        # Surface as 400 for client/Supabase errors by default
        raise HTTPException(status_code=400, detail=str(e))
