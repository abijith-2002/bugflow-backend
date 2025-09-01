# APIBackend Supabase Setup

This backend uses the official supabase-py SDK for authentication and database operations.

1) Configure environment
   - Copy .env.example to .env in bugflow-backend/APIBackend/
   - Set the following variables in .env:
     - SUPABASE_URL
     - SUPABASE_ANON_KEY

2) Configure Supabase Authentication
   - In Supabase Dashboard > Authentication > URL Configuration:
     * Site URL: your frontend URL (e.g., http://localhost:3000/)
     * Add Redirect URLs: http://localhost:3000/** and your production domain /**
   - Optionally update Email Templates.

3) Create database schema
   - Use the Supabase SQL Editor to run these scripts in order:
     1. assets/sql/projects_setup.sql
     2. assets/sql/work_items_setup.sql
     3. assets/sql/work_item_comments_setup.sql
     4. (Optional) assets/sql/tasks_bugs_setup.sql
   - Note: The automation RPC (public.run_sql) is not installed in your project (PGRST202), so run scripts manually via the dashboard.

4) Endpoints
   - POST /auth/signup (supabase-py: auth.sign_up)
   - POST /auth/login (supabase-py: auth.sign_in_with_password)
   - /projects and /work-items perform CRUD using supabase.table(...)

5) Notes
   - The backend uses supabase-py to interact with both Auth and PostgREST.
   - Do not use REACT_APP_* vars in the backend.
   - The backend does not accept a redirect_to field on signup; configure redirect behavior entirely in Supabase (Site URL and Redirect URLs). No SITE_URL is required by the backend.
   - Email confirmation requirement is fully controlled by Supabase project settings. The backend forwards Supabase responses as-is.

Troubleshooting
- 500 Configuration error: Ensure APIBackend/.env has SUPABASE_URL and SUPABASE_ANON_KEY (see .env.example).
- 4xx from Supabase: Check table definitions, constraints, and RLS policies. Use assets/sql/*.sql scripts as source of truth.
- PGRST202 errors from tooling: Execute SQL via the Supabase Dashboard; the helper RPC is not present by default.
