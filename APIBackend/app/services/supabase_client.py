from supabase import create_client, Client
from ..config import get_settings

settings = get_settings()

def get_supabase_client() -> Client:
    """
    Create and return a Supabase client instance.
    
    Returns:
        Client: Supabase client instance
    """
    return create_client(settings.supabase_url, settings.supabase_key)

def get_supabase_anon_client() -> Client:
    """
    Create and return a Supabase client instance with anonymous key.
    Used for user registration and authentication.
    
    Returns:
        Client: Supabase client instance with anon key
    """
    return create_client(settings.supabase_url, settings.supabase_anon_key)

# Global client instances
supabase_client = get_supabase_client()
supabase_anon_client = get_supabase_anon_client()
