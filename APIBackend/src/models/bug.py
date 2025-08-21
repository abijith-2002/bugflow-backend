from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class BugPriority(str, Enum):
    """Bug priority enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BugStatus(str, Enum):
    """Bug status enumeration"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class BugBase(BaseModel):
    """Base bug model with common fields"""
    title: str = Field(..., min_length=1, max_length=255, description="Bug title")
    description: Optional[str] = Field(None, description="Bug description")
    priority: BugPriority = Field(BugPriority.MEDIUM, description="Bug priority level")
    status: BugStatus = Field(BugStatus.OPEN, description="Bug status")


class BugCreate(BugBase):
    """Model for creating a new bug"""
    project_id: str = Field(..., description="Project ID this bug belongs to")
    assigned_to: Optional[str] = Field(None, description="User ID assigned to this bug")


class BugUpdate(BaseModel):
    """Model for updating bug information"""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Bug title")
    description: Optional[str] = Field(None, description="Bug description")
    priority: Optional[BugPriority] = Field(None, description="Bug priority level")
    status: Optional[BugStatus] = Field(None, description="Bug status")
    assigned_to: Optional[str] = Field(None, description="User ID assigned to this bug")


class BugResponse(BugBase):
    """Model for bug response data"""
    id: str = Field(..., description="Bug's unique identifier")
    project_id: str = Field(..., description="Project ID this bug belongs to")
    assigned_to: Optional[str] = Field(None, description="User ID assigned to this bug")
    reported_by: str = Field(..., description="User ID who reported this bug")
    created_at: datetime = Field(..., description="Bug creation timestamp")
    updated_at: datetime = Field(..., description="Bug last update timestamp")

    class Config:
        from_attributes = True
