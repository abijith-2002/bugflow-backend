from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import router as auth_router

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
