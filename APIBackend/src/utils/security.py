from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..core.database import get_database
from ..models.schemas import UserResponse, UserRole
from .auth import verify_token

# Security scheme
security = HTTPBearer()


# PUBLIC_INTERFACE
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db = Depends(get_database)
) -> UserResponse:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = verify_token(token, "access")
        
        if payload is None:
            raise credentials_exception
            
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
    except Exception:
        raise credentials_exception
    
    # Get user from database
    try:
        result = db.table("users").select("*").eq("id", user_id).execute()
        if not result.data:
            raise credentials_exception
            
        user_data = result.data[0]
        return UserResponse(**user_data)
        
    except Exception:
        raise credentials_exception


# PUBLIC_INTERFACE
async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
    return current_user


# PUBLIC_INTERFACE
def require_role(required_role: UserRole):
    """Dependency factory for role-based access control."""
    async def role_checker(current_user: UserResponse = Depends(get_current_active_user)):
        # Define role hierarchy
        role_hierarchy = {
            UserRole.VIEWER: 1,
            UserRole.TESTER: 2,
            UserRole.DEVELOPER: 3,
            UserRole.PROJECT_MANAGER: 4,
            UserRole.ADMIN: 5
        }
        
        user_level = role_hierarchy.get(current_user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    
    return role_checker


# PUBLIC_INTERFACE
async def get_admin_user(
    current_user: UserResponse = Depends(require_role(UserRole.ADMIN))
) -> UserResponse:
    """Get current admin user."""
    return current_user


# PUBLIC_INTERFACE
async def get_project_manager_user(
    current_user: UserResponse = Depends(require_role(UserRole.PROJECT_MANAGER))
) -> UserResponse:
    """Get current project manager or higher user."""
    return current_user
