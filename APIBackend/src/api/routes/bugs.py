from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from src.models.bug import BugCreate, BugUpdate, BugResponse
from src.models.user import UserResponse
from src.services.bug import bug_service
from src.dependencies import get_current_user

router = APIRouter(prefix="/bugs", tags=["Bugs"])


# PUBLIC_INTERFACE
@router.post("/", response_model=BugResponse, summary="Create a new bug")
async def create_bug(
    bug_data: BugCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Create a new bug report.
    
    - **title**: Bug title (required)
    - **description**: Bug description (optional)
    - **priority**: Bug priority (low, medium, high, critical)
    - **status**: Bug status (open, in_progress, resolved, closed)
    - **project_id**: ID of the project this bug belongs to
    - **assigned_to**: ID of the user assigned to this bug (optional)
    """
    return await bug_service.create_bug(bug_data, current_user)


# PUBLIC_INTERFACE
@router.get("/", response_model=List[BugResponse], summary="Get bugs")
async def get_bugs(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user ID"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get bugs with optional filters.
    
    - **project_id**: Filter bugs by project (optional)
    - **assigned_to**: Filter bugs by assigned user (optional)
    """
    return await bug_service.get_bugs(project_id=project_id, assigned_to=assigned_to)


# PUBLIC_INTERFACE
@router.get("/statistics", summary="Get bug statistics")
async def get_bug_statistics(current_user: UserResponse = Depends(get_current_user)):
    """
    Get bug statistics for dashboard display.
    
    Returns counts for total, open, critical, and resolved bugs.
    """
    return await bug_service.get_bug_statistics()


# PUBLIC_INTERFACE
@router.get("/{bug_id}", response_model=BugResponse, summary="Get bug by ID")
async def get_bug(
    bug_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get a specific bug by its ID.
    
    - **bug_id**: The unique identifier of the bug
    """
    bug = await bug_service.get_bug_by_id(bug_id)
    if not bug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bug not found"
        )
    return bug


# PUBLIC_INTERFACE
@router.put("/{bug_id}", response_model=BugResponse, summary="Update bug")
async def update_bug(
    bug_id: str,
    bug_data: BugUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Update an existing bug.
    
    - **bug_id**: The unique identifier of the bug
    - **title**: New bug title (optional)
    - **description**: New bug description (optional)
    - **priority**: New bug priority (optional)
    - **status**: New bug status (optional)
    - **assigned_to**: New assigned user ID (optional)
    """
    return await bug_service.update_bug(bug_id, bug_data, current_user)


# PUBLIC_INTERFACE
@router.delete("/{bug_id}", summary="Delete bug")
async def delete_bug(
    bug_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Delete a bug.
    
    - **bug_id**: The unique identifier of the bug
    """
    success = await bug_service.delete_bug(bug_id, current_user)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bug not found"
        )
    return {"message": "Bug deleted successfully"}
