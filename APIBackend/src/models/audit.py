from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class AuditLogBase(BaseModel):
    """Base audit log model with common fields"""
    action: str = Field(..., description="Action performed")
    entity_type: str = Field(..., description="Type of entity affected")
    entity_id: str = Field(..., description="ID of entity affected")
    old_values: Optional[Dict[str, Any]] = Field(None, description="Previous values")
    new_values: Optional[Dict[str, Any]] = Field(None, description="New values")


class AuditLogCreate(AuditLogBase):
    """Model for creating a new audit log"""
    user_id: str = Field(..., description="User ID who performed the action")


class AuditLogResponse(AuditLogBase):
    """Model for audit log response data"""
    id: str = Field(..., description="Audit log's unique identifier")
    user_id: str = Field(..., description="User ID who performed the action")
    created_at: datetime = Field(..., description="Audit log creation timestamp")

    class Config:
        from_attributes = True
