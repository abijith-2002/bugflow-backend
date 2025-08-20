# Supabase Integration Guide for BugFlow API

This project uses Supabase for:
- Authentication (Supabase Auth)
- Postgres database (via Supabase Postgres/PostgREST)
- Optional Realtime (not used yet)

The API backend communicates with Supabase using the official `supabase` Python SDK.

## Environment Variables

Create a `.env` file at `bugflow-backend/APIBackend/.env` with the following variables:

- SUPABASE_URL=your_supabase_project_url
- SUPABASE_SERVICE_ROLE_KEY=your_service_role_key  # Recommended for server-side usage
- SUPABASE_ANON_KEY=your_anon_public_key           # Optional fallback if service role key is not provided
- APP_SITE_URL=https://your-frontend-url           # Used for auth email redirect on signup
- CORS_ALLOW_ORIGINS=*                             # Comma-separated origins or * for all

Refer to `.env.example` for the template.

## Database Schema

Run the following SQL in the Supabase SQL editor to create the necessary tables:

```sql
-- Profiles table: ties to auth.users
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  role text not null default 'user' check (role in ('user','manager','admin')),
  created_at timestamp with time zone default now()
);

-- Projects
create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text,
  owner_id uuid references auth.users(id),
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- Bugs
create table if not exists public.bugs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  title text not null,
  description text,
  status text not null default 'open' check (status in ('open','in_progress','resolved','closed')),
  priority text not null check (priority in ('low','medium','high','critical')),
  reporter_id uuid not null references auth.users(id),
  assignee_id uuid references auth.users(id),
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- Notifications
create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  message text not null,
  read boolean not null default false,
  created_at timestamp with time zone default now()
);

-- Audit Logs
create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid references auth.users(id),
  action text not null,
  entity_type text not null,
  entity_id uuid,
  metadata jsonb default '{}'::jsonb,
  created_at timestamp with time zone default now()
);

-- Basic RLS enabling
alter table public.profiles enable row level security;
alter table public.projects enable row level security;
alter table public.bugs enable row level security;
alter table public.notifications enable row level security;
alter table public.audit_logs enable row level security;

-- Example RLS policies (adjust as needed)
-- Profiles: a user can select/update own profile; service role bypasses RLS.
create policy "Profiles are viewable by users themselves" on public.profiles
  for select using (auth.uid() = id);

create policy "Profiles can be inserted by service role" on public.profiles
  for insert with check (true);

create policy "Profiles can be updated by user themselves" on public.profiles
  for update using (auth.uid() = id);

-- Projects: readable by authenticated users
create policy "Projects are readable by all authenticated users" on public.projects
  for select using (auth.role() = 'authenticated');

-- Bugs: readable by authenticated users
create policy "Bugs are readable by all authenticated users" on public.bugs
  for select using (auth.role() = 'authenticated');

-- Notifications: only owner can read
create policy "Users can read their notifications" on public.notifications
  for select using (auth.uid() = user_id);

-- Audit Logs: admin-only via service role or edge logic; keep no select for anon.
```

Notes:
- When using the service role key from the backend, RLS rules are bypassed by default. You may tighten policies if you choose to use anon key from backend.

## Authentication Flow

- Registration: `POST /auth/register`
  - Uses Supabase Auth to create an account, with `email_redirect_to` set to `APP_SITE_URL/auth/callback`.
  - Creates a `profiles` record with role (`user` by default).

- Login: `POST /auth/login`
  - Uses Supabase Auth to authenticate and returns a bearer token.
  - The frontend should store the access token and send it as `Authorization: Bearer <token>` in subsequent API requests.

- Current user: `GET /auth/me`
  - Resolves the user from Supabase using the provided bearer token and returns profile info.

## Running

- Ensure `.env` file is created per the template.
- Install dependencies and run the server using uvicorn (example):
  ```
  cd bugflow-backend/APIBackend
  pip install -r requirements.txt
  uvicorn src.api.main:app --host 0.0.0.0 --port 3001 --reload
  ```

## OpenAPI

- Visit `/docs` for Swagger UI and `/openapi.json` for the schema.
- To regenerate the checked-in `interfaces/openapi.json`, run:
  ```
  cd bugflow-backend/APIBackend
  python -m src.api.generate_openapi
  ```

## Security Notes

- Prefer using `SUPABASE_SERVICE_ROLE_KEY` on the server side.
- Never expose the service role key to the frontend.
- If using `SUPABASE_ANON_KEY` in the backend, ensure RLS policies are correctly configured to allow necessary operations.
