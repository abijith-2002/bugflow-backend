# BugFlow Backend (APIBackend)

FastAPI backend for the BugFlow application. This service exposes REST APIs and integrates with Supabase for authentication.

## Endpoints
- GET / — Health check
- POST /signup — User signup via Supabase
- POST /login — User login via Supabase

## Environment Variables
Copy `.env.example` to `.env` and set values:
- SUPABASE_URL
- SUPABASE_ANON_KEY
- FRONTEND_ORIGIN (optional; defaults to "*")
- SITE_URL (optional; used for signup email redirect)

## Supabase Database Setup
Our automation failed because your project is missing the helper RPC `public.run_sql(query text)`. Create it first, then apply schema:

SQL for helper RPC:
```
create or replace function public.run_sql(query text)
returns json
language plpgsql
as $$
declare
  result json;
begin
  execute query into result;
  return result;
end;
$$;
```

Profiles table and RLS:
```
create table if not exists public.profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid unique not null,
  email text not null,
  full_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
create or replace function public.handle_new_profile()
returns trigger
language plpgsql
as $$
begin
  if new.user_id is null then
    new.user_id := auth.uid();
  end if;
  new.updated_at := now();
  return new;
end;
$$;
drop trigger if exists trg_profiles_biu on public.profiles;
create trigger trg_profiles_biu before insert or update on public.profiles
for each row execute function public.handle_new_profile();

drop policy if exists "Read own profile" on public.profiles;
create policy "Read own profile" on public.profiles for select using (auth.uid() = user_id);
drop policy if exists "Insert own profile" on public.profiles;
create policy "Insert own profile" on public.profiles for insert with check (auth.uid() = user_id or (user_id is null and auth.uid() is not null));
drop policy if exists "Update own profile" on public.profiles;
create policy "Update own profile" on public.profiles for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
```

## Run locally
1. Create and fill .env
2. Install dependencies: `pip install -r APIBackend/requirements.txt`
3. Start server (from APIBackend root):
   `uvicorn src.api.main:app --host 0.0.0.0 --port 3001 --reload`

OpenAPI docs: `/docs`