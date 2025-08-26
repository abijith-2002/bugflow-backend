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
    return Settings(
        SUPABASE_URL=os.getenv("SUPABASE_URL", "").strip(),
        SUPABASE_ANON_KEY=os.getenv("SUPABASE_ANON_KEY", "").strip(),
        SITE_URL=os.getenv("SITE_URL", "").strip(),
    )
