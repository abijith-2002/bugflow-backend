# Supabase Setup: Unified Work Items

Run the SQL in bugflow-backend/assets/sql/work_items_setup.sql in Supabase SQL Editor to create the unified public.work_item table with:
- item_type ('task' or 'bug')
- Trigger-based incremental id per project, starting at 1
- item_key generated as <PROJECT_KEY>-<id> (e.g., KAI-1)

Notes:
- Requires public.projects with a unique project_key column (see assets/sql/projects_setup.sql).
- RLS is enabled with dev-permissive policies. Tighten for production.
- The FastAPI backend exposes:
  - GET /work-items?project_id=<uuid>
  - POST /work-items

Payload example (POST /work-items):
{
  "project_id": "uuid",
  "item_type": "task",
  "title": "Implement authentication",
  "description": "Integrate Supabase auth",
  "priority": "high"
}

Response example:
{
  "project_id": "uuid",
  "id": 1,
  "item_key": "KAI-1",
  "item_type": "task",
  "title": "Implement authentication",
  "description": "Integrate Supabase auth",
  "status": "open",
  "priority": "high",
  "created_at": "2025-01-01T12:00:00Z"
}
