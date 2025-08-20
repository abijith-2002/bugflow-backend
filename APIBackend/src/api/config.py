import os
from typing import List

from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


class Settings:
    """
    Application settings loaded from environment variables.

    This class centralizes configuration required by the application including:
      - Supabase configuration (URL and keys)
      - Site URL used for auth redirect
      - CORS origins
    """

    def __init__(self) -> None:
        # Supabase Project configuration
        self.supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
        # Prefer Service Role key for server-side operations. Falls back to anon key if not provided.
        self.supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        self.supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "").strip()

        # Application site URL (required for Supabase email redirect on signup)
        self.app_site_url: str = os.getenv("APP_SITE_URL", "").strip()

        # CORS configuration (comma-separated origins or "*" for all)
        cors_env = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
        if cors_env == "*":
            self.cors_allow_origins: List[str] = ["*"]
        else:
            self.cors_allow_origins = [o.strip() for o in cors_env.split(",") if o.strip()]

        # Basic validation for essential configuration
        if not self.supabase_url:
            raise RuntimeError("Environment variable SUPABASE_URL is not set.")
        if not (self.supabase_service_role_key or self.supabase_anon_key):
            raise RuntimeError(
                "Provide SUPABASE_SERVICE_ROLE_KEY (recommended) or SUPABASE_ANON_KEY for Supabase access."
            )
        if not self.app_site_url:
            raise RuntimeError("Environment variable APP_SITE_URL is not set (used for auth email redirect).")


_settings: Settings | None = None


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Return a singleton Settings instance loaded from environment variables."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
