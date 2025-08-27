from functools import lru_cache

from supabase import Client, create_client  # supabase-py SDK

# PUBLIC_INTERFACE
def get_supabase_client(supabase_url: str, supabase_key: str) -> Client:
    """Create and return a Supabase Python client.

    This factory uses supabase-py to interact with both Auth and PostgREST.
    """
    if not supabase_url or not supabase_key:
        raise ValueError("Supabase URL and Key must be provided via environment variables.")
    return create_client(supabase_url.strip(), supabase_key.strip())


class SupabaseClientProvider:
    """Helper to lazily construct and cache a Supabase client."""

    def __init__(self, supabase_url: str, supabase_key: str):
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL and Key must be provided via environment variables.")
        self._url = supabase_url
        self._key = supabase_key

    @lru_cache(maxsize=1)
    def client(self) -> Client:
        return get_supabase_client(self._url, self._key)
