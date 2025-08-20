from typing import Any, Optional
from uuid import UUID

from src.api.db.supabase_client import get_supabase


# PUBLIC_INTERFACE
def create_audit_log(
    action: str, entity_type: str, entity_id: Optional[UUID], actor_id: Optional[UUID], metadata: Optional[dict[str, Any]] = None
) -> Optional[dict]:
    """
    Create an audit log entry.

    Args:
        action: Action name (e.g., 'create', 'update', 'delete', 'assign').
        entity_type: Entity type string (e.g., 'project', 'bug').
        entity_id: Optional entity UUID.
        actor_id: Optional actor user UUID.
        metadata: Optional metadata dict.

    Returns:
        Inserted row dict or None.
    """
    supabase = get_supabase()
    payload: dict[str, Any] = {
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
        "actor_id": str(actor_id) if actor_id else None,
        "metadata": metadata or {},
    }
    result = supabase.table("audit_logs").insert(payload).execute()
    if result.data:
        return result.data[0]
    return None
