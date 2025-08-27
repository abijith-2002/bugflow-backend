import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env at application startup
# This ensures Settings() in config.py sees variables without external shell exporting.
try:
    from dotenv import load_dotenv
    # Resolve .env path relative to container root if running from elsewhere
    # Default to APIBackend/.env as requested
    default_env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    # Allow overriding via ENV_PATH if provided
    env_path = os.getenv("ENV_PATH", default_env_path)
    load_dotenv(dotenv_path=env_path)
except Exception:
    # Fail open: if dotenv isn't available or any error occurs, rely on process env
    # python-dotenv is listed in requirements.txt, so this is just a safeguard.
    pass

from .auth import router as auth_router
from .projects import router as projects_router

app = FastAPI(
    title="BugFlow API",
    description="RESTful API for BugFlow application integrating with Supabase for authentication.",
    version="0.1.0",
    openapi_tags=[
        {"name": "Health", "description": "Service health and diagnostics"},
        {"name": "Authentication", "description": "User sign-up and login endpoints via Supabase"},
    ],
)

# CORS for frontend consumption; tighten origins as needed via env in future
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend URL(s)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/", tags=["Health"], summary="Health Check", description="Basic health check endpoint to verify API is running")
def health_check():
    """Return service health."""
    return {"message": "Healthy"}

# Register routers
app.include_router(auth_router)
app.include_router(projects_router)
