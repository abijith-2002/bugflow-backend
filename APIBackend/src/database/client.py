import os
from supabase import create_client, Client
from typing import Optional


class SupabaseClient:
    """Supabase client wrapper for database operations"""
    
    def __init__(self):
        self._client: Optional[Client] = None
        self._url = os.getenv("SUPABASE_URL")
        self._key = os.getenv("SUPABASE_KEY")
        self._service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self._url or not self._key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables are required")
    
    @property
    def client(self) -> Client:
        """Get Supabase client instance"""
        if not self._client:
            self._client = create_client(self._url, self._key)
        return self._client
    
    @property 
    def admin_client(self) -> Client:
        """Get Supabase admin client with service role key"""
        if not self._service_role_key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is required")
        return create_client(self._url, self._service_role_key)


# Global Supabase client instance
supabase_client = SupabaseClient()
