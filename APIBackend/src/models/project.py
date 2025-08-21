from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    """Base project model with common fields"""
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")


class ProjectCreate(ProjectBase):
    """Model for creating a new project"""
    pass


class ProjectUpdate(BaseModel):
    """Model for updating project information"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")


class ProjectResponse(ProjectBase):
    """Model for project response data"""
    id: str = Field(..., description="Project's unique identifier")
    created_by: str = Field(..., description="ID of user who created the project")
    created_at: datetime = Field(..., description="Project creation timestamp")
    updated_at: datetime = Field(..., description="Project last update timestamp")

    class Config:
        from_attributes = True
