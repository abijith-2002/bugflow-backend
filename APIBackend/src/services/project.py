from typing import List, Optional
from fastapi import HTTPException, status
from src.database.client import supabase_client
from src.models.project import ProjectCreate, ProjectUpdate, ProjectResponse
from src.models.user import UserResponse
from datetime import datetime


class ProjectService:
    """Project service for managing projects"""
    
    def __init__(self):
        self.supabase = supabase_client.client

    async def create_project(self, project_data: ProjectCreate, current_user: UserResponse) -> ProjectResponse:
        """Create a new project"""
        try:
            project_dict = {
                "name": project_data.name,
                "description": project_data.description,
                "created_by": current_user.id,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            response = self.supabase.table("projects").insert(project_dict).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create project"
                )
            
            project = response.data[0]
            return ProjectResponse(
                id=project["id"],
                name=project["name"],
                description=project["description"],
                created_by=project["created_by"],
                created_at=datetime.fromisoformat(project["created_at"]),
                updated_at=datetime.fromisoformat(project["updated_at"])
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create project: {str(e)}"
            )

    async def get_projects(self, current_user: UserResponse) -> List[ProjectResponse]:
        """Get all projects accessible to the user"""
        try:
            response = self.supabase.table("projects").select("*").execute()
            
            projects = []
            for project_data in response.data:
                projects.append(ProjectResponse(
                    id=project_data["id"],
                    name=project_data["name"],
                    description=project_data["description"],
                    created_by=project_data["created_by"],
                    created_at=datetime.fromisoformat(project_data["created_at"]),
                    updated_at=datetime.fromisoformat(project_data["updated_at"])
                ))
            
            return projects
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get projects: {str(e)}"
            )

    async def get_project_by_id(self, project_id: str) -> Optional[ProjectResponse]:
        """Get project by ID"""
        try:
            response = self.supabase.table("projects").select("*").eq("id", project_id).execute()
            
            if not response.data:
                return None
            
            project_data = response.data[0]
            return ProjectResponse(
                id=project_data["id"],
                name=project_data["name"],
                description=project_data["description"],
                created_by=project_data["created_by"],
                created_at=datetime.fromisoformat(project_data["created_at"]),
                updated_at=datetime.fromisoformat(project_data["updated_at"])
            )
            
        except Exception:
            return None

    async def update_project(self, project_id: str, project_data: ProjectUpdate, current_user: UserResponse) -> ProjectResponse:
        """Update an existing project"""
        try:
            # Check if project exists
            existing_project = await self.get_project_by_id(project_id)
            if not existing_project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found"
                )
            
            # Prepare update data
            update_dict = {"updated_at": datetime.utcnow().isoformat()}
            if project_data.name is not None:
                update_dict["name"] = project_data.name
            if project_data.description is not None:
                update_dict["description"] = project_data.description
            
            response = self.supabase.table("projects").update(update_dict).eq("id", project_id).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update project"
                )
            
            project = response.data[0]
            return ProjectResponse(
                id=project["id"],
                name=project["name"],
                description=project["description"],
                created_by=project["created_by"],
                created_at=datetime.fromisoformat(project["created_at"]),
                updated_at=datetime.fromisoformat(project["updated_at"])
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update project: {str(e)}"
            )

    async def delete_project(self, project_id: str, current_user: UserResponse) -> bool:
        """Delete a project"""
        try:
            # Check if project exists
            existing_project = await self.get_project_by_id(project_id)
            if not existing_project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found"
                )
            
            response = self.supabase.table("projects").delete().eq("id", project_id).execute()
            
            return len(response.data) > 0
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete project: {str(e)}"
            )


# Global project service instance
project_service = ProjectService()
