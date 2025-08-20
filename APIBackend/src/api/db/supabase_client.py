from typing import Optional

from supabase import Client, create_client

from src.api.config import get_settings

_supabase_client: Optional[Client] = None


# PUBLIC_INTERFACE
def get_supabase() -> Client:
    """
    Returns a singleton Supabase Client instance configured with environment variables.

    Uses SUPABASE_SERVICE_ROLE_KEY if provided, otherwise falls back to SUPABASE_ANON_KEY.
    """
    global _supabase_client
    if _supabase_client is None:
        settings = get_settings()
        supabase_key = settings.supabase_service_role_key or settings.supabase_anon_key
        _supabase_client = create_client(settings.supabase_url, supabase_key)
    return _supabase_client
