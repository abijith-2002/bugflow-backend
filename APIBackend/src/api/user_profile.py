from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from supabase import Client as SupabaseClient

from .config import get_settings
from .supabase_client import SupabaseClientProvider

from .security import require_auth

router = APIRouter(prefix="/users", tags=["Authentication"], dependencies=[Depends(require_auth)])

def get_supabase(settings=Depends(get_settings)) -> SupabaseClient:
    """PUBLIC_INTERFACE: Provide supabase client from settings."""
    try:
        provider = SupabaseClientProvider(
            supabase_url=settings.SUPABASE_URL, supabase_key=settings.SUPABASE_ANON_KEY
        )
        return provider.client()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")

class CurrentUserProfileResponse(BaseModel):
    """Response model for current authenticated user's profile information."""
    user_id: Optional[str] = Field(default=None, description="Authenticated Supabase user id")
    display_name: Optional[str] = Field(default=None, description="Display name from public.profiles.display_name")
    source: str = Field(..., description="Where the display name was obtained from (profiles|metadata|fallback)")

async def _resolve_current_user(
    supabase: SupabaseClient,
    authorization: Optional[str],
) -> Optional[str]:
    """
    Resolve current user id from Authorization: Bearer <jwt>.
    Returns the user id string or None if not resolvable.
    """
    if not authorization:
        return None
    parts = authorization.split()
    if not (len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip()):
        return None
    token = parts[1].strip()
    try:
        user_res = supabase.auth.get_user(token=token)
        user = getattr(user_res, "user", None)
        return getattr(user, "id", None)
    except Exception:
        return None

