# Supabase Integration for APIBackend

This backend integrates with Supabase Auth using direct HTTP calls (no heavy SDK). It requires the following environment variables:

- SUPABASE_URL: e.g., https://your-project-id.supabase.co
- SUPABASE_ANON_KEY: Project anon public key
- SITE_URL: Public frontend URL for email confirmation redirect (must be allow‑listed in Supabase > Authentication > URL Configuration)

Auth endpoints used by the backend:
- POST {SUPABASE_URL}/auth/v1/signup
- POST {SUPABASE_URL}/auth/v1/token?grant_type=password

HTTP headers sent:
- apikey: SUPABASE_ANON_KEY
- Authorization: Bearer SUPABASE_ANON_KEY
- Content-Type: application/json

Signup forwards emailRedirectTo using either the request-provided `redirect_to` or the configured `SITE_URL`.

## Current setup status

- Backend code is integrated and ready. It reads env vars via src/api/config.py and calls Supabase Auth via src/api/supabase_client.py using httpx.
- Database inspection/creation via automation is pending due to a temporary tools RPC issue (public.run_sql not available), which blocked the required SupabaseTools steps.

## Required actions in Supabase Dashboard

1) Authentication > URL Configuration
   - Site URL: set to your frontend URL (dev: http://localhost:3000/).
   - Additional Redirect URLs: include http://localhost:3000/** and your production domain /**.

2) Authentication > Email Templates
   - Optionally customize emails. Ensure links point to your `SITE_URL` or use the redirect passed at signup.

3) Policies and Tables (optional for future profile data)
   - If you plan to store user profile metadata, create a `profiles` table with columns:
     - id uuid default gen_random_uuid() primary key
     - user_id uuid not null unique references auth.users(id) on delete cascade
     - full_name text
     - avatar_url text
     - created_at timestamptz default now()
     - updated_at timestamptz default now()
   - Example RLS policies (enable RLS and allow users to select/update only their own row):
     - SELECT: using (auth.uid() = user_id)
     - INSERT: with check (auth.uid() = user_id)
     - UPDATE: using (auth.uid() = user_id)
     - DELETE: using (auth.uid() = user_id)

When the Supabase tools adapter is available, we will:
- List existing tables.
- Create the `profiles` table if missing.
- Apply RLS policies via SQL.

## Environment variables

Backend (.env for APIBackend):
- SUPABASE_URL
- SUPABASE_ANON_KEY
- SITE_URL

Frontend (React) will use:
- REACT_APP_SUPABASE_URL
- REACT_APP_SUPABASE_ANON_KEY
- REACT_APP_SITE_URL (optional helper for redirects)

Make sure the frontend uses a getURL() utility to construct redirect URLs dynamically.

## Testing locally

- Copy APIBackend/.env.example to APIBackend/.env and set real values.
- Start backend and call:
  - POST /auth/signup
  - POST /auth/login
- Inspect responses and verify email redirects hit your frontend (SITE_URL or provided redirect_to).

## Notes

- Never hardcode URLs in auth flows; use environment variables.
- In production, restrict CORS origins to your frontend domain(s).
