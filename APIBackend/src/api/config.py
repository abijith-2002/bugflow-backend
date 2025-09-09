import os
from functools import lru_cache
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """
    Application settings loaded from environment variables.

    Required environment variables:
    - SUPABASE_URL: The base URL of your Supabase project (e.g., https://xyzcompany.supabase.co)
    - SUPABASE_ANON_KEY: The anon public API key for Supabase

    Notes:
    - Environment variables are automatically loaded from APIBackend/.env at app startup (see src/api/main.py).
    - You may override the .env path by setting ENV_PATH before starting the app.
    """
    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_ANON_KEY: str = Field(..., description="Supabase anon key")


# PUBLIC_INTERFACE
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings from environment variables."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "").strip()

    # Validate presence of mandatory env variables to avoid obscure 500s later
    missing = []
    if not supabase_url:
        missing.append("SUPABASE_URL")
    if not supabase_key:
        missing.append("SUPABASE_ANON_KEY")
    if missing:
        # Raise a clear error; route will convert to HTTP error in dependency
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Set them in APIBackend/.env (see .env.example and SUPABASE_SETUP.md)."
        )

    return Settings(
        SUPABASE_URL=supabase_url,
        SUPABASE_ANON_KEY=supabase_key,
    )
