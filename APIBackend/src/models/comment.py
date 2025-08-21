from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CommentBase(BaseModel):
    """Base comment model with common fields"""
    content: str = Field(..., min_length=1, description="Comment content")


class CommentCreate(CommentBase):
    """Model for creating a new comment"""
    bug_id: str = Field(..., description="Bug ID this comment belongs to")


class CommentUpdate(BaseModel):
    """Model for updating comment information"""
    content: Optional[str] = Field(None, min_length=1, description="Comment content")


class CommentResponse(CommentBase):
    """Model for comment response data"""
    id: str = Field(..., description="Comment's unique identifier")
    bug_id: str = Field(..., description="Bug ID this comment belongs to")
    user_id: str = Field(..., description="User ID who created this comment")
    created_at: datetime = Field(..., description="Comment creation timestamp")

    class Config:
        from_attributes = True
