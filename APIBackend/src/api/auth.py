from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from supabase import Client as SupabaseClient
# Note: In supabase-py v2, credential helper classes are not needed; pass dicts to auth methods.

from .config import get_settings
from .supabase_client import SupabaseClientProvider

router = APIRouter(prefix="/auth", tags=["Authentication"])


class SignUpRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address of the new user")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    username: str = Field(
        ...,
        min_length=2,
        max_length=60,
        description="Display name to be stored in the Supabase user profile (user_metadata).",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        # Basic strength checks; frontends may add more stringent checks
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class SignUpResponse(BaseModel):
    message: str = Field(..., description="Status message")
    user_id: Optional[str] = Field(
        default=None, description="Supabase user ID (if available)"
    )
    needs_verification: bool = Field(
        default=True,
        description="True if email confirmation or verification is required",
    )


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="User password")


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token from Supabase")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: Optional[int] = Field(
        default=None, description="Token expiry in seconds, if provided by Supabase"
    )
    refresh_token: Optional[str] = Field(
        default=None, description="The refresh token from Supabase, if provided"
    )
    user_id: Optional[str] = Field(default=None, description="Supabase user id")


def get_supabase(settings=Depends(get_settings)) -> SupabaseClient:
    """
    Build a supabase-py Client using validated settings. Converts configuration
    errors into HTTPExceptions for clearer API responses.
    """
    try:
        provider = SupabaseClientProvider(
            supabase_url=settings.SUPABASE_URL, supabase_key=settings.SUPABASE_ANON_KEY
        )
        return provider.client()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")


# PUBLIC_INTERFACE
@router.post(
    "/signup",
    response_model=SignUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user with email and password using Supabase auth. Sends confirmation email based on project settings.",
    responses={
        201: {"description": "User registered"},
        400: {"description": "Validation or Supabase error"},
        500: {"description": "Unexpected server error"},
    },
)
async def signup(payload: SignUpRequest, supabase: SupabaseClient = Depends(get_supabase)) -> SignUpResponse:
    """
    Register a new user using Supabase Auth via supabase-py.
    """
    try:
        # supabase-py v2 accepts a dict with email, password, and options
        creds = {
            "email": str(payload.email),
            "password": payload.password,
            "options": {"data": {"display_name": payload.username}},
        }
        res = supabase.auth.sign_up(credentials=creds)
        # res contains user and session (session is None if email verification required)
        user_id = res.user.id if getattr(res, "user", None) else None
        needs_verification = res.session is None
        return SignUpResponse(
            message="User registration initiated",
            user_id=user_id,
            needs_verification=needs_verification,
        )
    except Exception as e:
        # supabase-py throws generic exceptions with message; map to 400 by default
        raise HTTPException(status_code=400, detail=str(e))


# PUBLIC_INTERFACE
@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with email and password",
    description="Authenticates a user via Supabase and returns a JWT access token (and refresh token if provided).",
    responses={
        200: {"description": "Authenticated"},
        400: {"description": "Invalid credentials or Supabase error"},
        401: {"description": "Unauthorized"},
        500: {"description": "Unexpected server error"},
    },
)
async def login(payload: LoginRequest, supabase: SupabaseClient = Depends(get_supabase)) -> LoginResponse:
    """
    Authenticate using supabase-py password grant and return token information.
    """
    try:
        # supabase-py v2 accepts a dict with email and password
        creds = {
            "email": str(payload.email),
            "password": payload.password,
        }
        res = supabase.auth.sign_in_with_password(credentials=creds)
        # res.session contains access_token, refresh_token, expires_in; res.user contains id
        if not res or not res.session:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        access_token = res.session.access_token
        refresh_token = res.session.refresh_token
        expires_in = res.session.expires_in
        user_id = res.user.id if getattr(res, "user", None) else None

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            refresh_token=refresh_token,
            user_id=user_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
