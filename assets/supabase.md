# Supabase Integration Guide for BugFlow API

This project uses Supabase for:
- Authentication (Supabase Auth)
- Postgres database (via Supabase Postgres/PostgREST)
- Storage (file uploads, e.g., bug attachments)
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

In Supabase Dashboard:
- Go to Authentication > URL Configuration
  - Site URL: your frontend URL (e.g., http://localhost:3000 for dev)
  - Additional Redirect URLs:
    * http://localhost:3000/**
    * https://yourapp.com/**
- If you use custom email templates, ensure any redirect URLs match the ones above.

## Database Schema

Run the following SQL in the Supabase SQL editor to create the necessary tables:

```sql
-- Enable required extensions
create extension if not exists "pgcrypto";
create extension if not exists "uuid-ossp";

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

-- Profiles: a user can select/update own profile; service role bypasses RLS.
do $$
begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='profiles' and policyname='Profiles are viewable by users themselves') then
    create policy "Profiles are viewable by users themselves" on public.profiles
      for select using (auth.uid() = id);
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='profiles' and policyname='Profiles can be inserted by service role') then
    create policy "Profiles can be inserted by service role" on public.profiles
      for insert with check (true);
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='profiles' and policyname='Profiles can be updated by user themselves') then
    create policy "Profiles can be updated by user themselves" on public.profiles
      for update using (auth.uid() = id);
  end if;
end $$;

-- Projects: readable by authenticated users
do $$
begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='projects' and policyname='Projects are readable by all authenticated users') then
    create policy "Projects are readable by all authenticated users" on public.projects
      for select using (auth.role() = 'authenticated');
  end if;
end $$;

-- Bugs: readable by authenticated users
do $$
begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='bugs' and policyname='Bugs are readable by all authenticated users') then
    create policy "Bugs are readable by all authenticated users" on public.bugs
      for select using (auth.role() = 'authenticated');
  end if;
end $$;

-- Notifications: only owner can read
do $$
begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='notifications' and policyname='Users can read their notifications') then
    create policy "Users can read their notifications" on public.notifications
      for select using (auth.uid() = user_id);
  end if;
end $$;

-- OPTIONAL: stricter write policies if you use anon key from backend:
-- Projects insert/update/delete by users with role manager/admin in profiles
-- Note: service role bypasses RLS.
create or replace function public.is_manager_or_admin(uid uuid)
returns boolean language sql stable as $$
  select exists(select 1 from public.profiles p where p.id = uid and p.role in ('manager','admin'));
$$;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='projects' and policyname='Projects insert by manager or admin') then
    create policy "Projects insert by manager or admin" on public.projects
      for insert with check (public.is_manager_or_admin(auth.uid()));
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='projects' and policyname='Projects update by manager or admin') then
    create policy "Projects update by manager or admin" on public.projects
      for update using (public.is_manager_or_admin(auth.uid()));
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='projects' and policyname='Projects delete by manager or admin') then
    create policy "Projects delete by manager or admin" on public.projects
      for delete using (public.is_manager_or_admin(auth.uid()));
  end if;
end $$;

-- Bugs insert: any authenticated user can insert as reporter (server can set reporter_id)
do $$
begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='bugs' and policyname='Bugs insert by authenticated') then
    create policy "Bugs insert by authenticated" on public.bugs
      for insert with check (auth.role() = 'authenticated');
  end if;
end $$;

-- Audit Logs: generally queried by backend using service role; avoid select policies for anon.
```

## Storage Configuration (Attachments)

If you want to store file attachments for bugs, create a private bucket and RLS:

```sql
-- Create private bucket for attachments
select storage.create_bucket('attachments', public := false);

-- Policies on storage.objects (applied per object)
-- Authenticated users can upload to 'attachments' bucket
create policy if not exists "Upload attachments (authenticated)"
on storage.objects for insert
with check (bucket_id = 'attachments' and auth.role() = 'authenticated');

-- Authenticated users can read from 'attachments' bucket
create policy if not exists "Read attachments (authenticated)"
on storage.objects for select
using (bucket_id = 'attachments' and auth.role() = 'authenticated');

-- Optionally, restrict by folder prefix 'user_id/*' (recommended):
-- When uploading from the client, prefix the path with the user id, e.g., `${user.id}/filename.ext`
-- Then replace the read policy above with:
-- using (bucket_id = 'attachments' and (auth.uid()::text = split_part(name, '/', 1)))
```

Notes:
- When using the service role key from the backend, RLS rules are bypassed by default.
- If using `SUPABASE_ANON_KEY` from the backend, ensure write policies permit inserts/updates as required.

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
  uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
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

## After Setting Environment Variables

Once SUPABASE_URL and keys are configured in the environment:
1) I will run Supabase checks:
   - List existing tables
   - Create any missing tables
   - Apply RLS and storage policies
2) Verify auth flows and role checks end-to-end.
