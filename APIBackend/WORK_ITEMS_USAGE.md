# Work Items API Usage

Base URL: /work-items

Schema (Supabase):
- Table: public.work_item
  - id integer not null (per-project incremental id, set by trigger)
  - project_id uuid not null references public.projects(id)
  - item_key text generated always as (<project_key>-<id>) unique
  - item_type text not null check (task/bug)
  - title varchar(200) not null
  - description text null
  - status varchar(40) not null default 'open'
  - priority varchar(20) null
  - created_at timestamptz not null default now()
  - PK: (project_id, id)

Endpoints:

GET /work-items
- Query params:
  - project_id (optional): UUID to filter by project
- Response 200: Array of work items

POST /work-items
- Body:
  {
    "project_id": "uuid",
    "item_type": "task" | "bug",
    "title": "Title",
    "description": "Optional",
    "status": "Optional (default 'open')",
    "priority": "Optional",
    "created_at": "Optional ISO timestamp"
  }
- Response 201: Created work item, including numeric id and item_key like KAI-1.

PATCH /work-items/{project_id}/{id}/status
- Body:
  {
    "status": "in_progress | done | blocked | open | <custom>"
  }
- Response 200: Updated work item.
- Notes:
  - Validation: status must be a non-empty string up to 40 chars.
  - Not found (404) if the (project_id, id) pair does not match a row.

Notes:
- The incremental id is per project and increases regardless of item_type.
- item_key is generated from the project's project_key and the numeric id.
- Ensure you have run assets/sql/projects_setup.sql and assets/sql/work_items_setup.sql in Supabase.

Troubleshooting:
- 500 Configuration error: Ensure SUPABASE_URL and SUPABASE_ANON_KEY are set in APIBackend/.env.
- 4xx from Supabase: Check that work_item table exists with policies and columns as defined above.
