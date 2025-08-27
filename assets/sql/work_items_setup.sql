-- Supabase SQL: Unified work_item table for tasks and bugs with project-key-based incremental IDs.
-- Execute this script in Supabase SQL Editor.
-- Prerequisite: public.projects must exist and contain a unique project_key (see assets/sql/projects_setup.sql).
--
-- This script creates:
-- - public.work_item (id integer, project_id uuid, item_key text generated, item_type text, title, description, status, priority, created_at)
-- - item_key generated as <PROJECT_KEY>-<id>, where <id> is the per-project incremental number
-- - RLS with permissive development policies
-- - Function + trigger to assign incremental id on insert per project across all item types

create extension if not exists pgcrypto;

-- Drop existing trigger (idempotent for re-runs in development)
do $$
begin
  if exists (
    select 1 from information_schema.triggers
    where event_object_schema = 'public'
      and event_object_table = 'work_item'
      and trigger_name = 'work_item_assign_incremental_id'
  ) then
    drop trigger work_item_assign_incremental_id on public.work_item;
  end if;
exception when undefined_table then
  null;
end $$;

-- Drop function if it exists
drop function if exists public.fn_work_item_assign_incremental_id cascade;

-- Create unified table
create table if not exists public.work_item (
  id integer not null,
  project_id uuid not null references public.projects(id) on delete cascade,
  item_key text generated always as (
    (select p.project_key from public.projects p where p.id = project_id)::text || '-' || id::text
  ) stored,
  item_type text not null check (item_type in ('task','bug')),
  title varchar(200) not null,
  description text null,
  status varchar(40) not null default 'open',
  priority varchar(20) null,
  created_at timestamp with time zone not null default now(),
  constraint work_item_pk primary key (project_id, id),
  constraint work_item_item_key_unique unique (item_key)
);

-- Indexes
create index if not exists idx_work_item_project on public.work_item (project_id);
create index if not exists idx_work_item_item_type on public.work_item (item_type);
create index if not exists idx_work_item_created_at on public.work_item (created_at desc);

-- Enable RLS
alter table public.work_item enable row level security;

-- Dev RLS policies (permissive)
do $$
begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='work_item' and polname='Allow select for all (dev)') then
    create policy "Allow select for all (dev)" on public.work_item for select using (true);
  end if;
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='work_item' and polname='Allow insert for all (dev)') then
    create policy "Allow insert for all (dev)" on public.work_item for insert with check (true);
  end if;
end $$;

-- Function to assign the next incremental id within a project
create or replace function public.fn_work_item_assign_incremental_id()
returns trigger
language plpgsql
as $$
declare
  next_id integer;
begin
  if NEW.id is null or NEW.id <= 0 then
    select coalesce(max(w.id), 0) + 1
      into next_id
      from public.work_item w
     where w.project_id = NEW.project_id;
    NEW.id := next_id;
  end if;
  return NEW;
end;
$$;

-- Trigger on insert to assign incremental id
create trigger work_item_assign_incremental_id
before insert on public.work_item
for each row
execute function public.fn_work_item_assign_incremental_id();

-- Verification snippets (optional)
-- insert into public.projects (name, project_key) values ('Kai Project','KAI') returning id;
-- insert into public.work_item (project_id, item_type, title) values ('<uuid>','task','Test Item') returning *;
-- select * from public.work_item where project_id = '<uuid>' order by id;
