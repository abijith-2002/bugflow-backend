-- Supabase SQL: Projects table and permissive development RLS policies
-- Execute this script in Supabase SQL Editor (SQL -> New query) and Run.

-- 1) Ensure pgcrypto for gen_random_uuid()
create extension if not exists pgcrypto;

-- 2) Create projects table (id, name, description, created_at)
create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text null,
  created_at timestamptz not null default now()
);

-- 3) Enable RLS
alter table public.projects enable row level security;

-- 4) Development policies (permissive). Adjust for prod later.
-- Drop existing to avoid duplicates if re-running
drop policy if exists "Allow select for all (dev)" on public.projects;
drop policy if exists "Allow insert for all (dev)" on public.projects;

-- Re-create
create policy "Allow select for all (dev)"
  on public.projects
  for select
  using (true);

create policy "Allow insert for all (dev)"
  on public.projects
  for insert
  with check (true);

-- Optional: Verify
-- select table_name from information_schema.tables where table_schema='public' and table_name='projects';
-- select * from public.projects limit 1;
