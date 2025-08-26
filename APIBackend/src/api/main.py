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

# Ensure environment variables are available when app is imported, regardless of how it's started.
# This allows `uvicorn src.api.main:app` to work the same as `python run.py`.
try:
    from pathlib import Path
    from dotenv import load_dotenv  # type: ignore
    # Load .env from the APIBackend directory if present
    env_path = (Path(__file__).parent.parent / ".env")
    load_dotenv(dotenv_path=env_path)
except Exception:
    # dotenv is optional; ignore failures (e.g., not installed or file missing)
    pass

# Attempt to import auth router. If running from a different CWD where 'src' isn't on sys.path,
# adjust sys.path to include the APIBackend root so 'src' package can be resolved.
try:
    from src.api.auth import router as auth_router
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    api_dir = current_file.parent
    src_dir = api_dir.parent  # .../APIBackend/src
    api_backend_root = src_dir.parent  # .../APIBackend
    if str(api_backend_root) not in sys.path:
        sys.path.insert(0, str(api_backend_root))
    from src.api.auth import router as auth_router

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
    return {"message": "Healthy"}

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
