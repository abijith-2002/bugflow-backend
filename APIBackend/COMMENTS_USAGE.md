# Comments API Usage

Base URL: /work-items/{project_id}/{id}/comments

Schema (Supabase):
- Table: public.work_item_comment
  - project_id uuid not null references public.work_item(project_id) ON DELETE CASCADE
  - item_id integer not null references public.work_item(id) ON DELETE CASCADE
  - id integer not null (per-work-item incremental id, assigned by trigger)
  - body text not null
  - author_id uuid null (optional, could map to auth.users.id)
  - created_at timestamptz not null default now()
  - PK: (project_id, item_id, id)

Endpoints:

GET /work-items/{project_id}/{id}/comments
- Response 200: Array of comments ordered by created_at asc.

POST /work-items/{project_id}/{id}/comments
- Body:
  {
    "body": "This needs reproduction steps",
    "author_id": "optional-user-uuid"
  }
- Response 201: Created comment.

Required environment variables:
- SUPABASE_URL
- SUPABASE_ANON_KEY

Setup:
- Run assets/sql/work_item_comments_setup.sql in Supabase SQL Editor.
- Ensure projects and work_item schemas are already created.
