from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

Role = Literal["user", "manager", "admin"]
BugStatus = Literal["open", "in_progress", "resolved", "closed"]
BugPriority = Literal["low", "medium", "high", "critical"]


# ---------- Auth / Profile ----------
class UserProfile(BaseModel):
    """Represents a user's profile as stored in the 'profiles' table."""

    id: UUID = Field(..., description="User unique identifier (auth.users.id).")
    email: str = Field(..., description="User email address.")
    role: Role = Field(..., description="User role in the system (user, manager, admin).")
    created_at: Optional[datetime] = Field(None, description="Profile creation timestamp.")


class AuthRegisterRequest(BaseModel):
    """Request payload for user registration."""

    email: str = Field(..., description="Email address for registration.")
    password: str = Field(..., description="Password for registration.")
    role: Optional[Role] = Field(
        default="user", description="Optional role to assign on registration (default 'user')."
    )


class AuthLoginRequest(BaseModel):
    """Request payload for user login."""

    email: str = Field(..., description="User email.")
    password: str = Field(..., description="User password.")


class AuthResponse(BaseModel):
    """Authentication response with access token and user profile."""

    access_token: str = Field(..., description="JWT access token from Supabase.")
    token_type: str = Field(default="bearer", description="Type of token.")
    user: UserProfile = Field(..., description="User profile information.")


# ---------- Projects ----------
class ProjectBase(BaseModel):
    """Base fields shared by project models."""

    name: str = Field(..., description="Project name.")
    description: Optional[str] = Field(None, description="Project description.")


class ProjectCreate(ProjectBase):
    """Request payload to create a new project."""
    pass


class ProjectUpdate(BaseModel):
    """Request payload to update a project (all fields optional)."""

    name: Optional[str] = Field(None, description="Project name.")
    description: Optional[str] = Field(None, description="Project description.")


class ProjectOut(ProjectBase):
    """Response model representing a project."""

    id: UUID = Field(..., description="Project identifier.")
    owner_id: Optional[UUID] = Field(None, description="Owner user id.")
    created_at: Optional[datetime] = Field(None, description="Creation time.")
    updated_at: Optional[datetime] = Field(None, description="Last update time.")


# ---------- Bugs ----------
class BugBase(BaseModel):
    """Base fields shared by bug models."""

    project_id: UUID = Field(..., description="Project id to which the bug belongs.")
    title: str = Field(..., description="Short description of the bug.")
    description: Optional[str] = Field(None, description="Detailed description of the bug.")
    priority: BugPriority = Field(..., description="Priority of the bug.")


class BugCreate(BugBase):
    """Request payload to create a new bug."""

    assignee_id: Optional[UUID] = Field(None, description="User id to assign the bug to (optional).")


class BugUpdate(BaseModel):
    """Request payload to update a bug (all fields optional)."""

    title: Optional[str] = Field(None, description="Short description of the bug.")
    description: Optional[str] = Field(None, description="Detailed description of the bug.")
    status: Optional[BugStatus] = Field(None, description="New status of the bug.")
    priority: Optional[BugPriority] = Field(None, description="Priority of the bug.")
    assignee_id: Optional[UUID] = Field(None, description="New assignee user id.")


class BugOut(BugBase):
    """Response model representing a bug."""

    id: UUID = Field(..., description="Bug id.")
    status: BugStatus = Field(..., description="Bug status.")
    reporter_id: UUID = Field(..., description="User id of the reporter.")
    assignee_id: Optional[UUID] = Field(None, description="Assignee user id.")
    created_at: Optional[datetime] = Field(None, description="Creation time.")
    updated_at: Optional[datetime] = Field(None, description="Last update time.")


# ---------- Notifications ----------
class NotificationOut(BaseModel):
    """Response model representing a user notification."""

    id: UUID = Field(..., description="Notification id.")
    user_id: UUID = Field(..., description="User receiving the notification.")
    message: str = Field(..., description="Notification message.")
    read: bool = Field(..., description="Read state of the notification.")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp.")


# ---------- Audit ----------
class AuditLogOut(BaseModel):
    """Response model representing an audit log record."""

    id: UUID = Field(..., description="Audit log id.")
    actor_id: Optional[UUID] = Field(None, description="Actor user id (if available).")
    action: str = Field(..., description="Action performed.")
    entity_type: str = Field(..., description="Entity type, e.g., 'project', 'bug'.")
    entity_id: Optional[UUID] = Field(None, description="Entity id the action relates to.")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Additional metadata.")
    created_at: Optional[datetime] = Field(None, description="Creation time.")
