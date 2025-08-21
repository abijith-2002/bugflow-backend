from fastapi import APIRouter, Depends, HTTPException, status, Request
from ..core.database import get_database
from ..models.schemas import (
    UserCreate, UserResponse, LoginRequest, Token, TokenRefresh,
    PasswordReset, PasswordUpdate, SuccessResponse
)
from ..utils.auth import (
    verify_password, get_password_hash, create_token_pair, verify_token
)
from ..utils.security import get_current_active_user
from ..utils.helpers import generate_uuid, create_activity_log

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, summary="Register new user")
async def register_user(
    user_data: UserCreate,
    db = Depends(get_database)
):
    """
    Register a new user account.
    
    Creates a new user with the provided information and returns user details.
    """
    try:
        # Check if user already exists
        existing_user = db.table("users").select("id").eq("email", user_data.email).execute()
        if existing_user.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        user_id = generate_uuid()
        hashed_password = get_password_hash(user_data.password)
        
        new_user = {
            "id": user_id,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "role": user_data.role.value,
            "password_hash": hashed_password,
            "is_active": True
        }
        
        result = db.table("users").insert(new_user).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        # Log activity
        activity = create_activity_log(
            user_id=user_id,
            action="user_registered",
            resource_type="user",
            resource_id=user_id
        )
        db.table("audit_logs").insert(activity).execute()
        
        return UserResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=Token, summary="User login")
async def login(
    login_data: LoginRequest,
    request: Request,
    db = Depends(get_database)
):
    """
    Authenticate user and return access tokens.
    
    Validates user credentials and returns JWT tokens for API access.
    """
    try:
        # Get user by email
        result = db.table("users").select("*").eq("email", login_data.email).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        user = result.data[0]
        
        # Verify password
        if not verify_password(login_data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check if user is active
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled"
            )
        
        # Create tokens
        token_data = {"sub": user["id"], "email": user["email"], "role": user["role"]}
        tokens = create_token_pair(token_data)
        
        # Update last login
        db.table("users").update({"last_login": "now()"}).eq("id", user["id"]).execute()
        
        # Log activity
        client_ip = request.client.host if request.client else "unknown"
        activity = create_activity_log(
            user_id=user["id"],
            action="user_login",
            resource_type="user",
            resource_id=user["id"],
            details={"ip_address": client_ip}
        )
        db.table("audit_logs").insert(activity).execute()
        
        return Token(**tokens)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=Token, summary="Refresh access token")
async def refresh_token(
    token_data: TokenRefresh,
    db = Depends(get_database)
):
    """
    Refresh access token using refresh token.
    
    Validates refresh token and returns new access and refresh tokens.
    """
    try:
        # Verify refresh token
        payload = verify_token(token_data.refresh_token, "refresh")
        
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user_id = payload.get("sub")
        
        # Get current user data
        result = db.table("users").select("id, email, role, is_active").eq("id", user_id).execute()
        
        if not result.data or not result.data[0].get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        user = result.data[0]
        
        # Create new tokens
        token_payload = {"sub": user["id"], "email": user["email"], "role": user["role"]}
        tokens = create_token_pair(token_payload)
        
        return Token(**tokens)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout", response_model=SuccessResponse, summary="User logout")
async def logout(
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Logout current user.
    
    Logs user logout activity for audit purposes.
    """
    try:
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="user_logout",
            resource_type="user",
            resource_id=current_user.id
        )
        db.table("audit_logs").insert(activity).execute()
        
        return SuccessResponse(message="Logged out successfully")
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.post("/password-reset", response_model=SuccessResponse, summary="Request password reset")
async def request_password_reset(
    reset_data: PasswordReset,
    db = Depends(get_database)
):
    """
    Request password reset.
    
    Initiates password reset process for the specified email.
    Note: This is a placeholder implementation. In production,
    you would send an email with a reset link.
    """
    try:
        # Check if user exists
        db.table("users").select("id").eq("email", reset_data.email).execute()
        
        # Always return success to prevent email enumeration
        return SuccessResponse(
            message="If an account with this email exists, you will receive password reset instructions."
        )
        
    except Exception:
        return SuccessResponse(
            message="If an account with this email exists, you will receive password reset instructions."
        )


@router.put("/password", response_model=SuccessResponse, summary="Update password")
async def update_password(
    password_data: PasswordUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Update user password.
    
    Changes the current user's password after verifying the current password.
    """
    try:
        # Get current user with password
        result = db.table("users").select("password_hash").eq("id", current_user.id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user = result.data[0]
        
        # Verify current password
        if not verify_password(password_data.current_password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        new_password_hash = get_password_hash(password_data.new_password)
        db.table("users").update({"password_hash": new_password_hash}).eq("id", current_user.id).execute()
        
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="password_updated",
            resource_type="user",
            resource_id=current_user.id
        )
        db.table("audit_logs").insert(activity).execute()
        
        return SuccessResponse(message="Password updated successfully")
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password update failed"
        )


@router.get("/me", response_model=UserResponse, summary="Get current user")
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """
    Get current authenticated user information.
    
    Returns the profile information of the currently authenticated user.
    """
    return current_user
