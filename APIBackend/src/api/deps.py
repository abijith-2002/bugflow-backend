from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.db.supabase_client import get_supabase
from src.api.models import Role, UserProfile

security = HTTPBearer(auto_error=False)


def _fetch_profile(user_id: str, email: str) -> UserProfile:
    """
    Ensure a profile exists for the user; create default 'user' role if missing.
    """
    supabase = get_supabase()

    resp = supabase.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
    data = resp.data
    if data is None:
        # Create a default profile with role 'user'
        create_data = {"id": user_id, "email": email, "role": "user"}
        ins = supabase.table("profiles").insert(create_data).execute()
        profile = ins.data[0]
    else:
        profile = data

    return UserProfile(id=profile["id"], email=profile["email"], role=profile.get("role", "user"), created_at=profile.get("created_at"))


# PUBLIC_INTERFACE
async def get_current_user(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserProfile:
    """
    Resolve the current user using the Authorization: Bearer <token> header and Supabase Auth.

    Args:
        request: Request object.
        credentials: HTTP bearer credentials provided by FastAPI security.

    Returns:
        UserProfile: The current authenticated user's profile.

    Raises:
        HTTPException: 401 if credentials are missing or invalid.
    """
    if credentials is None or not credentials.scheme.lower() == "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    jwt = credentials.credentials
    supabase = get_supabase()
    try:
        user_resp = supabase.auth.get_user(jwt)
        if user_resp is None or user_resp.user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Build profile object (ensure profile exists)
    user_id = user_resp.user.id
    email = user_resp.user.email or ""
    profile = _fetch_profile(user_id=user_id, email=email)
    return profile


# PUBLIC_INTERFACE
def require_role(required: Role):
    """
    Dependency factory that ensures the current user has the given role or higher.

    Role precedence: user < manager < admin
    """

    role_order = {"user": 1, "manager": 2, "admin": 3}

    async def _checker(user: UserProfile = Depends(get_current_user)) -> UserProfile:
        user_level = role_order.get(user.role, 1)
        required_level = role_order.get(required, 1)
        if user_level < required_level:
            raise HTTPException(status_code=403, detail=f"Requires role '{required}'")
        return user

    return _checker
