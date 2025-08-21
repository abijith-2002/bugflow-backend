from fastapi import APIRouter, Depends
from src.models.user import UserCreate, UserLogin, UserResponse, AuthResponse
from src.services.auth import auth_service
from src.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


# PUBLIC_INTERFACE
@router.post("/register", response_model=AuthResponse, summary="Register a new user")
async def register(user_data: UserCreate):
    """
    Register a new user in the system.
    
    - **email**: User's email address
    - **password**: User's password (minimum 8 characters)
    - **role**: User's role (user, admin, project_manager)
    
    Returns the user information and JWT access token.
    """
    return await auth_service.register(user_data)


# PUBLIC_INTERFACE
@router.post("/login", response_model=AuthResponse, summary="Authenticate user")
async def login(credentials: UserLogin):
    """
    Authenticate user and return JWT token.
    
    - **email**: User's email address
    - **password**: User's password
    
    Returns the user information and JWT access token.
    """
    return await auth_service.login(credentials)


# PUBLIC_INTERFACE
@router.get("/me", response_model=UserResponse, summary="Get current user info")
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    """
    Get information about the currently authenticated user.
    
    Requires valid JWT token in Authorization header.
    """
    return current_user


# PUBLIC_INTERFACE
@router.post("/logout", summary="Logout user")
async def logout():
    """
    Logout the current user.
    
    Note: Since we're using stateless JWT tokens, logout is handled client-side
    by removing the token from storage.
    """
    return {"message": "Successfully logged out"}
