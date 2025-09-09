"""
Security utilities and dependencies for JWT-based authentication.

This module provides:
- Settings integration for JWT_SECRET and JWT_ALGORITHM loaded from environment.
- A reusable FastAPI dependency `get_current_user` that validates the Bearer token
  using the `jwt` (PyJWT) library, and returns a simple `CurrentUser` model.
- A `require_auth` dependency to enforce authentication without returning the user information.

All protected endpoints should use one of these dependencies in their signature.
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

import jwt  # PyJWT

from .config import get_settings  # type: ignore


class _JWTSettings(BaseModel):
    """Internal helper model for JWT config."""
    secret_key: str = Field(..., description="JWT secret key used to verify tokens")
    algorithm: str = Field(..., description="JWT signing/verification algorithm (e.g., HS256)")


def _load_jwt_settings() -> _JWTSettings:
    """
    Load JWT settings from environment via shared settings loader.

    Required environment variables:
    - JWT_SECRET
    - JWT_ALGORITHM
    """
    # Reuse existing get_settings to ensure dotenv is loaded; read env directly for JWT vars
    # because the existing Settings class does not yet include JWT fields.
    import os

    secret = (os.getenv("JWT_SECRET") or "").strip()
    alg = (os.getenv("JWT_ALGORITHM") or "").strip()

    missing = []
    if not secret:
        missing.append("JWT_SECRET")
    if not alg:
        missing.append("JWT_ALGORITHM")
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Set them in APIBackend/.env (see .env.example)."
        )
    return _JWTSettings(secret_key=secret, algorithm=alg)


class CurrentUser(BaseModel):
    """Represents the authenticated principal resolved from the JWT."""
    user_id: str = Field(..., description="Subject (sub) from JWT or user identifier")
    email: Optional[str] = Field(default=None, description="Email claim from JWT when present")
    raw_claims: dict = Field(default_factory=dict, description="All decoded claims for debugging/audit")


# HTTP Bearer scheme
_bearer_scheme = HTTPBearer(auto_error=True)


def _decode_token(token: str, settings: _JWTSettings) -> dict:
    """
    Decode and validate a JWT using PyJWT.

    - Validates signature using secret and algorithm.
    - Validates exp/nbf/iat automatically if present.
    - Returns decoded claims dict.
    """
    try:
        # Note: options include verifying exp by default; PyJWT will raise ExpiredSignatureError if expired
        claims = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require": [], "verify_signature": True},
        )
        if not isinstance(claims, dict):
            raise jwt.InvalidTokenError("Invalid token payload")
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}")
    except Exception:
        # Generic failure
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# PUBLIC_INTERFACE
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> CurrentUser:
    """Resolve and return the authenticated user from a Bearer JWT.

    This dependency:
    - Extracts the Bearer token from the Authorization header.
    - Loads JWT_SECRET and JWT_ALGORITHM from environment.
    - Decodes and validates the token using PyJWT.
    - Returns a CurrentUser built from claims (sub and email when present).

    Raises:
    - 401 Unauthorized on missing/invalid/expired tokens.

    Usage:
    - Add `current_user: CurrentUser = Depends(get_current_user)` to protected endpoints.
    """
    # Ensure base settings load (dotenv handled in app startup). Not used directly here, but
    # calling get_settings ensures global env loading side-effects remain intact.
    try:
        _ = get_settings()
    except Exception:
        # Even if Supabase settings are missing, JWT may still need to work; ignore here.
        pass

    settings = _load_jwt_settings()
    token = credentials.credentials or ""
    claims = _decode_token(token, settings)

    sub = str(claims.get("sub") or "")
    if not sub:
        # Some JWTs use 'user_id' or 'uid'; fallback checks
        for alt in ("user_id", "uid", "id"):
            if claims.get(alt):
                sub = str(claims[alt])
                break
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: missing subject")

    email = claims.get("email")
    return CurrentUser(user_id=sub, email=email, raw_claims=claims)


# PUBLIC_INTERFACE
async def require_auth(_: CurrentUser = Depends(get_current_user)) -> None:
    """Dependency that simply enforces authentication without returning user details.

    Add `Depends(require_auth)` to endpoints that only need to ensure a valid token is present.
    """
    return None
