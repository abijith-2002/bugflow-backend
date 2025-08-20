from typing import Optional
from uuid import UUID

from src.api.db.supabase_client import get_supabase


# PUBLIC_INTERFACE
def create_notification(user_id: UUID, message: str) -> Optional[dict]:
    """
    Create a notification for the user.

    Args:
        user_id: User UUID to notify.
        message: Message content.

    Returns:
        Inserted row dict or None if insert failed.
    """
    supabase = get_supabase()
    result = supabase.table("notifications").insert({"user_id": str(user_id), "message": message, "read": False}).execute()
    if result.data:
        return result.data[0]
    return None


# PUBLIC_INTERFACE
def mark_notification_read(notification_id: UUID) -> Optional[dict]:
    """Mark a notification as read and return the updated row."""
    supabase = get_supabase()
    result = supabase.table("notifications").update({"read": True}).eq("id", str(notification_id)).execute()
    if result.data:
        return result.data[0]
    return None
