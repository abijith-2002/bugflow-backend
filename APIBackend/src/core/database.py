from supabase import create_client, Client
from .config import settings
import logging

logger = logging.getLogger(__name__)


class SupabaseConnection:
    """Supabase database connection manager."""
    
    def __init__(self):
        self._client: Client = None
        
    @property
    def client(self) -> Client:
        """Get Supabase client instance."""
        if self._client is None:
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
            logger.info("Supabase client initialized")
        return self._client
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            # Test with a simple query
            self.client.table("users").select("id").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False


# Global database instance
db = SupabaseConnection()


# PUBLIC_INTERFACE
def get_database() -> Client:
    """Get database client dependency for FastAPI routes."""
    return db.client
