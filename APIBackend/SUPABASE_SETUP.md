# APIBackend Supabase Setup

This backend uses the official supabase-py SDK for authentication and database operations.

1) Configure environment
   - Copy .env.example to .env in bugflow-backend/APIBackend/
   - Set the following variables in .env:
     - SUPABASE_URL (e.g., https://your-project-id.supabase.co)
     - SUPABASE_ANON_KEY (Anon public API key from Project Settings -> API)
   - Important: Do NOT use REACT_APP_* variables in the backend. Those are for the frontend only.

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
     4. assets/sql/profiles_setup.sql   <-- required for display_name near avatar (/users/me)
     5. (Optional) assets/sql/tasks_bugs_setup.sql
   - Note: The automation RPC (public.run_sql) is not installed in your project (PGRST202), so run scripts manually via the dashboard.
   - If you need a ready-to-paste snippet for profiles, see bugflow-backend/assets/sql/README_profiles_setup.md.

4) Endpoints
   - POST /auth/signup (supabase-py: auth.sign_up)
   - POST /auth/login (supabase-py: auth.sign_in_with_password)
   - /projects and /work-items perform CRUD using supabase.table(...)

5) Verifying authentication end-to-end
   - Login: POST /auth/login with email/password created in Supabase; note the access_token from response.
   - Call: GET /projects with header Authorization: Bearer <access_token>
   - Expected:
     * Valid token (from the same Supabase project configured in backend) => 200 OK with project list (possibly empty).
     * Missing header => 401 Unauthorized ("Authorization header missing")
     * Malformed header => 401 Unauthorized ("Invalid or malformed Authorization header")
     * Invalid/expired token => 401 Unauthorized ("Unauthorized")

Troubleshooting
- 401 Unauthorized from /projects:
  * Ensure the request includes header: Authorization: Bearer <token>
  * The token must be obtained from the same Supabase project as configured via SUPABASE_URL/SUPABASE_ANON_KEY in the backend.
  * Verify APIBackend/.env is loaded (src/api/main.py loads APIBackend/.env by default). If you changed the path, set ENV_PATH accordingly.
- 500 Configuration error:
  * Ensure APIBackend/.env has SUPABASE_URL and SUPABASE_ANON_KEY (see .env.example).
- 4xx from Supabase on data operations:
  * Check table definitions, constraints, and RLS policies. Use assets/sql/*.sql scripts as source of truth.
- PGRST202 errors from tooling:
  * Execute SQL via the Supabase Dashboard; the helper RPC is not present by default.
