from fastapi import APIRouter, Depends, HTTPException, status

from src.api.config import get_settings
from src.api.db.supabase_client import get_supabase
from src.api.deps import get_current_user
from src.api.models import AuthLoginRequest, AuthRegisterRequest, AuthResponse, UserProfile

router = APIRouter(prefix="", tags=["Auth"])


# PUBLIC_INTERFACE
@router.post(
    "/register",
    response_model=UserProfile,
    summary="Register a new user",
    description="Registers a new user using Supabase Auth, and creates a corresponding profile with a role (default: user).",
    responses={
        201: {"description": "User registered"},
        400: {"description": "Invalid input or registration failed"},
    },
    status_code=201,
)
def register(payload: AuthRegisterRequest):
    """
    Register a new user with email/password using Supabase Auth.

    Args:
        payload: Registration payload containing email, password and optional role.

    Returns:
        UserProfile: Created user profile.

    Notes:
        - Uses APP_SITE_URL for email redirect upon verification.
        - Creates a row in the 'profiles' table with the specified role.
    """
    settings = get_settings()
    supabase = get_supabase()
    try:
        # sign up with Supabase
        resp = supabase.auth.sign_up(
            {
                "email": payload.email,
                "password": payload.password,
                "options": {"email_redirect_to": f"{settings.app_site_url}/auth/callback"},
            }
        )
        if resp.user is None:
            raise HTTPException(status_code=400, detail="Registration failed")

        user = resp.user
        # Create profile
        role_val = payload.role or "user"
        profile_data = {"id": user.id, "email": payload.email, "role": role_val}
        supabase.table("profiles").insert(profile_data).execute()

        return UserProfile(id=user.id, email=payload.email, role=role_val)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration failed: {e}")


# PUBLIC_INTERFACE
@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login a user",
    description="Authenticates a user using Supabase Auth and returns a bearer access token plus profile.",
    responses={
        200: {"description": "Authenticated"},
        401: {"description": "Invalid credentials"},
    },
)
def login(payload: AuthLoginRequest):
    """
    Authenticate a user using Supabase Auth and issue a JWT access token.

    Args:
        payload: Login request containing email and password.

    Returns:
        AuthResponse: Access token, token type and user profile.
    """
    supabase = get_supabase()
    try:
        session = supabase.auth.sign_in_with_password({"email": payload.email, "password": payload.password})
        if session is None or session.session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        access_token = session.session.access_token
        user = session.user
        # fetch profile
        prof = (
            supabase.table("profiles").select("*").eq("id", user.id).maybe_single().execute().data
            or {"id": user.id, "email": user.email, "role": "user"}
        )
        profile = UserProfile(id=prof["id"], email=prof["email"], role=prof.get("role", "user"), created_at=prof.get("created_at"))
        return AuthResponse(access_token=access_token, token_type="bearer", user=profile)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


# PUBLIC_INTERFACE
@router.get(
    "/me",
    response_model=UserProfile,
    summary="Get current user",
    description="Return the current authenticated user's profile.",
)
async def me(user: UserProfile = Depends(get_current_user)):
    """
    Get the currently authenticated user's profile.

    Returns:
        UserProfile: Current user's profile.
    """
    return user
