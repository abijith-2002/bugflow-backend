-- Supabase SQL: Minimal tasks and bugs tables required to support counts in /projects.
-- Execute this script in Supabase SQL Editor if you want the backend to include 'tasks' and 'bugs' counts.

create extension if not exists pgcrypto;

-- tasks table
create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  created_at timestamp with time zone not null default now()
);

-- bugs table
create table if not exists public.bugs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  created_at timestamp with time zone not null default now()
);

-- Enable RLS and permissive select for development
alter table public.tasks enable row level security;
alter table public.bugs enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where polname = 'Allow select for all (dev)' and tablename = 'tasks') then
    create policy "Allow select for all (dev)" on public.tasks for select using (true);
  end if;
  if not exists (select 1 from pg_policies where polname = 'Allow insert for all (dev)' and tablename = 'tasks') then
    create policy "Allow insert for all (dev)" on public.tasks for insert with check (true);
  end if;
  if not exists (select 1 from pg_policies where polname = 'Allow select for all (dev)' and tablename = 'bugs') then
    create policy "Allow select for all (dev)" on public.bugs for select using (true);
  end if;
  if not exists (select 1 from pg_policies where polname = 'Allow insert for all (dev)' and tablename = 'bugs') then
    create policy "Allow insert for all (dev)" on public.bugs for insert with check (true);
  end if;
end $$;
