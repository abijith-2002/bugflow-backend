from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status, Header
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
    # Optional display name resolved at creation time; may not exist on old rows.
    author_display_name: Optional[str] = Field(
        default=None,
        description="Author's display name at the time of commenting (resolved from user profile)"
    )
    created_at: datetime = Field(..., description="Timestamp when the comment was created")


class CreateCommentRequest(BaseModel):
    """Payload to create a new comment on a given work item."""
    body: str = Field(..., min_length=1, max_length=5000, description="Comment text content")
    # Accept author_id and author_display_name from client; if not provided, fall back to auth-derived values
    author_id: Optional[str] = Field(
        default=None,
        description="Optional Supabase user id of the commenter. If omitted, resolved from Authorization header when possible.",
    )
    author_display_name: Optional[str] = Field(
        default=None,
        description="Optional display name of the commenter. If omitted, resolved server-side or falls back to 'Anonymous'.",
    )

    @field_validator("body")
    @classmethod
    def body_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Comment body cannot be blank")
        return v.strip()


async def _resolve_user_from_bearer_token(
    supabase: SupabaseClient,
    authorization: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """
    Resolve (user_id, display_name) from the provided Authorization: Bearer <jwt> header.

    Strategy:
    - If token is present, call supabase.auth.get_user(token=...) to retrieve the user.
    - Prefer display name from user.user_metadata.display_name.
    - If not present, attempt to read 'users' public table with id = auth.user.id (best-effort).
    - Fallbacks:
        * display_name: 'Anonymous' if missing
        * user_id: None if cannot be determined
    """
    try:
        if not authorization:
            return None, "Anonymous"
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            token = parts[1].strip()
        else:
            # Malformed header; treat as anonymous
            return None, "Anonymous"

        # Get user info from Supabase Auth
        user_res = supabase.auth.get_user(token=token)
        user = getattr(user_res, "user", None)
        user_id = getattr(user, "id", None)

        display_name: Optional[str] = None
        # Try user_metadata
        if user and getattr(user, "user_metadata", None):
            meta = user.user_metadata or {}
            display_name = meta.get("display_name") or meta.get("full_name") or meta.get("name")

        # Best-effort lookup in a public 'users' table if present
        if (not display_name) and user_id:
            try:
                urow = (
                    supabase.table("users")
                    .select("display_name")
                    .eq("id", user_id)
                    .limit(1)
                    .execute()
                )
                if urow.data:
                    display_name = (urow.data[0] or {}).get("display_name")
            except Exception:
                # Ignore if table not found / RLS; just fallback
                pass

        if not display_name:
            display_name = str(user_id) if user_id else "Anonymous"

        return (str(user_id) if user_id else None), display_name
    except Exception:
        # On any failure, degrade gracefully
        return None, "Anonymous"


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
    description="Create a new comment for a given work item. Accepts optional author_id and author_display_name in payload; if omitted, these are resolved from the authenticated user or fall back to 'Anonymous'.",
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
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> Comment:
    """
    PUBLIC_INTERFACE
    Add a comment to an existing work item.

    Behavior:
    - Verifies the work item exists before inserting a comment (best-effort).
    - Accepts optional author_id and author_display_name in the payload; when provided, these are used as-is.
    - If optional fields are not provided, determines the current user based on Authorization: Bearer <token> and resolves display name.
    - Inserts into public.work_item_comment with (project_id, item_id, body, author_id, author_display_name).
    - Returns the inserted comment row.

    If user info is missing or not resolvable and not provided in payload, falls back to (author_id=None, author_display_name='Anonymous').
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
            # If select fails due to RLS or transient issues, proceed and let FK constraints handle it.
            pass

        # Resolve current user and display name from Supabase (used as fallback)
        resolved_author_id, resolved_display_name = await _resolve_user_from_bearer_token(
            supabase=supabase,
            authorization=authorization,
        )

        # Honor client-provided values if present, otherwise use resolved fallbacks
        effective_author_id = payload.author_id.strip() if isinstance(payload.author_id, str) and payload.author_id.strip() else resolved_author_id
        effective_display_name = (
            payload.author_display_name.strip()
            if isinstance(payload.author_display_name, str) and payload.author_display_name.strip()
            else resolved_display_name or "Anonymous"
        )

        insert_body = {
            "project_id": project_id,
            "item_id": id,
            "body": payload.body,
            "author_display_name": effective_display_name,
        }
        if effective_author_id:
            insert_body["author_id"] = effective_author_id

        # Insert comment
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
