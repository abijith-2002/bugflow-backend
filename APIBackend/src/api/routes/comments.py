from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from src.models.comment import CommentCreate, CommentUpdate, CommentResponse
from src.models.user import UserResponse
from src.services.comment import comment_service
from src.dependencies import get_current_user

router = APIRouter(prefix="/comments", tags=["Comments"])


# PUBLIC_INTERFACE
@router.post("/", response_model=CommentResponse, summary="Create a new comment")
async def create_comment(
    comment_data: CommentCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Create a new comment on a bug.
    
    - **content**: Comment content (required)
    - **bug_id**: ID of the bug this comment belongs to
    """
    return await comment_service.create_comment(comment_data, current_user)


# PUBLIC_INTERFACE
@router.get("/bug/{bug_id}", response_model=List[CommentResponse], summary="Get comments for a bug")
async def get_bug_comments(
    bug_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get all comments for a specific bug.
    
    - **bug_id**: The unique identifier of the bug
    """
    return await comment_service.get_comments_by_bug_id(bug_id)


# PUBLIC_INTERFACE
@router.put("/{comment_id}", response_model=CommentResponse, summary="Update comment")
async def update_comment(
    comment_id: str,
    comment_data: CommentUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Update an existing comment.
    
    - **comment_id**: The unique identifier of the comment
    - **content**: New comment content
    """
    return await comment_service.update_comment(comment_id, comment_data, current_user)


# PUBLIC_INTERFACE
@router.delete("/{comment_id}", summary="Delete comment")
async def delete_comment(
    comment_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Delete a comment.
    
    - **comment_id**: The unique identifier of the comment
    """
    success = await comment_service.delete_comment(comment_id, current_user)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    return {"message": "Comment deleted successfully"}
