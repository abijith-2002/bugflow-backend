from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class NotificationType(str, Enum):
    """Notification type enumeration"""
    BUG_ASSIGNED = "bug_assigned"
    BUG_UPDATED = "bug_updated"
    COMMENT_ADDED = "comment_added"


class NotificationBase(BaseModel):
    """Base notification model with common fields"""
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    type: NotificationType = Field(..., description="Notification type")


class NotificationCreate(NotificationBase):
    """Model for creating a new notification"""
    user_id: str = Field(..., description="User ID to receive this notification")


class NotificationUpdate(BaseModel):
    """Model for updating notification information"""
    read: Optional[bool] = Field(None, description="Whether the notification has been read")


class NotificationResponse(NotificationBase):
    """Model for notification response data"""
    id: str = Field(..., description="Notification's unique identifier")
    user_id: str = Field(..., description="User ID this notification belongs to")
    read: bool = Field(False, description="Whether the notification has been read")
    created_at: datetime = Field(..., description="Notification creation timestamp")

    class Config:
        from_attributes = True
