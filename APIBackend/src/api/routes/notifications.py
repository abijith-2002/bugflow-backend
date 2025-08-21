from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from src.models.notification import NotificationResponse
from src.models.user import UserResponse
from src.services.notification import notification_service
from src.dependencies import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# PUBLIC_INTERFACE
@router.get("/", response_model=List[NotificationResponse], summary="Get user notifications")
async def get_notifications(
    unread_only: bool = Query(False, description="Get only unread notifications"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get notifications for the current user.
    
    - **unread_only**: If true, returns only unread notifications
    """
    return await notification_service.get_user_notifications(current_user.id, unread_only)


# PUBLIC_INTERFACE
@router.put("/{notification_id}/read", response_model=NotificationResponse, summary="Mark notification as read")
async def mark_notification_read(
    notification_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Mark a specific notification as read.
    
    - **notification_id**: The unique identifier of the notification
    """
    return await notification_service.mark_notification_as_read(notification_id, current_user.id)


# PUBLIC_INTERFACE
@router.put("/mark-all-read", summary="Mark all notifications as read")
async def mark_all_notifications_read(current_user: UserResponse = Depends(get_current_user)):
    """
    Mark all notifications as read for the current user.
    """
    success = await notification_service.mark_all_notifications_as_read(current_user.id)
    if success:
        return {"message": "All notifications marked as read"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notifications as read"
        )
