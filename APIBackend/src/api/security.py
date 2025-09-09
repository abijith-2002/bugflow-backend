"""
Security utilities and dependencies for JWT-based authentication.

This module provides:
- Lazy environment checks so the app doesn't crash at import/startup if JWT envs are missing.
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

# Note: Do not import settings at module import in a way that forces env validation.
# from .config import get_settings  # Avoid mandatory loading here


# PUBLIC_INTERFACE
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=True))) -> dict:
    """Validate a Bearer JWT and return its claims.

    Uses JWT_SECRET_KEY and JWT_ALGORITHM from environment variables to verify the token
    signature via PyJWT. Raises 401 on any validation failure, including missing envs.

    Returns:
        dict: Decoded claims payload.
    """
    import os

    secret = (os.getenv("JWT_SECRET_KEY") or "").strip()
    algorithm = (os.getenv("JWT_ALGORITHM") or "").strip()
    if not secret or not algorithm:
        # Defer error to request-time so public endpoints can load without env present.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is not configured",
        )

    token = credentials.credentials or ""
    try:
        claims = jwt.decode(token, secret, algorithms=[algorithm])
        if not isinstance(claims, dict):
            raise jwt.InvalidTokenError("Invalid token payload")
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}")


class _JWTSettings(BaseModel):
    """Internal helper model for JWT config."""
    secret_key: str = Field(..., description="JWT secret key used to verify tokens")
    algorithm: str = Field(..., description="JWT signing/verification algorithm (e.g., HS256)")


def _load_jwt_settings() -> Optional[_JWTSettings]:
    """
    Load JWT settings from environment in a lazy, non-throwing manner.

    Returns:
        _JWTSettings if both env vars are present; otherwise None.
    """
    import os

    # Correctly read JWT_SECRET_KEY; previously used 'JWT_SECRET' which was inconsistent.
    secret = (os.getenv("JWT_SECRET_KEY") or "").strip()
    alg = (os.getenv("JWT_ALGORITHM") or "").strip()

    if not secret or not alg:
        # Do not raise here; defer to request-time.
        return None

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# PUBLIC_INTERFACE
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> CurrentUser:
    """Resolve and return the authenticated user from a Bearer JWT.

    This dependency:
    - Extracts the Bearer token from the Authorization header.
    - Lazily loads JWT_SECRET_KEY and JWT_ALGORITHM from environment.
    - Decodes and validates the token using PyJWT.
    - Returns a CurrentUser built from claims (sub and email when present).

    Raises:
    - 401 Unauthorized on missing/invalid/expired tokens or missing env configuration.

    Usage:
    - Add `current_user: CurrentUser = Depends(get_current_user)` to protected endpoints.
    """
    settings = _load_jwt_settings()
    if settings is None:
        # Missing secret/algorithm: treat as unauthorized for protected endpoints.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is not configured")

    token = credentials.credentials or ""
    claims = _decode_token(token, settings)

    sub = str(claims.get("sub") or "")
    if not sub:
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
