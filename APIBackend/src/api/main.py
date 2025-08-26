"""
FastAPI application for the BugFlow backend.

Exposes:
- Health endpoint at GET /
- Authentication endpoints at POST /signup and POST /login (Supabase-backed)

OpenAPI is configured with descriptive tags. CORS is enabled using FRONTEND_ORIGIN
environment variable (default "*").
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter
import os
import logging

logger = logging.getLogger("bugflow.api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# Ensure environment variables are available when app is imported, regardless of how it's started.
# Explicitly resolve APIBackend/.env using an absolute path so CWD/import context do not matter.
dotenv_loaded = False
dotenv_path_str = ""
try:
    import sys
    from pathlib import Path
    from dotenv import load_dotenv  # type: ignore

    # Main file: .../APIBackend/src/api/main.py
    current_file = Path(__file__).resolve()
    api_dir = current_file.parent                  # .../APIBackend/src/api
    src_dir = api_dir.parent                       # .../APIBackend/src
    api_backend_root = src_dir.parent              # .../APIBackend

    # Compute .env absolute path: .../APIBackend/.env
    env_path = (api_backend_root / ".env").resolve()
    dotenv_path_str = str(env_path)

    # Load the .env strictly from APIBackend root
    dotenv_loaded = load_dotenv(dotenv_path=env_path)
    logger.info(
        "Env load attempt: path=%s loaded=%s exists=%s",
        dotenv_path_str, dotenv_loaded, env_path.exists()
    )

    # Also ensure APIBackend root on sys.path so 'src' imports resolve regardless of CWD
    if str(api_backend_root) not in sys.path:
        sys.path.insert(0, str(api_backend_root))
        logger.info("Adjusted sys.path to include APIBackend root: %s", api_backend_root)
except Exception as e:
    # dotenv is optional; log failure (e.g., not installed or file missing)
    logger.warning("Env load failed via python-dotenv: %s", e)

# Log current working directory and sys.path for diagnosing container run contexts
try:
    import sys as _sys
    logger.info("Process CWD: %s", os.getcwd())
    logger.info("sys.path contains APIBackend? %s", any("APIBackend" in p for p in _sys.path))
except Exception:
    pass

# Snapshot critical env presence after attempted load
logger.info(
    "Startup env snapshot: SUPABASE_URL_present=%s SUPABASE_ANON_KEY_present=%s FRONTEND_ORIGIN=%s",
    bool(os.getenv("SUPABASE_URL")), bool(os.getenv("SUPABASE_ANON_KEY")), os.getenv("FRONTEND_ORIGIN", "<unset>")
)

# Import routers (sys.path already adjusted above if necessary)
from src.api.auth import router as auth_router  # noqa: E402

openapi_tags = [
    {"name": "Health", "description": "Service health and utility endpoints"},
    {"name": "Authentication", "description": "User authentication via Supabase (signup and login)"},
]

# PUBLIC_INTERFACE
def get_openapi_tags():
    """Return the OpenAPI tag definitions used by the application."""
    return openapi_tags

# PUBLIC_INTERFACE
app = FastAPI(
    title="BugFlow API",
    description="Backend API for the BugFlow bug tracking application. Handles auth and business logic.",
    version="0.1.0",
    openapi_tags=openapi_tags,
)

# CORS: allow frontend origin if provided, otherwise permissive for development
frontend_origin = os.getenv("FRONTEND_ORIGIN", "*")
allow_origins = [frontend_origin] if frontend_origin != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health router
health_router = APIRouter()

# PUBLIC_INTERFACE
@health_router.get(
    "/",
    tags=["Health"],
    summary="Health Check",
    description="Simple health check endpoint to verify the API is running.",
)
def health_check():
    """Return basic service health indicator."""
    return {
        "message": "Healthy",
        "env_loaded": dotenv_loaded,
        "supabase_url": bool(os.getenv("SUPABASE_URL")),
        "supabase_key": bool(os.getenv("SUPABASE_ANON_KEY")),
        "dotenv_path": dotenv_path_str,
    }

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
