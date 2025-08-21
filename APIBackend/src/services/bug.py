from typing import List, Optional
from fastapi import HTTPException, status
from src.database.client import supabase_client
from src.models.bug import BugCreate, BugUpdate, BugResponse, BugStatus, BugPriority
from src.models.user import UserResponse
from src.services.notification import notification_service
from datetime import datetime


class BugService:
    """Bug service for managing bugs"""
    
    def __init__(self):
        self.supabase = supabase_client.client

    async def create_bug(self, bug_data: BugCreate, current_user: UserResponse) -> BugResponse:
        """Create a new bug"""
        try:
            bug_dict = {
                "title": bug_data.title,
                "description": bug_data.description,
                "priority": bug_data.priority.value,
                "status": bug_data.status.value,
                "project_id": bug_data.project_id,
                "assigned_to": bug_data.assigned_to,
                "reported_by": current_user.id,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            response = self.supabase.table("bugs").insert(bug_dict).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create bug"
                )
            
            bug = response.data[0]
            
            # Create notification if bug is assigned
            if bug_data.assigned_to:
                await notification_service.create_notification(
                    user_id=bug_data.assigned_to,
                    title="New Bug Assigned",
                    message=f"You have been assigned a new bug: {bug_data.title}",
                    notification_type="bug_assigned"
                )
            
            return BugResponse(
                id=bug["id"],
                title=bug["title"],
                description=bug["description"],
                priority=BugPriority(bug["priority"]),
                status=BugStatus(bug["status"]),
                project_id=bug["project_id"],
                assigned_to=bug["assigned_to"],
                reported_by=bug["reported_by"],
                created_at=datetime.fromisoformat(bug["created_at"]),
                updated_at=datetime.fromisoformat(bug["updated_at"])
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create bug: {str(e)}"
            )

    async def get_bugs(self, project_id: Optional[str] = None, assigned_to: Optional[str] = None) -> List[BugResponse]:
        """Get bugs with optional filters"""
        try:
            query = self.supabase.table("bugs").select("*")
            
            if project_id:
                query = query.eq("project_id", project_id)
            if assigned_to:
                query = query.eq("assigned_to", assigned_to)
            
            response = query.execute()
            
            bugs = []
            for bug_data in response.data:
                bugs.append(BugResponse(
                    id=bug_data["id"],
                    title=bug_data["title"],
                    description=bug_data["description"],
                    priority=BugPriority(bug_data["priority"]),
                    status=BugStatus(bug_data["status"]),
                    project_id=bug_data["project_id"],
                    assigned_to=bug_data["assigned_to"],
                    reported_by=bug_data["reported_by"],
                    created_at=datetime.fromisoformat(bug_data["created_at"]),
                    updated_at=datetime.fromisoformat(bug_data["updated_at"])
                ))
            
            return bugs
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get bugs: {str(e)}"
            )

    async def get_bug_by_id(self, bug_id: str) -> Optional[BugResponse]:
        """Get bug by ID"""
        try:
            response = self.supabase.table("bugs").select("*").eq("id", bug_id).execute()
            
            if not response.data:
                return None
            
            bug_data = response.data[0]
            return BugResponse(
                id=bug_data["id"],
                title=bug_data["title"],
                description=bug_data["description"],
                priority=BugPriority(bug_data["priority"]),
                status=BugStatus(bug_data["status"]),
                project_id=bug_data["project_id"],
                assigned_to=bug_data["assigned_to"],
                reported_by=bug_data["reported_by"],
                created_at=datetime.fromisoformat(bug_data["created_at"]),
                updated_at=datetime.fromisoformat(bug_data["updated_at"])
            )
            
        except Exception:
            return None

    async def update_bug(self, bug_id: str, bug_data: BugUpdate, current_user: UserResponse) -> BugResponse:
        """Update an existing bug"""
        try:
            # Get existing bug
            existing_bug = await self.get_bug_by_id(bug_id)
            if not existing_bug:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bug not found"
                )
            
            # Prepare update data
            update_dict = {"updated_at": datetime.utcnow().isoformat()}
            if bug_data.title is not None:
                update_dict["title"] = bug_data.title
            if bug_data.description is not None:
                update_dict["description"] = bug_data.description
            if bug_data.priority is not None:
                update_dict["priority"] = bug_data.priority.value
            if bug_data.status is not None:
                update_dict["status"] = bug_data.status.value
            if bug_data.assigned_to is not None:
                update_dict["assigned_to"] = bug_data.assigned_to
            
            response = self.supabase.table("bugs").update(update_dict).eq("id", bug_id).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update bug"
                )
            
            bug = response.data[0]
            
            # Create notification for assignment changes
            if bug_data.assigned_to and bug_data.assigned_to != existing_bug.assigned_to:
                await notification_service.create_notification(
                    user_id=bug_data.assigned_to,
                    title="Bug Assigned",
                    message=f"You have been assigned to bug: {bug['title']}",
                    notification_type="bug_assigned"
                )
            
            # Create notification for status changes
            if bug_data.status and bug_data.status != existing_bug.status:
                if existing_bug.assigned_to:
                    await notification_service.create_notification(
                        user_id=existing_bug.assigned_to,
                        title="Bug Updated",
                        message=f"Bug status changed: {bug['title']} is now {bug_data.status.value}",
                        notification_type="bug_updated"
                    )
            
            return BugResponse(
                id=bug["id"],
                title=bug["title"],
                description=bug["description"],
                priority=BugPriority(bug["priority"]),
                status=BugStatus(bug["status"]),
                project_id=bug["project_id"],
                assigned_to=bug["assigned_to"],
                reported_by=bug["reported_by"],
                created_at=datetime.fromisoformat(bug["created_at"]),
                updated_at=datetime.fromisoformat(bug["updated_at"])
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update bug: {str(e)}"
            )

    async def delete_bug(self, bug_id: str, current_user: UserResponse) -> bool:
        """Delete a bug"""
        try:
            # Check if bug exists
            existing_bug = await self.get_bug_by_id(bug_id)
            if not existing_bug:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bug not found"
                )
            
            response = self.supabase.table("bugs").delete().eq("id", bug_id).execute()
            
            return len(response.data) > 0
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete bug: {str(e)}"
            )

    async def get_bug_statistics(self) -> dict:
        """Get bug statistics for dashboard"""
        try:
            # Get total bugs
            total_response = self.supabase.table("bugs").select("id", count="exact").execute()
            total_bugs = total_response.count or 0
            
            # Get open bugs
            open_response = self.supabase.table("bugs").select("id", count="exact").eq("status", "open").execute()
            open_bugs = open_response.count or 0
            
            # Get critical bugs
            critical_response = self.supabase.table("bugs").select("id", count="exact").eq("priority", "critical").execute()
            critical_bugs = critical_response.count or 0
            
            # Get resolved bugs
            resolved_response = self.supabase.table("bugs").select("id", count="exact").eq("status", "resolved").execute()
            resolved_bugs = resolved_response.count or 0
            
            return {
                "total_bugs": total_bugs,
                "open_bugs": open_bugs,
                "critical_bugs": critical_bugs,
                "resolved_bugs": resolved_bugs
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get bug statistics: {str(e)}"
            )


# Global bug service instance
bug_service = BugService()
