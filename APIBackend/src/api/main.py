import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from starlette import status

try:
    # supabase-py v2 client
    from supabase import create_client, Client  # type: ignore
except Exception:  # pragma: no cover - handled at runtime if dependency missing
    create_client = None  # type: ignore
    Client = None  # type: ignore

# App metadata for OpenAPI
app = FastAPI(
    title="BugFlow API",
    version="0.1.0",
    description=(
        "FastAPI backend for BugFlow. Provides authentication endpoints (signup/login) "
        "integrated with Supabase and is ready for React frontend consumption."
    ),
    contact={"name": "BugFlow", "url": "https://example.com"},
)

# CORS configuration - frontend origin should be set via env; default to allow all for dev
# Required envs:
# - SUPABASE_URL
# - SUPABASE_ANON_KEY
# - FRONTEND_ORIGIN (http://localhost:3000)
# - SITE_URL (http://localhost:3000/)
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables required for Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SITE_URL = os.getenv("SITE_URL")  # Used for email redirect links

_supabase_client: Optional["Client"] = None


def _get_supabase() -> "Client":
    """
    Internal helper to lazily initialize and return the Supabase client.
    Raises a 500 error if env vars are missing or dependency is not installed.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if create_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase client library is not installed. Please add 'supabase' to requirements.",
        )
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase configuration missing. Ensure SUPABASE_URL and SUPABASE_ANON_KEY are set.",
        )
    _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _supabase_client


# Pydantic models for requests and responses

class HealthResponse(BaseModel):
    message: str = Field(..., description="Health status message")


class AuthBase(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="User password (min 6 characters)")


class SignupRequest(AuthBase):
    #: Optional redirect URL for email confirmation
    redirect_to: Optional[str] = Field(
        default=None,
        description="Override redirect URL for email confirmation. Defaults to SITE_URL if set.",
    )


class LoginRequest(AuthBase):
    pass


class AuthResponse(BaseModel):
    user_id: Optional[str] = Field(None, description="Supabase user ID")
    access_token: Optional[str] = Field(None, description="Access token for authenticated requests")
    token_type: Optional[str] = Field(None, description="Type of token, typically 'bearer'")
    message: Optional[str] = Field(None, description="Additional message")
    requires_verification: Optional[bool] = Field(
        default=None, description="True if email verification is required to complete signup"
    )


openapi_tags = [
    {"name": "Health", "description": "Service health and diagnostics"},
    {"name": "Auth", "description": "User authentication endpoints using Supabase"},
]


@app.get("/", response_model=HealthResponse, tags=["Health"], summary="Health Check", description="Basic service health check endpoint.")
# PUBLIC_INTERFACE
def health_check():
    """Return service health information."""
    return HealthResponse(message="Healthy")


@app.post(
    "/auth/signup",
    response_model=AuthResponse,
    tags=["Auth"],
    summary="User Signup",
    description="Creates a new user using Supabase auth with email and password. If email confirmations are enabled in Supabase, the user may need to verify their email.",
    responses={
        201: {"description": "User created"},
        400: {"description": "Invalid input or user already exists"},
        500: {"description": "Server configuration error"},
    },
    status_code=status.HTTP_201_CREATED,
)
# PUBLIC_INTERFACE
def signup(payload: SignupRequest) -> AuthResponse:
    """Signup a new user with email and password via Supabase."""
    sb = _get_supabase()
    redirect_to = payload.redirect_to or SITE_URL
    try:
        # Supabase python client expects dict
        data = {"email": payload.email, "password": payload.password}
        # Include optional emailRedirectTo if configured
        options = {}
        if redirect_to:
            options["email_redirect_to"] = redirect_to

        res = sb.auth.sign_up(data if not options else {**data, **options})
        # res contains user and/or session; session is often None if email confirmation required
        user_id = getattr(getattr(res, "user", None), "id", None) if hasattr(res, "user") else None
        session = getattr(res, "session", None) if hasattr(res, "session") else None
        access_token = getattr(session, "access_token", None) if session else None
        requires_verification = access_token is None  # heuristic

        return AuthResponse(
            user_id=user_id,
            access_token=access_token,
            token_type="bearer" if access_token else None,
            message="Signup successful. Please check your email to verify your account." if requires_verification else "Signup successful.",
            requires_verification=requires_verification,
        )
    except Exception as e:
        # Common cases: user already registered, invalid email, weak password
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.post(
    "/auth/login",
    response_model=AuthResponse,
    tags=["Auth"],
    summary="User Login",
    description="Logs in an existing user using Supabase auth with email and password. Returns an access token on success.",
    responses={
        200: {"description": "Login successful"},
        400: {"description": "Invalid credentials"},
        500: {"description": "Server configuration error"},
    },
)
# PUBLIC_INTERFACE
def login(payload: LoginRequest) -> AuthResponse:
    """Login an existing user via Supabase and return access token."""
    sb = _get_supabase()
    try:
        res = sb.auth.sign_in_with_password({"email": payload.email, "password": payload.password})
        session = getattr(res, "session", None)
        if not session or not getattr(session, "access_token", None):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials")
        user_id = getattr(getattr(res, "user", None), "id", None) if hasattr(res, "user") else None
        access_token = session.access_token
        return AuthResponse(
            user_id=user_id,
            access_token=access_token,
            token_type="bearer",
            message="Login successful",
            requires_verification=False,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
