import os
from functools import lru_cache
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """
    Application settings loaded from environment variables.

    Required environment variables:
    - SUPABASE_URL: The base URL of your Supabase project (e.g., https://xyzcompany.supabase.co)
    - SUPABASE_ANON_KEY: The anon public API key for Supabase
    - SITE_URL: Public site URL used for email redirect links during signup (e.g., https://app.example.com)
    """
    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_ANON_KEY: str = Field(..., description="Supabase anon key")
    SITE_URL: str = Field(..., description="Public site URL for redirect links")


# PUBLIC_INTERFACE
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings from environment variables."""
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    site_url = os.getenv("SITE_URL", "").strip()

    # Validate presence of mandatory env variables to avoid obscure 500s later
    missing = []
    if not supabase_url:
        missing.append("SUPABASE_URL")
    if not supabase_key:
        missing.append("SUPABASE_ANON_KEY")
    if not site_url:
        missing.append("SITE_URL")
    if missing:
        # Raise a clear error; route will convert to HTTP error in dependency
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Set them in APIBackend/.env (see .env.example and SUPABASE_SETUP.md)."
        )

    return Settings(
        SUPABASE_URL=supabase_url,
        SUPABASE_ANON_KEY=supabase_key,
        SITE_URL=site_url,
    )
