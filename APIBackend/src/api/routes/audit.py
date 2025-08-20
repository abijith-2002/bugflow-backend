from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends

from src.api.db.supabase_client import get_supabase
from src.api.deps import require_role
from src.api.models import AuditLogOut, UserProfile

router = APIRouter(prefix="", tags=["Audit Logs"])


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=List[AuditLogOut],
    summary="List audit logs",
    description="List audit logs. Admin only. Optional filters by entity_type and entity_id.",
)
def list_audit_logs(
    entity_type: Optional[str] = None, entity_id: Optional[UUID] = None, user: UserProfile = Depends(require_role("admin"))
):
    supabase = get_supabase()
    query = supabase.table("audit_logs").select("*").order("created_at", desc=True)
    if entity_type:
        query = query.eq("entity_type", entity_type)
    if entity_id:
        query = query.eq("entity_id", str(entity_id))
    result = query.execute()
    return result.data or []
