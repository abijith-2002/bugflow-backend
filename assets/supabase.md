# Supabase Integration for APIBackend

This backend integrates with Supabase Auth using direct HTTP calls (no heavy SDK). It requires the following environment variables:

- SUPABASE_URL: e.g., https://your-project-id.supabase.co
- SUPABASE_ANON_KEY: Project anon public key

Auth endpoints used by the backend:
- POST {SUPABASE_URL}/auth/v1/signup
- POST {SUPABASE_URL}/auth/v1/token?grant_type=password

HTTP headers sent:
- apikey: SUPABASE_ANON_KEY
- Authorization: Bearer SUPABASE_ANON_KEY
- Content-Type: application/json

Signup does not accept a request-provided redirect URL. Configure all redirect behavior in Supabase (Site URL and Redirect URLs in the Supabase Dashboard). The backend does not need a SITE_URL variable.

## Current setup status

- Backend code is integrated and ready. It reads env vars via src/api/config.py and calls Supabase Auth via src/api/supabase_client.py using httpx.
- Database automation via SupabaseTools is temporarily blocked in this project because public.run_sql is not available in the schema cache. As a result, automated list/create/policy operations failed. We provide a SQL script and manual steps below.

## Database schema: projects

Required by /projects GET and POST endpoints (see APIBackend/PROJECTS_USAGE.md):

Table: public.projects
- id uuid primary key default gen_random_uuid()
- name text not null
- description text null
- created_at timestamptz not null default now()

RLS (development-permissive; tighten for production):
- SELECT policy: using (true)
- INSERT policy: with check (true)

You can execute the standardized SQL from this repository:
- Path: bugflow-backend/assets/sql/projects_setup.sql
- How: In Supabase Dashboard > SQL Editor > New query, paste the content of the file and click Run.

## Manual setup steps (Supabase Dashboard)

1) SQL
   - Open SQL Editor and run the contents of assets/sql/projects_setup.sql.

2) Verify table & policies
   - Table Editor: confirm public.projects exists with columns id, name, description, created_at.
   - Policies tab: confirm two policies:
     * "Allow select for all (dev)" for SELECT using (true)
     * "Allow insert for all (dev)" for INSERT with check (true)
   - Ensure RLS is enabled on projects.

3) Authentication > URL Configuration
   - Site URL: set to your frontend URL (dev: http://localhost:3000/).
   - Additional Redirect URLs: include http://localhost:3000/** and your production domain /**.

4) Authentication > Email Templates
   - Optional customization.

5) Environment variables
   - Backend (APIBackend/.env):
     * SUPABASE_URL
     * SUPABASE_ANON_KEY
   - Frontend (React, if applicable):
     * REACT_APP_SUPABASE_URL
     * REACT_APP_SUPABASE_ANON_KEY

## Verification checklist

- Call GET /projects: should return [] initially (200).
- Call POST /projects with body {"name":"Test","description":"Optional"}:
  - Expect 201 with created row including id (uuid) and created_at (timestamp).
- Call GET /projects again: should include the new project, ordered by created_at desc.

If you encounter 401/403 on /projects:
- Check that RLS is enabled and the dev policies exist as above.
- Confirm the API key used is the anon key and has access to public schema.

## Troubleshooting

- SupabaseTools errors: If you see PGRST202 about public.run_sql not found, it means the RPC helper is not available in your project. Use the provided SQL script via the SQL Editor.
- 500 Configuration error from backend: Ensure APIBackend/.env has SUPABASE_URL and SUPABASE_ANON_KEY.
- 4xx from Supabase: Check table name, columns, and RLS policies.

## Notes

- Never hardcode URLs in auth flows; use environment variables and Supabase URL configuration.
- In production, replace dev-permissive RLS with policies scoped to auth.uid() or project membership.
