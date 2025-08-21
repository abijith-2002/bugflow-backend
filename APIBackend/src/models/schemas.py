from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, EmailStr


# Enums
class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    PROJECT_MANAGER = "project_manager"
    DEVELOPER = "developer"
    TESTER = "tester"
    VIEWER = "viewer"


class BugStatus(str, Enum):
    """Bug status enumeration."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


class BugPriority(str, Enum):
    """Bug priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProjectStatus(str, Enum):
    """Project status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class NotificationType(str, Enum):
    """Notification type enumeration."""
    BUG_ASSIGNED = "bug_assigned"
    BUG_UPDATED = "bug_updated"
    PROJECT_ASSIGNED = "project_assigned"
    COMMENT_ADDED = "comment_added"
    STATUS_CHANGED = "status_changed"


# Base Models
class BaseSchema(BaseModel):
    """Base schema with common fields."""
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# User Models
class UserBase(BaseModel):
    """User base schema."""
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.DEVELOPER
    is_active: bool = True


class UserCreate(UserBase):
    """User creation schema."""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """User update schema."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase, BaseSchema):
    """User response schema."""
    avatar_url: Optional[str] = None
    last_login: Optional[datetime] = None


class UserProfile(UserResponse):
    """Extended user profile with additional fields."""
    projects_count: Optional[int] = 0
    bugs_assigned: Optional[int] = 0
    bugs_reported: Optional[int] = 0


# Authentication Models
class Token(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefresh(BaseModel):
    """Token refresh request schema."""
    refresh_token: str


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str


class PasswordReset(BaseModel):
    """Password reset request schema."""
    email: EmailStr


class PasswordUpdate(BaseModel):
    """Password update schema."""
    current_password: str
    new_password: str = Field(..., min_length=8)


# Project Models
class ProjectBase(BaseModel):
    """Project base schema."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.ACTIVE


class ProjectCreate(ProjectBase):
    """Project creation schema."""
    owner_id: str


class ProjectUpdate(BaseModel):
    """Project update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None


class ProjectResponse(ProjectBase, BaseSchema):
    """Project response schema."""
    owner_id: str
    owner_name: Optional[str] = None
    members_count: Optional[int] = 0
    bugs_count: Optional[int] = 0
    open_bugs_count: Optional[int] = 0


class ProjectMember(BaseModel):
    """Project member schema."""
    user_id: str
    user_name: str
    user_email: str
    role: UserRole
    joined_at: datetime


class ProjectStats(BaseModel):
    """Project statistics schema."""
    total_bugs: int
    open_bugs: int
    in_progress_bugs: int
    resolved_bugs: int
    closed_bugs: int
    critical_bugs: int
    high_priority_bugs: int


# Bug Models
class BugBase(BaseModel):
    """Bug base schema."""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    status: BugStatus = BugStatus.OPEN
    priority: BugPriority = BugPriority.MEDIUM
    project_id: str


class BugCreate(BugBase):
    """Bug creation schema."""
    reported_by: str
    assigned_to: Optional[str] = None


class BugUpdate(BaseModel):
    """Bug update schema."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[BugStatus] = None
    priority: Optional[BugPriority] = None
    assigned_to: Optional[str] = None


class BugResponse(BugBase, BaseSchema):
    """Bug response schema."""
    reported_by: str
    reported_by_name: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    project_name: Optional[str] = None
    comments_count: Optional[int] = 0
    resolved_at: Optional[datetime] = None


class BugComment(BaseSchema):
    """Bug comment schema."""
    bug_id: str
    user_id: str
    user_name: Optional[str] = None
    content: str


class BugCommentCreate(BaseModel):
    """Bug comment creation schema."""
    content: str = Field(..., min_length=1)


# Notification Models
class NotificationBase(BaseModel):
    """Notification base schema."""
    user_id: str
    type: NotificationType
    title: str
    message: str
    is_read: bool = False


class NotificationCreate(NotificationBase):
    """Notification creation schema."""
    related_id: Optional[str] = None  # Bug ID, Project ID, etc.


class NotificationResponse(NotificationBase, BaseSchema):
    """Notification response schema."""
    related_id: Optional[str] = None


class NotificationUpdate(BaseModel):
    """Notification update schema."""
    is_read: bool


# Audit Log Models
class AuditLogBase(BaseModel):
    """Audit log base schema."""
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    details: Optional[dict] = None


class AuditLogCreate(AuditLogBase):
    """Audit log creation schema."""
    pass


class AuditLogResponse(AuditLogBase, BaseSchema):
    """Audit log response schema."""
    user_name: Optional[str] = None
    ip_address: Optional[str] = None


# Generic Response Models
class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    """Generic error response."""
    success: bool = False
    message: str
    details: Optional[dict] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""
    items: List[dict]
    total: int
    page: int
    per_page: int
    pages: int


# Dashboard Models
class DashboardStats(BaseModel):
    """Dashboard statistics schema."""
    total_projects: int
    total_bugs: int
    open_bugs: int
    resolved_bugs: int
    critical_bugs: int
    my_assigned_bugs: int
    recent_activity: List[dict]


class ActivityItem(BaseModel):
    """Activity item schema."""
    id: str
    type: str
    description: str
    user_name: str
    timestamp: datetime
    related_id: Optional[str] = None
