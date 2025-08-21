from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from ..core.database import get_database
from ..models.schemas import (
    UserResponse, UserCreate, UserUpdate, UserProfile, UserRole,
    PaginatedResponse, SuccessResponse
)
from ..utils.security import get_current_active_user, get_admin_user
from ..utils.helpers import (
    generate_uuid, create_pagination_params, create_paginated_response,
    create_activity_log
)
from ..utils.auth import get_password_hash

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=PaginatedResponse, summary="List users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    List all users with pagination and filtering.
    
    Returns a paginated list of users with optional filtering by search term, role, and status.
    """
    try:
        # Build query
        query = db.table("users").select("id, email, full_name, role, is_active, created_at, last_login")
        
        # Apply filters
        if search:
            query = query.or_(f"full_name.ilike.%{search}%,email.ilike.%{search}%")
        
        if role:
            query = query.eq("role", role.value)
            
        if is_active is not None:
            query = query.eq("is_active", is_active)
        
        # Get total count
        count_result = query.execute()
        total = len(count_result.data) if count_result.data else 0
        
        # Apply pagination
        pagination = create_pagination_params(page, per_page)
        paginated_query = query.range(
            pagination["offset"], 
            pagination["offset"] + pagination["limit"] - 1
        ).order("created_at", desc=True)
        
        result = paginated_query.execute()
        users = result.data if result.data else []
        
        return create_paginated_response(users, total, page, per_page)
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch users"
        )


@router.get("/{user_id}", response_model=UserProfile, summary="Get user by ID")
async def get_user(
    user_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Get detailed user information by ID.
    
    Returns extended user profile with statistics and activity information.
    """
    try:
        # Get user details
        result = db.table("users").select("*").eq("id", user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user = result.data[0]
        
        # Get user statistics
        projects_count = 0
        bugs_assigned = 0
        bugs_reported = 0
        
        try:
            # Count projects owned
            projects_result = db.table("projects").select("id").eq("owner_id", user_id).execute()
            projects_count = len(projects_result.data) if projects_result.data else 0
            
            # Count bugs assigned
            assigned_result = db.table("bugs").select("id").eq("assigned_to", user_id).execute()
            bugs_assigned = len(assigned_result.data) if assigned_result.data else 0
            
            # Count bugs reported
            reported_result = db.table("bugs").select("id").eq("reported_by", user_id).execute()
            bugs_reported = len(reported_result.data) if reported_result.data else 0
            
        except Exception:
            pass  # Continue with default values if stats fail
        
        # Create user profile
        user_profile = UserProfile(
            **user,
            projects_count=projects_count,
            bugs_assigned=bugs_assigned,
            bugs_reported=bugs_reported
        )
        
        return user_profile
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user"
        )


@router.post("/", response_model=UserResponse, summary="Create new user")
async def create_user(
    user_data: UserCreate,
    admin_user: UserResponse = Depends(get_admin_user),
    db = Depends(get_database)
):
    """
    Create a new user (Admin only).
    
    Creates a new user account with the provided information.
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
            "is_active": user_data.is_active
        }
        
        result = db.table("users").insert(new_user).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        
        # Log activity
        activity = create_activity_log(
            user_id=admin_user.id,
            action="user_created",
            resource_type="user",
            resource_id=user_id,
            details={"created_user_email": user_data.email}
        )
        db.table("audit_logs").insert(activity).execute()
        
        return UserResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User creation failed"
        )


@router.put("/{user_id}", response_model=UserResponse, summary="Update user")
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Update user information.
    
    Users can update their own profile, admins can update any user.
    """
    try:
        # Check if user exists
        existing_user = db.table("users").select("*").eq("id", user_id).execute()
        if not existing_user.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check permissions (user can update own profile, admin can update any)
        if current_user.id != user_id and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this user"
            )
        
        # Prepare update data
        update_data = {}
        for field, value in user_data.dict(exclude_unset=True).items():
            if value is not None:
                if field == "role" and isinstance(value, UserRole):
                    update_data[field] = value.value
                else:
                    update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid update data provided"
            )
        
        # Check email uniqueness if email is being updated
        if "email" in update_data:
            email_check = db.table("users").select("id").eq("email", update_data["email"]).neq("id", user_id).execute()
            if email_check.data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
        
        # Update user
        result = db.table("users").update(update_data).eq("id", user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user"
            )
        
        # Log activity
        activity = create_activity_log(
            user_id=current_user.id,
            action="user_updated",
            resource_type="user",
            resource_id=user_id,
            details={"updated_fields": list(update_data.keys())}
        )
        db.table("audit_logs").insert(activity).execute()
        
        return UserResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User update failed"
        )


@router.delete("/{user_id}", response_model=SuccessResponse, summary="Delete user")
async def delete_user(
    user_id: str,
    admin_user: UserResponse = Depends(get_admin_user),
    db = Depends(get_database)
):
    """
    Delete user (Admin only).
    
    Soft deletes a user by setting is_active to false.
    """
    try:
        # Check if user exists
        existing_user = db.table("users").select("id, email").eq("id", user_id).execute()
        if not existing_user.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user = existing_user.data[0]
        
        # Prevent admin from deleting themselves
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        # Soft delete user
        result = db.table("users").update({"is_active": False}).eq("id", user_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user"
            )
        
        # Log activity
        activity = create_activity_log(
            user_id=admin_user.id,
            action="user_deleted",
            resource_type="user",
            resource_id=user_id,
            details={"deleted_user_email": user["email"]}
        )
        db.table("audit_logs").insert(activity).execute()
        
        return SuccessResponse(message="User deleted successfully")
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User deletion failed"
        )
