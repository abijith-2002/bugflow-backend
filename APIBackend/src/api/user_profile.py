from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from supabase import Client as SupabaseClient

from .config import get_settings
from .supabase_client import SupabaseClientProvider

router = APIRouter(prefix="/users", tags=["Authentication"])

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
        "Fetch display_name from public.profiles for the authenticated user (id = auth user id). "
        "Falls back to user_metadata fields or Anonymous if not found."
    ),
    responses={
        200: {"description": "Resolved current user's display name"},
        401: {"description": "Unauthorized or invalid token"},
        500: {"description": "Unexpected server error"},
    },
)
async def get_me(
    supabase: SupabaseClient = Depends(get_supabase),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> CurrentUserProfileResponse:
    """
    PUBLIC_INTERFACE
    Resolve current user's display name:
    - Determine auth user id from Authorization bearer token.
    - Try public.profiles (id = user id) to read display_name.
    - If not found, try user_metadata on the auth user (full_name/name/username).
    - Fallback to 'Anonymous' when nothing is available.
    """
    try:
        user_id = await _resolve_current_user(supabase, authorization)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Prefer public.profiles.display_name if available
        src = "fallback"
        display_name: Optional[str] = None

        try:
            prof = (
                supabase.table("profiles")
                .select("display_name")
                .eq("id", user_id)
                .limit(1)
                .execute()
            )
            if prof.data:
                display_name = (prof.data[0] or {}).get("display_name")
                if display_name and isinstance(display_name, str) and display_name.strip():
                    src = "profiles"
        except Exception:
            # Ignore missing table or RLS issues; continue with metadata fallback
            pass

        # Fallback to user_metadata
        if not display_name:
            try:
                user_res = supabase.auth.get_user(token=authorization.split()[1]) if authorization else None
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

        return CurrentUserProfileResponse(user_id=str(user_id), display_name=display_name, source=src)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
