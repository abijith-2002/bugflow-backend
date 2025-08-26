# Supabase Integration for BugFlow (Backend + Frontend)

This repository integrates Supabase authentication (email/password) with:
- FastAPI backend (bugflow-backend/APIBackend)
- React frontend (bugflow-frontend/WebFrontend)

Backend provides /auth/signup and /auth/login using Supabase auth. Frontend calls these endpoints and applies Nord theme + Reddit Sans font.

IMPORTANT: SupabaseTools could not execute due to missing RPC public.run_sql in the Supabase project. You must enable the RPC or run the provided SQL manually in the Supabase SQL editor.

----------------------------------------------------------------------
Environment variables
----------------------------------------------------------------------

Backend (FastAPI):
- SUPABASE_URL: https://<project>.supabase.co
- SUPABASE_ANON_KEY: Supabase anon public key
- SITE_URL: Frontend public URL for auth redirects (e.g., http://localhost:3000/)
- FRONTEND_ORIGIN: CORS allowlist origin (e.g., http://localhost:3000)

Frontend (React):
- REACT_APP_API_BASE_URL: Backend API base URL (e.g., http://localhost:3001)

Note: As per container_env, the frontend currently has:
- REACT_APP_SUPABASE_URL
- REACT_APP_SUPABASE_KEY
- REACT_APP_SUPABASE_ANON_KEY
… and dev flags. The provided frontend code does NOT create a Supabase client directly; it calls the backend. You may keep these envs, but only REACT_APP_API_BASE_URL is required by the current code.

----------------------------------------------------------------------
Required Supabase SQL (run in SQL Editor)
----------------------------------------------------------------------

1) Enable required extensions (if not already):
-- Enable pgcrypto for gen_random_uuid
create extension if not exists pgcrypto;

2) Create a basic user profile table to store metadata for users (optional but recommended):
create table if not exists public.profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique,
  full_name text,
  created_at timestamptz default now()
);

3) RLS:
alter table public.profiles enable row level security;

-- Policies (example: each user can manage their profile row):
create policy "Read own profile" on public.profiles
for select using (auth.uid() = user_id);

create policy "Insert own profile" on public.profiles
for insert with check (auth.uid() = user_id);

create policy "Update own profile" on public.profiles
for update using (auth.uid() = user_id)
with check (auth.uid() = user_id);

4) (Optional) Trigger to auto-create profile after user signs up:
-- If desired, create a trigger function using edge functions or database function.
-- Many teams handle profile creation in application code post-signup.

----------------------------------------------------------------------
Auth Settings in Supabase Dashboard
----------------------------------------------------------------------

Authentication > URL Configuration:
- Site URL: set to your dev URL, e.g., http://localhost:3000/
- Redirect URLs allowlist: 
  - http://localhost:3000/**
  - Your production URL /**

Authentication > Email Templates:
- Update templates if desired.
- Ensure "Confirm Email" uses the redirect configured, if applicable.

----------------------------------------------------------------------
Backend integration details
----------------------------------------------------------------------

- FastAPI app uses environment variables:
  - SUPABASE_URL and SUPABASE_ANON_KEY to create the Supabase Python client.
  - SITE_URL (optional) used as email redirect hint for signup.
  - FRONTEND_ORIGIN used to configure CORS.

Endpoints:
- POST /auth/signup
  - body: { email, password, redirect_to? }
  - returns: { user_id?, access_token?, token_type?, requires_verification? }
- POST /auth/login
  - body: { email, password }
  - returns: { user_id?, access_token?, token_type: "bearer" }

Note: The backend currently exposes health check only in OpenAPI template. For session endpoints (/auth/me, /auth/logout) referenced by frontend code, you can return 204/200 or implement these later.

----------------------------------------------------------------------
Frontend integration details
----------------------------------------------------------------------

- React app uses REACT_APP_API_BASE_URL to call backend /auth/signup and /auth/login.
- Apply Nord theme and Reddit Sans via src/theme.css (already wired).
- Simple hash-based navigation used to switch between Login and Signup.

----------------------------------------------------------------------
What failed in automation and why
----------------------------------------------------------------------

SupabaseTools calls failed with:
PGRST202: Could not find the function public.run_sql(query) in the schema cache.

Resolution:
- In your Supabase project, create the RPC used by the automation or allow run_sql via admin. Alternatively, run the SQL above manually in the SQL editor.

----------------------------------------------------------------------
Post-setup checklist
----------------------------------------------------------------------

1) In Supabase:
   - Create tables and RLS per above.
   - Configure Authentication URLs and templates.

2) In backend environment:
   - Set SUPABASE_URL
   - Set SUPABASE_ANON_KEY
   - Set FRONTEND_ORIGIN=http://localhost:3000
   - Optionally set SITE_URL=http://localhost:3000/

3) In frontend environment:
   - Set REACT_APP_API_BASE_URL=http://localhost:3001

4) Start services and test:
   - Backend at :3001 (or your configured port)
   - Frontend at :3000
   - Test signup and login flows.

----------------------------------------------------------------------

Appendix: If you want client-side Supabase (optional future change)
----------------------------------------------------------------------

- Add supabase-js and create a client with:
  - REACT_APP_SUPABASE_URL
  - REACT_APP_SUPABASE_ANON_KEY
- Implement getURL() utility to generate dynamic redirectTo/emailRedirectTo.

This project currently keeps auth centralized in backend for simplicity.

