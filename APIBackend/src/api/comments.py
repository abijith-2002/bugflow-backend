from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field, field_validator
from supabase import Client as SupabaseClient

from .config import get_settings
from .supabase_client import SupabaseClientProvider

router = APIRouter(prefix="/work-items", tags=["Comments"])


def get_supabase(settings=Depends(get_settings)) -> SupabaseClient:
    """PUBLIC_INTERFACE: Provide supabase client from settings."""
    try:
        provider = SupabaseClientProvider(
            supabase_url=settings.SUPABASE_URL, supabase_key=settings.SUPABASE_ANON_KEY
        )
        return provider.client()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")


class Comment(BaseModel):
    """Represents a single comment on a work item."""
    project_id: str = Field(..., description="UUID of the project that the work item belongs to")
    item_id: int = Field(..., description="Numeric work item id within the project")
    id: int = Field(..., description="Auto-increment comment id per (project_id, item_id)")
    body: str = Field(..., description="Comment text content")
    author_id: Optional[str] = Field(default=None, description="Optional Supabase user id of the commenter")
    created_at: datetime = Field(..., description="Timestamp when the comment was created")


class CreateCommentRequest(BaseModel):
    """Payload to create a new comment on a given work item."""
    body: str = Field(..., min_length=1, max_length=5000, description="Comment text content")
    author_id: Optional[str] = Field(default=None, description="Optional Supabase user id of the commenter")

    @field_validator("body")
    @classmethod
    def body_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Comment body cannot be blank")
        return v.strip()


# PUBLIC_INTERFACE
@router.get(
    "/{project_id}/{id}/comments",
    response_model=List[Comment],
    status_code=status.HTTP_200_OK,
    summary="List comments for a work item",
    description="Retrieve all comments for a work item identified by project_id and id. Results are ordered by created_at ascending.",
    responses={
        200: {"description": "List of comments"},
        500: {"description": "Unexpected server error"},
    },
)
async def list_comments(
    project_id: str = Path(..., description="UUID of the project"),
    id: int = Path(..., description="Numeric item id within the project"),
    supabase: SupabaseClient = Depends(get_supabase),
) -> List[Comment]:
    """
    PUBLIC_INTERFACE
    List comments associated with a specific work item (project_id, id).
    """
    try:
        resp = (
            supabase.table("work_item_comment")
            .select("*")
            .eq("project_id", project_id)
            .eq("item_id", id)
            .order("created_at", desc=False)
            .execute()
        )
        rows = resp.data or []
        return [Comment(**row) for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# PUBLIC_INTERFACE
@router.post(
    "/{project_id}/{id}/comments",
    response_model=Comment,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a work item",
    description="Create a new comment for a given work item. Returns the created comment.",
    responses={
        201: {"description": "Comment created"},
        400: {"description": "Validation or Supabase error"},
        404: {"description": "Work item not found"},
        500: {"description": "Unexpected server error"},
    },
)
async def add_comment(
    project_id: str = Path(..., description="UUID of the project"),
    id: int = Path(..., description="Numeric item id within the project"),
    payload: CreateCommentRequest = ...,
    supabase: SupabaseClient = Depends(get_supabase),
) -> Comment:
    """
    PUBLIC_INTERFACE
    Add a comment to an existing work item.

    Behavior:
    - Optionally verifies the work item exists before inserting a comment.
    - Inserts into public.work_item_comment with (project_id, item_id, body, author_id).
    - Returns the inserted comment row.
    """
    try:
        # Verify the work item exists (best-effort)
        try:
            w = (
                supabase.table("work_item")
                .select("id")
                .eq("project_id", project_id)
                .eq("id", id)
                .limit(1)
                .execute()
            )
            if not (w.data and len(w.data) > 0):
                raise HTTPException(status_code=404, detail="Work item not found")
        except HTTPException:
            raise
        except Exception:
            # If select fails due to RLS or transient issues, we proceed and let FK constraints handle it.
            pass

        insert_body = {
            "project_id": project_id,
            "item_id": id,
            "body": payload.body,
        }
        if payload.author_id:
            insert_body["author_id"] = payload.author_id

        resp = (
            supabase.table("work_item_comment")
            .insert(insert_body, returning="representation")
            .execute()
        )
        data = resp.data or []
        created = data[0] if isinstance(data, list) and data else (data if data else None)
        if not created:
            # Fall back to select latest (rare)
            fallback = (
                supabase.table("work_item_comment")
                .select("*")
                .eq("project_id", project_id)
                .eq("item_id", id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            created = fallback.data[0] if fallback.data else None

        if not created:
            raise HTTPException(status_code=502, detail="Supabase did not return inserted comment")

        return Comment(**created)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
