import os
from functools import lru_cache
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """
    Application settings loaded from environment variables.

    Required environment variables (for endpoints that interact with Supabase):
    - SUPABASE_URL: The base URL of your Supabase project (e.g., https://xyzcompany.supabase.co)
    - SUPABASE_ANON_KEY: The anon public API key for Supabase

    Notes:
    - Environment variables are automatically loaded from APIBackend/.env at app startup (see src/api/main.py).
    - You may override the .env path by setting ENV_PATH before starting the app.
    - Importantly, we DO NOT raise during import-time if values are missing to allow the app to start
      and expose health/docs routes. Endpoints that require Supabase will validate presence and
      return a clear 500 error if configuration is missing.
    """
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_ANON_KEY: str = Field(default="", description="Supabase anon key")

    def is_supabase_configured(self) -> bool:
        """Return True if both SUPABASE_URL and SUPABASE_ANON_KEY are present."""
        return bool(self.SUPABASE_URL and self.SUPABASE_ANON_KEY)


# PUBLIC_INTERFACE
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings from environment variables without raising on missing values."""
    supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
    supabase_key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
    return Settings(
        SUPABASE_URL=supabase_url,
        SUPABASE_ANON_KEY=supabase_key,
    )
