from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .config import get_settings
from .routes import auth

# Load environment variables
load_dotenv()

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Bug tracking application API",
    version=settings.app_version,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User authentication and authorization endpoints. Handles user signup, login, and token verification using Supabase as the authentication provider."
        },
        {
            "name": "Health",
            "description": "Application health check endpoints"
        }
    ]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

@app.get("/", tags=["Health"])
async def health_check():
    """
    # PUBLIC_INTERFACE
    Health check endpoint

    Returns the health status of the API service.
    This endpoint can be used for monitoring and load balancer health checks.

    Returns:
    - **message**: Health status message
    - **version**: API version
    - **status**: Service status
    """
    return {
        "message": "BugFlow API is running",
        "version": settings.app_version,
        "status": "healthy"
    }
