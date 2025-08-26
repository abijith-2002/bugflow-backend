from typing import Optional, Dict, Any

import os
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field
from supabase import create_client, Client

logger = logging.getLogger("bugflow.api.auth")

# PUBLIC_INTERFACE
def get_supabase_client() -> Client:
    """Create and return a Supabase client using environment variables.

    Requires:
    - SUPABASE_URL: Supabase project URL
    - SUPABASE_ANON_KEY: Supabase anonymous (public) API key

    Returns:
        supabase.Client: An authenticated Supabase client instance.

    Raises:
        HTTPException: If required environment variables are missing.
    """
    # Log a snapshot just before dependency creation
    logger.info(
        "get_supabase_client: SUPABASE_URL_present=%s SUPABASE_ANON_KEY_present=%s",
        bool(os.getenv("SUPABASE_URL")), bool(os.getenv("SUPABASE_ANON_KEY"))
    )

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_anon_key:
        # Provide a helpful error with guidance on where to configure env.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Supabase configuration missing. Please set SUPABASE_URL and SUPABASE_ANON_KEY. "
                "The API loads environment variables from the process environment and, if present, "
                "from a .env file located at APIBackend/.env. Ensure these variables are set before "
                "calling /signup or /login."
            ),
        )
    return create_client(supabase_url, supabase_anon_key)


class SignupRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password (min 6 characters)")
    full_name: Optional[str] = Field(None, description="User full name")

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")

class AuthResponse(BaseModel):
    user_id: Optional[str] = Field(None, description="Unique user identifier from Supabase")
    access_token: Optional[str] = Field(None, description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token for renewing the session")
    message: str = Field(..., description="Status message")


router = APIRouter(prefix="", tags=["Authentication"])


# PUBLIC_INTERFACE
@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User signup",
    description="Registers a new user using Supabase Auth. Optionally stores user profile data.",
    responses={
        201: {"description": "User successfully created"},
        400: {"description": "Invalid input"},
        409: {"description": "User already exists"},
        500: {"description": "Server error / configuration error"},
    },
)
def signup(payload: SignupRequest, supabase: Client = Depends(get_supabase_client)) -> AuthResponse:
    """Create a new user account with Supabase.

    Parameters:
        payload (SignupRequest): Email, password, and optional full name.
        supabase (Client): Supabase client dependency.

    Returns:
        AuthResponse: Contains user_id, access_token, refresh_token, and a message.

    Notes:
        - The email confirmation behavior depends on your Supabase project's auth settings.
        - If email confirmation is enabled, access token may be None until confirmed.
    """
    try:
        logger.info(
            "Handling /signup: SITE_URL_present=%s",
            bool(os.getenv("SITE_URL"))
        )
        # Prepare options: set email redirect URL if SITE_URL is present
        site_url = os.getenv("SITE_URL")
        signup_options: Dict[str, Any] = {}
        if site_url:
            signup_options["email_redirect_to"] = f"{site_url}/auth/callback"

        # Sign up user
        result = supabase.auth.sign_up(
            {"email": payload.email, "password": payload.password, "options": signup_options or None}
        )

        # result contains user and potentially session (if auto-confirm disabled)
        user = result.user
        session = result.session

        # Optionally upsert profile in a "profiles" table if exists
        # This is best-effort and will be ignored if table does not exist
        if payload.full_name:
            try:
                supabase.table("profiles").upsert(
                    {"id": user.id, "email": payload.email, "full_name": payload.full_name}
                ).execute()
            except Exception:
                # Silently ignore if table not available
                logger.info("profiles upsert skipped or failed (table may not exist).")
                pass

        return AuthResponse(
            user_id=user.id if user else None,
            access_token=session.access_token if session else None,
            refresh_token=session.refresh_token if session else None,
            message="Signup successful. Check your email to confirm your account if required."
        )
    except Exception as e:
        msg = str(e)
        if "User already registered" in msg or "already registered" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Signup failed: {msg}")


# PUBLIC_INTERFACE
@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticates a user with email and password via Supabase and returns a session.",
    responses={
        200: {"description": "Authentication successful"},
        400: {"description": "Invalid credentials or request"},
        401: {"description": "Unauthorized"},
        500: {"description": "Server error / configuration error"},
    },
)
def login(payload: LoginRequest, supabase: Client = Depends(get_supabase_client)) -> AuthResponse:
    """Authenticate an existing user with Supabase.

    Parameters:
        payload (LoginRequest): Email and password.
        supabase (Client): Supabase client dependency.

    Returns:
        AuthResponse: Contains user_id, access_token, refresh_token, and a message.
    """
    try:
        logger.info("Handling /login request.")
        result = supabase.auth.sign_in_with_password({"email": payload.email, "password": payload.password})
        session = result.session
        user = result.user

        if not session or not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        return AuthResponse(
            user_id=user.id,
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            message="Login successful"
        )
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        if "Invalid login credentials" in msg or "invalid" in msg.lower():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Login failed: {msg}")
