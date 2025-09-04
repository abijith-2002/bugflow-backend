# Supabase: profiles table setup (manual run)

Purpose
- Provide public.profiles (id uuid PK = auth.users.id) to store a display_name used by the backend endpoint GET /users/me.

Why this file
- Automated SQL execution via public.run_sql is not available in your Supabase project (PGRST202). Use the SQL Editor to run these commands.

Steps
1) Open Supabase Dashboard > SQL Editor
2) Paste and run the following SQL:

-------------------------------------------------
create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key,                 -- matches auth.users.id
  display_name text null,              -- preferred display name
  updated_at timestamp with time zone not null default now()
);

create index if not exists idx_profiles_id on public.profiles (id);

alter table public.profiles enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='profiles' and policyname='Allow select for all (dev)'
  ) then
    create policy "Allow select for all (dev)" on public.profiles for select using (true);
  end if;

  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='profiles' and policyname='Allow insert for all (dev)'
  ) then
    create policy "Allow insert for all (dev)" on public.profiles for insert with check (true);
  end if;

  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='profiles' and policyname='Allow update for all (dev)'
  ) then
    create policy "Allow update for all (dev)" on public.profiles for update using (true) with check (true);
  end if;
end $$;
-------------------------------------------------

3) Verification
- select column_name, data_type from information_schema.columns where table_schema='public' and table_name='profiles';
- select * from public.profiles limit 1;
- You should see RLS enabled on the table and the three permissive dev policies.

Notes
- For production, replace permissive dev policies with stricter ones tied to auth.uid().
- You can upsert a row after signup/login:
  insert into public.profiles (id, display_name) values ('<auth_user_id>', 'Your Name')
  on conflict (id) do update set display_name=excluded.display_name, updated_at=now();

Backend usage
- GET /users/me resolves the current user via the Authorization Bearer token, and reads public.profiles.display_name by id.
- If no profile row exists, it falls back to user_metadata or 'Anonymous'.
