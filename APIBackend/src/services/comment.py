from typing import List
from fastapi import HTTPException, status
from src.database.client import supabase_client
from src.models.comment import CommentCreate, CommentUpdate, CommentResponse
from src.models.user import UserResponse
from src.services.notification import notification_service
from src.services.bug import bug_service
from datetime import datetime


class CommentService:
    """Comment service for managing bug comments"""
    
    def __init__(self):
        self.supabase = supabase_client.client

    async def create_comment(self, comment_data: CommentCreate, current_user: UserResponse) -> CommentResponse:
        """Create a new comment"""
        try:
            # Verify the bug exists
            bug = await bug_service.get_bug_by_id(comment_data.bug_id)
            if not bug:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bug not found"
                )
            
            comment_dict = {
                "content": comment_data.content,
                "bug_id": comment_data.bug_id,
                "user_id": current_user.id,
                "created_at": datetime.utcnow().isoformat()
            }
            
            response = self.supabase.table("comments").insert(comment_dict).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create comment"
                )
            
            comment = response.data[0]
            
            # Create notification for bug assignee
            if bug.assigned_to and bug.assigned_to != current_user.id:
                await notification_service.create_notification(
                    user_id=bug.assigned_to,
                    title="New Comment",
                    message=f"New comment added to bug: {bug.title}",
                    notification_type="comment_added"
                )
            
            # Create notification for bug reporter if different from assignee and commenter
            if (bug.reported_by != current_user.id and 
                bug.reported_by != bug.assigned_to):
                await notification_service.create_notification(
                    user_id=bug.reported_by,
                    title="New Comment",
                    message=f"New comment added to bug: {bug.title}",
                    notification_type="comment_added"
                )
            
            return CommentResponse(
                id=comment["id"],
                content=comment["content"],
                bug_id=comment["bug_id"],
                user_id=comment["user_id"],
                created_at=datetime.fromisoformat(comment["created_at"])
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create comment: {str(e)}"
            )

    async def get_comments_by_bug_id(self, bug_id: str) -> List[CommentResponse]:
        """Get all comments for a bug"""
        try:
            response = self.supabase.table("comments").select("*").eq("bug_id", bug_id).order("created_at", desc=False).execute()
            
            comments = []
            for comment_data in response.data:
                comments.append(CommentResponse(
                    id=comment_data["id"],
                    content=comment_data["content"],
                    bug_id=comment_data["bug_id"],
                    user_id=comment_data["user_id"],
                    created_at=datetime.fromisoformat(comment_data["created_at"])
                ))
            
            return comments
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get comments: {str(e)}"
            )

    async def get_comment_by_id(self, comment_id: str) -> CommentResponse:
        """Get comment by ID"""
        try:
            response = self.supabase.table("comments").select("*").eq("id", comment_id).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Comment not found"
                )
            
            comment_data = response.data[0]
            return CommentResponse(
                id=comment_data["id"],
                content=comment_data["content"],
                bug_id=comment_data["bug_id"],
                user_id=comment_data["user_id"],
                created_at=datetime.fromisoformat(comment_data["created_at"])
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get comment: {str(e)}"
            )

    async def update_comment(self, comment_id: str, comment_data: CommentUpdate, current_user: UserResponse) -> CommentResponse:
        """Update an existing comment"""
        try:
            # Get existing comment
            existing_comment = await self.get_comment_by_id(comment_id)
            
            # Check if user owns the comment
            if existing_comment.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only edit your own comments"
                )
            
            # Prepare update data
            update_dict = {}
            if comment_data.content is not None:
                update_dict["content"] = comment_data.content
            
            if not update_dict:
                return existing_comment
            
            response = self.supabase.table("comments").update(update_dict).eq("id", comment_id).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update comment"
                )
            
            comment = response.data[0]
            return CommentResponse(
                id=comment["id"],
                content=comment["content"],
                bug_id=comment["bug_id"],
                user_id=comment["user_id"],
                created_at=datetime.fromisoformat(comment["created_at"])
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update comment: {str(e)}"
            )

    async def delete_comment(self, comment_id: str, current_user: UserResponse) -> bool:
        """Delete a comment"""
        try:
            # Get existing comment
            existing_comment = await self.get_comment_by_id(comment_id)
            
            # Check if user owns the comment
            if existing_comment.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only delete your own comments"
                )
            
            response = self.supabase.table("comments").delete().eq("id", comment_id).execute()
            
            return len(response.data) > 0
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete comment: {str(e)}"
            )


# Global comment service instance
comment_service = CommentService()
