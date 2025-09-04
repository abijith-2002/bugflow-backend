# Supabase Integration for APIBackend

This backend integrates with Supabase using the official supabase-py SDK for Auth and Database.

Required environment variables (set in bugflow-backend/APIBackend/.env — see .env.example):
- SUPABASE_URL: e.g., https://your-project-id.supabase.co
- SUPABASE_ANON_KEY: Project anon public key

Key SDK usage:
- Authentication:
  - supabase.auth.sign_up(SignUpWithPasswordCredentials(...))
  - supabase.auth.sign_in_with_password(SignInWithPasswordCredentials(...))
- Database (PostgREST):
  - supabase.table("projects").select(...).order(...).execute()
  - Inserts (supabase-py v2):
    resp = supabase.table("projects").insert(payload, returning="representation").execute()
    data = resp.data or []
    row = data[0] if isinstance(data, list) and data else data
  - supabase.table("work_item").select(...).eq(...).order(...).execute()
  - Counts via head=True and response.count (used by /projects for tasks_count and bugs_count):
    supabase.table("work_item").select("id", count="exact", head=True).eq("project_id", "<uuid>").eq("item_type", "task").execute().count
    supabase.table("work_item").select("id", count="exact", head=True).eq("project_id", "<uuid>").eq("item_type", "bug").execute().count
    Note: The backend defaults to 0 if response.count is missing or None.

Signup does not accept a request-provided redirect URL. Configure redirect behavior in Supabase (Site URL and Redirect URLs in the Supabase Dashboard). The backend does not need a SITE_URL variable.

## Current setup status

- Backend reads env vars via src/api/config.py, creates a client in src/api/supabase_client.py.
- SQL scripts for schema setup are provided under bugflow-backend/assets/sql/.
- Note: SupabaseTools RPC public.run_sql is not present in your project (PGRST202). Use the SQL Editor to run scripts.

## Database schema

Core tables used by this backend:
- public.projects (see assets/sql/projects_setup.sql)
- public.work_item (see assets/sql/work_items_setup.sql)
- public.work_item_comment (see assets/sql/work_item_comments_setup.sql)

Optional:
- public.tasks and public.bugs (legacy/minimal counts table; not required since work_item provides counts by item_type) — see assets/sql/tasks_bugs_setup.sql

RLS (development-permissive; tighten for production) is included in the scripts.

## Manual setup steps (Supabase Dashboard)

1) Run SQL:
   - Open SQL Editor and run assets/sql/projects_setup.sql
   - Then run assets/sql/work_items_setup.sql
   - Run assets/sql/work_item_comments_setup.sql
   - Run assets/sql/profiles_setup.sql  <-- required for /users/me display_name
   - Optionally run assets/sql/tasks_bugs_setup.sql

2) Verify:
   - public.projects exists with required columns & RLS policies.
   - public.work_item exists with composite PK (project_id, id), generated item_key, trigger for per-project id increment, and dev RLS policies.
   - public.work_item_comment exists with dev RLS policies and id trigger.
   - public.profiles exists with columns (id uuid pk, display_name text, updated_at timestamptz default now()), RLS enabled, and permissive dev policies for select/insert/update.

3) Authentication > URL Configuration:
   - Site URL: your frontend URL (e.g., http://localhost:3000/)
   - Additional Redirect URLs: http://localhost:3000/** and your production domain /**

4) Email templates (optional): Configure as needed.

5) Environment variables:
   - Backend: set SUPABASE_URL and SUPABASE_ANON_KEY in APIBackend/.env
   - Frontend (if applicable): REACT_APP_SUPABASE_URL and REACT_APP_SUPABASE_ANON_KEY

## Verification checklist

- GET /projects returns [] initially (200).
- POST /projects creates a project and returns it with defaults.
- GET /work-items returns [] initially; POST /work-items creates a task/bug and returns item_key like KAI-1.

If you encounter 401/403:
- Ensure RLS is enabled and dev policies exist as per scripts.
- Confirm the anon key is used and has access to public schema.

## Troubleshooting

- PGRST202 (public.run_sql not found): This is expected if the helper RPC isn't installed. Execute SQL via the dashboard.
- 500 Configuration error: Ensure APIBackend/.env has SUPABASE_URL and SUPABASE_ANON_KEY (see .env.example).
- 4xx from Supabase: Check table names, columns, constraints, and RLS policies.

## Notes

- Never hardcode URLs in auth flows; rely on Supabase dashboard URL configuration.
- Replace permissive RLS with policies based on auth.uid() for production.