# PUBLIC_INTERFACE
@router.get(
    "/me",
    response_model=CurrentUserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user's display name",
    description=(
        "Fetch display_name from public.profiles. "
        "If 'user_id' query parameter is provided, the endpoint will return the display_name for that user id. "
        "Otherwise, it uses the Authorization bearer token to resolve the current user id and then fetches display_name. "
        "Falls back to user_metadata fields or Anonymous if not found."
    ),
    responses={
        200: {"description": "Resolved current user's display name"},
        400: {"description": "Validation error (e.g., missing/invalid user_id)"},
        401: {"description": "Unauthorized or invalid token (when user_id is not provided)"},
        404: {"description": "Profile not found for provided user_id"},
        500: {"description": "Unexpected server error"},
    },
)
async def get_me(
    supabase: SupabaseClient = Depends(get_supabase),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    user_id: Optional[str] = None,
) -> CurrentUserProfileResponse:
    """
    PUBLIC_INTERFACE
    Resolve a user's display name.

    Behavior:
    - If the optional 'user_id' query parameter is provided:
        * Validate it as a non-empty string.
        * Query public.profiles where id = user_id for display_name.
        * If a profile row exists but display_name is null/blank, return "Anonymous" with source="profiles".
        * If no profile row exists, return 404 Profile not found.
        * Return payload with source='profiles'.
    - If 'user_id' is not provided:
        * Determine current auth user id from Authorization bearer token.
        * Try public.profiles (id = user id) to read display_name.
        * If not found, try user_metadata on the auth user (full_name/name/username).
        * Fallback to 'Anonymous' when nothing is available.
    """
    try:
        # If user_id query param is present, use it directly
        if user_id is not None:
            uid = user_id.strip()
            if not uid:
                raise HTTPException(status_code=400, detail="user_id must be a non-empty string")

            try:
                prof = (
                    supabase.table("profiles")
                    .select("display_name")
                    .eq("id", uid)
                    .limit(1)
                    .execute()
                )
            except Exception as e:
                # Map unexpected Supabase errors to 400 for client context
                raise HTTPException(status_code=400, detail=str(e))

            # Normalize response shape and determine if a profile row exists
            rows = []
            if prof is not None:
                if isinstance(getattr(prof, "data", None), list):
                    rows = prof.data or []
                elif isinstance(getattr(prof, "data", None), dict):
                    # Some setups may return a dict; wrap it for uniform handling
                    rows = [prof.data]
            if not rows:
                # No profile row found for the given user id
                raise HTTPException(status_code=404, detail="Profile not found")

            # Extract display_name safely
            candidate = (rows[0] or {}).get("display_name")
            if isinstance(candidate, str) and candidate.strip():
                name = candidate.strip()
            else:
                # Profile exists but display_name missing/blank -> return Anonymous with profiles source
                name = "Anonymous"

            return CurrentUserProfileResponse(user_id=uid, display_name=name, source="profiles")

        # Otherwise, behave like previous implementation (current user resolution)
        resolved_user_id = await _resolve_current_user(supabase, authorization)
        if not resolved_user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        src = "fallback"
        display_name: Optional[str] = None

        # Prefer public.profiles.display_name if available
        try:
            prof = (
                supabase.table("profiles")
                .select("display_name")
                .eq("id", resolved_user_id)
                .limit(1)
                .execute()
            )
            rows = prof.data or []
            if isinstance(rows, dict):
                rows = [rows]
            if rows:
                dn = (rows[0] or {}).get("display_name")
                if isinstance(dn, str) and dn.strip():
                    display_name = dn.strip()
                    src = "profiles"
        except Exception:
            # Ignore missing table or RLS issues; continue with metadata fallback
            pass

        # Fallback to user_metadata
        if not display_name:
            try:
                token = authorization.split()[1] if authorization else None
                user_res = supabase.auth.get_user(token=token) if token else None
                user = getattr(user_res, "user", None) if user_res else None
                meta = getattr(user, "user_metadata", None) or {}
                for key in ("display_name", "full_name", "name", "username"):
                    val = meta.get(key)
                    if isinstance(val, str) and val.strip():
                        display_name = val.strip()
                        src = "metadata"
                        break
            except Exception:
                # ignore
                pass

        if not display_name:
            display_name = "Anonymous"
            src = "fallback"

        return CurrentUserProfileResponse(
            user_id=str(resolved_user_id),
            display_name=display_name,
            source=src,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GetDisplayNameRequest(BaseModel):
    """Request model for POST /users/me to lookup a specific user's display_name by id."""
    user_id: str = Field(..., description="Supabase user id (UUID) to look up in public.profiles")

# PUBLIC_INTERFACE
@router.post(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Get user's display name by user id",
    description="Accepts a Supabase user_id from the client and returns display_name from public.profiles where id = user_id. Returns [{'display_name':'Anonymous'}] if not found.",
    responses={
        200: {"description": "Resolved user's display name"},
        400: {"description": "Validation or Supabase error"},
        500: {"description": "Unexpected server error"},
    },
)
async def get_display_name_by_id(
    payload: GetDisplayNameRequest,
    supabase: SupabaseClient = Depends(get_supabase),
) -> List[dict]:
    """
    PUBLIC_INTERFACE
    POST /users/me

    Purpose:
    - Mirror a direct SQL select display_name from public.profiles where id = :user_id
      and return an array of objects like: [{"display_name":"<name>"}].

    Behavior:
    - If a matching row is found, return [{"display_name": "<value>"}].
    - If not found or display_name is null/blank, return [{"display_name": "Anonymous"}].
    """
    try:
        user_id = payload.user_id.strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id must be a non-empty string")

        resp = (
            supabase.table("profiles")
            .select("display_name")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        name = None
        if resp and isinstance(resp.data, list) and resp.data:
            candidate = (resp.data[0] or {}).get("display_name")
            if isinstance(candidate, str) and candidate.strip():
                name = candidate.strip()

        if not name:
            name = "Anonymous"

        # Return as array of objects like SQL: [{"display_name": "name"}]
        return [{"display_name": name}]
    except HTTPException:
        raise
    except Exception as e:
        # Map general Supabase or runtime errors to 400 by default
        raise HTTPException(status_code=400, detail=str(e))
