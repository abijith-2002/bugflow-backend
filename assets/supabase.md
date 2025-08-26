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
- Database inspection/creation via automation is pending due to a temporary tools RPC issue (public.run_sql not available), which blocked the required SupabaseTools steps.

## Required actions in Supabase Dashboard

1) Authentication > URL Configuration
   - Site URL: set to your frontend URL (dev: http://localhost:3000/).
   - Additional Redirect URLs: include http://localhost:3000/** and your production domain /**.

2) Authentication > Email Templates
   - Optionally customize emails. Ensure links point to your configured Site URL.

3) Tables and Policies
   - Projects table for dashboard:
     - Create a `projects` table with columns:
       - id uuid primary key default gen_random_uuid()
       - name text not null
       - description text
       - created_at timestamptz not null default now()
     - Enable RLS and add policies suited to your app. For development, you may allow:
       - SELECT: using (true)
       - INSERT: with check (true)
     - In production, restrict based on auth.uid() or project membership.
   - (Optional) Profiles table for user metadata:
     - id uuid default gen_random_uuid() primary key
     - user_id uuid not null unique references auth.users(id) on delete cascade
     - full_name text
     - avatar_url text
     - created_at timestamptz default now()
     - updated_at timestamptz default now()
     - Example RLS policies:
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

Frontend (React) will use:
- REACT_APP_SUPABASE_URL
- REACT_APP_SUPABASE_ANON_KEY

Make sure the frontend uses a getURL() utility if it needs to construct URLs dynamically; the backend will not accept a redirect URL for signup.

## Testing locally

- Copy APIBackend/.env.example to APIBackend/.env and set real values.
- Start backend and call:
  - POST /auth/signup
  - POST /auth/login
- Inspect responses and verify signup emails from Supabase use the Site URL configured in the Supabase dashboard.

Troubleshooting login and email confirmation:
- If Supabase project has email confirmation disabled, login with correct credentials should return 200 and include session/access_token.
- If you still receive a 4xx error mentioning "email not confirmed", that message originates from Supabase (check Authentication settings in the dashboard). The backend does not enforce confirmation checks; it forwards Supabase's error payload.
- If you receive a 200 without a session (unexpected), the backend will return 502 "Supabase did not return a session"; verify your Supabase project configuration and keys.

## Notes

- Never hardcode URLs in auth flows; use environment variables and Supabase URL configuration.
- In production, restrict CORS origins to your frontend domain(s).
