from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from src.models.project import ProjectCreate, ProjectUpdate, ProjectResponse
from src.models.user import UserResponse
from src.services.project import project_service
from src.dependencies import get_current_user, get_manager_or_admin_user

router = APIRouter(prefix="/projects", tags=["Projects"])


# PUBLIC_INTERFACE
@router.post("/", response_model=ProjectResponse, summary="Create a new project")
async def create_project(
    project_data: ProjectCreate,
    current_user: UserResponse = Depends(get_manager_or_admin_user)
):
    """
    Create a new project.
    
    - **name**: Project name (required)
    - **description**: Project description (optional)
    
    Requires manager or admin role.
    """
    return await project_service.create_project(project_data, current_user)


# PUBLIC_INTERFACE
@router.get("/", response_model=List[ProjectResponse], summary="Get all projects")
async def get_projects(current_user: UserResponse = Depends(get_current_user)):
    """
    Get all projects accessible to the current user.
    
    Returns a list of all projects in the system.
    """
    return await project_service.get_projects(current_user)


# PUBLIC_INTERFACE
@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project by ID")
async def get_project(
    project_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get a specific project by its ID.
    
    - **project_id**: The unique identifier of the project
    """
    project = await project_service.get_project_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


# PUBLIC_INTERFACE
@router.put("/{project_id}", response_model=ProjectResponse, summary="Update project")
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    current_user: UserResponse = Depends(get_manager_or_admin_user)
):
    """
    Update an existing project.
    
    - **project_id**: The unique identifier of the project
    - **name**: New project name (optional)
    - **description**: New project description (optional)
    
    Requires manager or admin role.
    """
    return await project_service.update_project(project_id, project_data, current_user)


# PUBLIC_INTERFACE
@router.delete("/{project_id}", summary="Delete project")
async def delete_project(
    project_id: str,
    current_user: UserResponse = Depends(get_manager_or_admin_user)
):
    """
    Delete a project.
    
    - **project_id**: The unique identifier of the project
    
    Requires manager or admin role.
    """
    success = await project_service.delete_project(project_id, current_user)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return {"message": "Project deleted successfully"}
