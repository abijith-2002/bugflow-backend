from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from .config import get_settings
from .supabase_client import SupabaseAuthClient

router = APIRouter(prefix="/auth", tags=["Authentication"])


class SignUpRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address of the new user")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")

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


def get_auth_client(settings=Depends(get_settings)) -> SupabaseAuthClient:
    """
    Build a SupabaseAuthClient using validated settings.
    Converts configuration errors into HTTPExceptions for clearer API responses.
    """
    try:
        return SupabaseAuthClient(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_ANON_KEY,
        )
    except ValueError as e:
        # Configuration problem; surface as 500 with actionable detail
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
async def signup(payload: SignUpRequest, auth_client: SupabaseAuthClient = Depends(get_auth_client)) -> SignUpResponse:
    """
    Register a new user using Supabase authentication.

    Parameters:
    - email: Email address of the new user
    - password: Password for the new user (min 8 characters)

    Returns:
    - message: Status message
    - user_id: Supabase user id if available
    - needs_verification: Indicates if email verification is required (true in most Supabase setups)
    """
    try:
        res = await auth_client.sign_up(email=str(payload.email), password=payload.password)
        # Supabase returns {user, session}. If email confirmation is required, session will be None and user exists.
        user_id = None
        needs_verification = True
        if res:
            user = res.get("user")
            if user:
                user_id = user.get("id")
            session = res.get("session")
            needs_verification = session is None
        return SignUpResponse(message="User registration initiated", user_id=user_id, needs_verification=needs_verification)
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        # Propagate Supabase status and message. Avoid implying email confirmation issues
        # unless Supabase explicitly returns that message.
        status_code = e.response.status_code if e.response is not None else 400
        try:
            detail_json = e.response.json() if e.response is not None else None
        except Exception:
            detail_json = None
        # Prefer structured error fields if available
        if isinstance(detail_json, dict):
            detail = detail_json.get("error_description") or detail_json.get("error") or detail_json.get("msg") or detail_json.get("message") or e.response.text
        else:
            detail = e.response.text if e.response is not None else str(e)
        raise HTTPException(status_code=status_code, detail=detail)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supabase network error: {str(e)}")
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected server error")


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
async def login(payload: LoginRequest, auth_client: SupabaseAuthClient = Depends(get_auth_client)) -> LoginResponse:
    """
    Authenticate a user using Supabase email/password authentication.

    Parameters:
    - email: User email
    - password: User password

    Returns:
    - access_token: Supabase JWT
    - token_type: bearer
    - expires_in: Token expiry in seconds, when included
    - refresh_token: Supabase refresh token
    - user_id: Supabase user id
    """
    try:
        # Sign in with Supabase using password grant.
        # Supabase will return 200 with a session when credentials are valid and project
        # configuration allows immediate session creation (e.g., email confirmation disabled).
        # If email confirmation is required and not completed, Supabase typically returns 400 with a
        # descriptive error. We must not invent an "email not confirmed" error solely based on
        # a missing session; rely on Supabase's status codes and body instead.
        res = await auth_client.sign_in(email=str(payload.email), password=payload.password)
        if not isinstance(res, dict):
            raise HTTPException(status_code=502, detail="Unexpected response from Supabase")

        session = res.get("session")
        user = res.get("user")

        # When Supabase returns 200, a valid session should be present.
        # If for any reason the session is missing despite a 200, enhance diagnostics.
        if not session:
            # Collect common error fields if present
            # Include: error_description, error, msg, message
            error_fields = {}
            for k in ("error_description", "error", "msg", "message"):
                if k in res and res.get(k):
                    error_fields[k] = res.get(k)

            if error_fields:
                # Propagate as Unauthorized with upstream details for clearer troubleshooting
                # Prefer a concise message while preserving structure in detail
                # Use the first available field as the primary detail string
                primary = (
                    error_fields.get("error_description")
                    or error_fields.get("error")
                    or error_fields.get("msg")
                    or error_fields.get("message")
                )
                raise HTTPException(
                    status_code=401,
                    detail=primary if isinstance(primary, str) else str(primary),
                )

            # If none of the typical fields exist, return a 502 with a hint about present keys
            # Exclude obviously sensitive values (we only list keys, not values)
            sensitive_keys = {"access_token", "refresh_token", "provider_token", "provider_refresh_token"}
            present_keys = [k for k in res.keys() if k not in sensitive_keys]
            hint = f"payload keys present: {', '.join(sorted(present_keys))}" if present_keys else "payload was empty"
            raise HTTPException(
                status_code=502,
                detail=f"Supabase did not return a session; {hint}",
            )

        access_token = session.get("access_token")
        refresh_token = session.get("refresh_token")
        expires_in = session.get("expires_in")
        user_id = user.get("id") if user else None

        if not access_token:
            raise HTTPException(status_code=502, detail="Supabase did not return an access token")

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            refresh_token=refresh_token,
            user_id=user_id,
        )
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response is not None else 400
        detail = e.response.text if e.response is not None else str(e)
        raise HTTPException(status_code=status_code, detail=detail)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Supabase network error: {str(e)}")
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected server error")
