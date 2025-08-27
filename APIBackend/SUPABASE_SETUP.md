# APIBackend Supabase Setup

This backend uses the official supabase-py SDK for authentication and database operations.

1) Configure environment
   - Copy .env.example to .env
   - Set the following variables:
     - SUPABASE_URL
     - SUPABASE_ANON_KEY

2) Configure Supabase Authentication
   - In Supabase Dashboard > Authentication > URL Configuration:
     * Site URL: your frontend URL (e.g., http://localhost:3000/)
     * Add Redirect URLs: http://localhost:3000/** and your production domain /**
   - Optionally update Email Templates.

3) (Optional) Create profiles table and RLS policies
   - Create a `profiles` table keyed by user_id (references auth.users(id))
   - Enable RLS with row-level policies so each user can read/write only their own row.

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
- If POST /auth/signup returns a 500 with "Configuration error: Missing required environment variables...", ensure APIBackend/.env is present and contains values for:
  SUPABASE_URL, SUPABASE_ANON_KEY.
- If signup/login returns a 4xx with a JSON/text body, that is a Supabase error (e.g., weak password, email already registered, URL config). Review the response body and adjust inputs/settings accordingly.
- If project/task counts are incorrect or you see errors with grouped aggregations, ensure the work_item schema has been created per assets/sql/work_items_setup.sql. Optionally, create a database view that pre-aggregates counts and query it via supabase.table("project_counts_view").
