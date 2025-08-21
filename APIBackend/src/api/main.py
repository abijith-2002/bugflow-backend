from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from ..core.config import settings
from ..core.database import db
from ..routers import (
    auth_router,
    users_router,
    projects_router,
    bugs_router,
    notifications_router,
    dashboard_router,
    audit_logs_router
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAPI tags for documentation
openapi_tags = [
    {
        "name": "Authentication",
        "description": "User authentication and authorization operations including login, register, password management, and token handling."
    },
    {
        "name": "Users",
        "description": "User management operations including profile management, user creation, updates, and role management."
    },
    {
        "name": "Projects", 
        "description": "Project management operations including project creation, member management, and project statistics."
    },
    {
        "name": "Bugs",
        "description": "Bug tracking operations including bug creation, updates, comments, and status management."
    },
    {
        "name": "Notifications",
        "description": "Notification management for user alerts, updates, and system messages."
    },
    {
        "name": "Dashboard",
        "description": "Dashboard and analytics operations providing statistics and activity feeds."
    },
    {
        "name": "Audit Logs",
        "description": "Audit trail and logging operations for tracking user actions and system changes."
    }
]

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="A comprehensive bug tracking API built with FastAPI and Supabase. "
                "Provides endpoints for user management, project management, bug tracking, "
                "notifications, and audit logging with role-based access control.",
    version=settings.app_version,
    openapi_tags=openapi_tags,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Global HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Global exception handler for unexpected errors."""
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error"}
    )

# Health check endpoint
@app.get("/", tags=["Health"], summary="Health Check")
def health_check():
    """
    Health check endpoint to verify API availability.
    
    Returns the API status and basic information.
    """
    return {
        "message": "BugFlow API is healthy", 
        "version": settings.app_version,
        "status": "operational"
    }

# Database connection test endpoint
@app.get("/health/database", tags=["Health"], summary="Database Health Check")
def database_health_check():
    """
    Database health check endpoint.
    
    Tests the connection to Supabase database.
    """
    try:
        is_connected = db.test_connection()
        if is_connected:
            return {"message": "Database connection healthy", "status": "connected"}
        else:
            return JSONResponse(
                status_code=503,
                content={"message": "Database connection failed", "status": "disconnected"}
            )
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"message": "Database health check failed", "status": "error"}
        )

# Include all routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(bugs_router)
app.include_router(notifications_router)
app.include_router(dashboard_router)
app.include_router(audit_logs_router)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Test database connection
    try:
        is_connected = db.test_connection()
        if is_connected:
            logger.info("Database connection established")
        else:
            logger.warning("Database connection test failed")
    except Exception as e:
        logger.error(f"Database connection error: {e}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info(f"Shutting down {settings.app_name}")
