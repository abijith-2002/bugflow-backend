from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import get_settings
from src.api.routes.auth import router as auth_router
from src.api.routes.projects import router as projects_router
from src.api.routes.bugs import router as bugs_router
from src.api.routes.notifications import router as notifications_router
from src.api.routes.audit import router as audit_router

settings = get_settings()

openapi_tags = [
    {
        "name": "Auth",
        "description": "User authentication, registration and identity endpoints backed by Supabase Auth.",
    },
    {
        "name": "Projects",
        "description": "CRUD endpoints for managing projects.",
    },
    {
        "name": "Bugs",
        "description": "CRUD endpoints for tracking bugs and assignments.",
    },
    {
        "name": "Notifications",
        "description": "Endpoints for listing and updating user notifications.",
    },
    {
        "name": "Audit Logs",
        "description": "Admin endpoints for listing audit trails of actions performed in the system.",
    },
]

app = FastAPI(
    title="BugFlow API",
    description="Backend API for the BugFlow bug tracking application. Provides authentication, project/bug management, notifications and audit logging. Uses Supabase (Postgres + Auth) as persistence.",
    version="0.1.0",
    openapi_tags=openapi_tags,  # tags for grouping routes in Swagger UI
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PUBLIC_INTERFACE
@app.get("/", tags=["Auth"], summary="Health Check", operation_id="health_check")
def health_check():
    """
    Simple health check endpoint to verify the API is running.

    Returns:
        dict: JSON object containing a simple message indicating the service is healthy.
    """
    return {"message": "Healthy"}

# Include routers
app.include_router(auth_router, prefix="/auth")
app.include_router(projects_router, prefix="/projects")
app.include_router(bugs_router, prefix="/bugs")
app.include_router(notifications_router, prefix="/notifications")
app.include_router(audit_router, prefix="/audit")

# PUBLIC_INTERFACE
@app.get(
    "/websocket-usage",
    tags=["Auth"],
    summary="WebSocket Usage Notes",
    operation_id="websocket_usage_notes",
)
def websocket_usage_notes():
    """
    Provides notes related to real-time features.

    Returns:
        dict: Contains a note clarifying that the current API does not expose WebSocket endpoints.
    """
    return {
        "message": "No WebSocket endpoints are exposed in this API. Real-time features can be implemented later using Supabase Realtime if needed."
    }
