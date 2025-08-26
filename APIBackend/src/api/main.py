from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter
import os

from src.api.auth import router as auth_router

openapi_tags = [
    {"name": "Health", "description": "Service health and utility endpoints"},
    {"name": "Authentication", "description": "User authentication via Supabase (signup and login)"},
]

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
