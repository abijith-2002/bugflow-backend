from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from ..core.database import get_database
from ..models.schemas import (
    NotificationResponse, NotificationCreate, NotificationUpdate,
    UserResponse, PaginatedResponse, SuccessResponse
)
from ..utils.security import get_current_active_user, get_admin_user
from ..utils.helpers import (
    generate_uuid, create_pagination_params, create_paginated_response,
    create_activity_log
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=PaginatedResponse, summary="List user notifications")
async def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    List notifications for the current user.
    
    Returns paginated list of notifications with optional filtering by read status.
    """
    try:
        # Build query
        query = db.table("notifications").select("*").eq("user_id", current_user.id)
        
        # Apply filters
        if is_read is not None:
            query = query.eq("is_read", is_read)
        
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
        notifications = result.data if result.data else []
        
        return create_paginated_response(notifications, total, page, per_page)
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch notifications"
        )


@router.get("/unread/count", summary="Get unread notifications count")
async def get_unread_count(
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Get count of unread notifications for the current user.
    
    Returns the number of unread notifications.
    """
    try:
        result = db.table("notifications").select("id").eq("user_id", current_user.id).eq("is_read", False).execute()
        count = len(result.data) if result.data else 0
        
        return {"unread_count": count}
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch unread count"
        )


@router.put("/{notification_id}", response_model=NotificationResponse, summary="Update notification")
async def update_notification(
    notification_id: str,
    notification_data: NotificationUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Update notification (mark as read/unread).
    
    Allows users to mark their own notifications as read or unread.
    """
    try:
        # Check if notification exists and belongs to user
        existing_notification = db.table("notifications").select("*").eq("id", notification_id).eq("user_id", current_user.id).execute()
        if not existing_notification.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Update notification
        update_data = notification_data.dict(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid update data provided"
            )
        
        result = db.table("notifications").update(update_data).eq("id", notification_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update notification"
            )
        
        return NotificationResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notification update failed"
        )


@router.put("/mark-all-read", response_model=SuccessResponse, summary="Mark all notifications as read")
async def mark_all_read(
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Mark all notifications as read for the current user.
    
    Updates all unread notifications to read status.
    """
    try:
        # Mark all unread notifications as read
        db.table("notifications").update({"is_read": True}).eq("user_id", current_user.id).eq("is_read", False).execute()
        
        return SuccessResponse(message="All notifications marked as read")
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notifications as read"
        )


@router.delete("/{notification_id}", response_model=SuccessResponse, summary="Delete notification")
async def delete_notification(
    notification_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    db = Depends(get_database)
):
    """
    Delete a notification.
    
    Allows users to delete their own notifications.
    """
    try:
        # Check if notification exists and belongs to user
        existing_notification = db.table("notifications").select("id").eq("id", notification_id).eq("user_id", current_user.id).execute()
        if not existing_notification.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Delete notification
        db.table("notifications").delete().eq("id", notification_id).execute()
        
        return SuccessResponse(message="Notification deleted successfully")
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notification deletion failed"
        )


@router.post("/", response_model=NotificationResponse, summary="Create notification (Admin)")
async def create_notification(
    notification_data: NotificationCreate,
    admin_user: UserResponse = Depends(get_admin_user),
    db = Depends(get_database)
):
    """
    Create a new notification (Admin only).
    
    Allows admins to create notifications for specific users.
    """
    try:
        # Verify target user exists
        user_result = db.table("users").select("id").eq("id", notification_data.user_id).execute()
        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found"
            )
        
        # Create notification
        notification_id = generate_uuid()
        
        new_notification = {
            "id": notification_id,
            "user_id": notification_data.user_id,
            "type": notification_data.type.value,
            "title": notification_data.title,
            "message": notification_data.message,
            "related_id": notification_data.related_id,
            "is_read": notification_data.is_read
        }
        
        result = db.table("notifications").insert(new_notification).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create notification"
            )
        
        # Log activity
        activity = create_activity_log(
            user_id=admin_user.id,
            action="notification_created",
            resource_type="notification",
            resource_id=notification_id,
            details={"target_user": notification_data.user_id, "type": notification_data.type.value}
        )
        db.table("audit_logs").insert(activity).execute()
        
        return NotificationResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notification creation failed"
        )
