from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import auth, projects, bugs, notifications, comments

# Initialize FastAPI app with metadata
app = FastAPI(
    title="Bug Tracking API",
    description="A comprehensive bug tracking system with project management, notifications, and audit logging",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User authentication and authorization endpoints"
        },
        {
            "name": "Projects", 
            "description": "Project management operations"
        },
        {
            "name": "Bugs",
            "description": "Bug tracking and management operations"
        },
        {
            "name": "Comments",
            "description": "Bug comment management operations"
        },
        {
            "name": "Notifications",
            "description": "User notification management operations"
        }
    ]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(bugs.router)
app.include_router(comments.router)
app.include_router(notifications.router)


# PUBLIC_INTERFACE
@app.get("/", tags=["Health"])
def health_check():
    """
    Health check endpoint to verify API is running.
    
    Returns a simple health status message.
    """
    return {"message": "Bug Tracking API is healthy", "status": "ok"}


# PUBLIC_INTERFACE
@app.get("/health", tags=["Health"])
def detailed_health_check():
    """
    Detailed health check endpoint with more information.
    
    Returns detailed status information about the API.
    """
    return {
        "message": "Bug Tracking API is healthy",
        "status": "ok",
        "version": "1.0.0",
        "description": "Bug tracking system with FastAPI and Supabase"
    }
