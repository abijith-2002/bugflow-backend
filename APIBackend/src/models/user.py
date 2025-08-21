from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration"""
    USER = "user"
    ADMIN = "admin" 
    PROJECT_MANAGER = "project_manager"


class UserBase(BaseModel):
    """Base user model with common fields"""
    email: str = Field(..., description="User's email address")
    role: UserRole = Field(UserRole.USER, description="User's role in the system")


class UserCreate(UserBase):
    """Model for creating a new user"""
    password: str = Field(..., min_length=8, description="User's password")


class UserUpdate(BaseModel):
    """Model for updating user information"""
    role: Optional[UserRole] = Field(None, description="User's role in the system")


class UserResponse(UserBase):
    """Model for user response data"""
    id: str = Field(..., description="User's unique identifier")
    created_at: datetime = Field(..., description="User creation timestamp")
    updated_at: datetime = Field(..., description="User last update timestamp")

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Model for user login"""
    email: str = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class AuthResponse(BaseModel):
    """Model for authentication response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    user: UserResponse = Field(..., description="User information")
