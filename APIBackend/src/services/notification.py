from typing import List
from fastapi import HTTPException, status
from src.database.client import supabase_client
from src.models.notification import NotificationResponse, NotificationType
from datetime import datetime


class NotificationService:
    """Notification service for managing notifications"""
    
    def __init__(self):
        self.supabase = supabase_client.client

    async def create_notification(self, user_id: str, title: str, message: str, notification_type: str) -> NotificationResponse:
        """Create a new notification"""
        try:
            notification_dict = {
                "user_id": user_id,
                "title": title,
                "message": message,
                "type": notification_type,
                "read": False,
                "created_at": datetime.utcnow().isoformat()
            }
            
            response = self.supabase.table("notifications").insert(notification_dict).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create notification"
                )
            
            notification = response.data[0]
            return NotificationResponse(
                id=notification["id"],
                user_id=notification["user_id"],
                title=notification["title"],
                message=notification["message"],
                type=NotificationType(notification["type"]),
                read=notification["read"],
                created_at=datetime.fromisoformat(notification["created_at"])
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create notification: {str(e)}"
            )

    async def get_user_notifications(self, user_id: str, unread_only: bool = False) -> List[NotificationResponse]:
        """Get notifications for a user"""
        try:
            query = self.supabase.table("notifications").select("*").eq("user_id", user_id)
            
            if unread_only:
                query = query.eq("read", False)
            
            query = query.order("created_at", desc=True)
            response = query.execute()
            
            notifications = []
            for notification_data in response.data:
                notifications.append(NotificationResponse(
                    id=notification_data["id"],
                    user_id=notification_data["user_id"],
                    title=notification_data["title"],
                    message=notification_data["message"],
                    type=NotificationType(notification_data["type"]),
                    read=notification_data["read"],
                    created_at=datetime.fromisoformat(notification_data["created_at"])
                ))
            
            return notifications
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get notifications: {str(e)}"
            )

    async def mark_notification_as_read(self, notification_id: str, user_id: str) -> NotificationResponse:
        """Mark a notification as read"""
        try:
            response = self.supabase.table("notifications").update({"read": True}).eq("id", notification_id).eq("user_id", user_id).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Notification not found"
                )
            
            notification = response.data[0]
            return NotificationResponse(
                id=notification["id"],
                user_id=notification["user_id"],
                title=notification["title"],
                message=notification["message"],
                type=NotificationType(notification["type"]),
                read=notification["read"],
                created_at=datetime.fromisoformat(notification["created_at"])
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to mark notification as read: {str(e)}"
            )

    async def mark_all_notifications_as_read(self, user_id: str) -> bool:
        """Mark all notifications as read for a user"""
        try:
            self.supabase.table("notifications").update({"read": True}).eq("user_id", user_id).eq("read", False).execute()
            
            return True
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to mark all notifications as read: {str(e)}"
            )


# Global notification service instance
notification_service = NotificationService()
