from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
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

class GetDisplayNameRequest(BaseModel):
    """Request model containing the user id to look up in public.profiles."""
    user_id: str = Field(..., description="Supabase user id (UUID) to look up in public.profiles")

# PUBLIC_INTERFACE
@router.post(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Get user's display name by user id",
    description="Accepts a Supabase user_id from the client and returns display_name from public.profiles where id = user_id. Returns {'display_name': 'Anonymous'} if not found.",
    responses={
        200: {"description": "Resolved user's display name"},
        400: {"description": "Validation or Supabase error"},
        500: {"description": "Unexpected server error"},
    },
)
async def get_display_name_by_id(
    payload: GetDisplayNameRequest,
    supabase: SupabaseClient = Depends(get_supabase),
) -> dict:
    """
    PUBLIC_INTERFACE
    Fetch display_name from public.profiles using the provided user_id.

    Parameters:
    - user_id: Supabase auth user id (UUID as string)

    Returns:
    - {"display_name": "<name or Anonymous>"} — Anonymous if profile not found or empty.
    """
    try:
        uid = (payload.user_id or "").strip()
        if not uid:
            raise HTTPException(status_code=400, detail="user_id is required")

        prof = (
            supabase.table("profiles")
            .select("display_name")
            .eq("id", uid)
            .limit(1)
            .execute()
        )
        display_name = None
        if prof.data:
            display_name = (prof.data[0] or {}).get("display_name")
        if not (isinstance(display_name, str) and display_name.strip()):
            display_name = "Anonymous"
        return {"display_name": display_name}
    except HTTPException:
        raise
    except Exception as e:
        # Surface as 400 by default for DB/RLS/validation issues
        raise HTTPException(status_code=400, detail=str(e))
