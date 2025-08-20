from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from src.api.db.supabase_client import get_supabase
from src.api.deps import get_current_user
from src.api.models import NotificationOut, UserProfile
from src.api.services.notifications import mark_notification_read

router = APIRouter(prefix="", tags=["Notifications"])


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[NotificationOut],
    summary="List notifications",
    description="List notifications for the current user.",
)
def list_notifications(user: UserProfile = Depends(get_current_user)):
    supabase = get_supabase()
    result = (
        supabase.table("notifications")
        .select("*")
        .eq("user_id", str(user.id))
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


# PUBLIC_INTERFACE
@router.post(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark notification as read",
    description="Mark a single notification as read and return the updated record.",
)
def read_notification(notification_id: UUID, user: UserProfile = Depends(get_current_user)):
    supabase = get_supabase()
    # Ensure the notification belongs to the current user
    check = (
        supabase.table("notifications")
        .select("*")
        .eq("id", str(notification_id))
        .eq("user_id", str(user.id))
        .maybe_single()
        .execute()
    )
    if not check.data:
        raise HTTPException(status_code=404, detail="Notification not found")

    updated = mark_notification_read(notification_id)
    if not updated:
        raise HTTPException(status_code=400, detail="Failed to update notification")

    return updated
