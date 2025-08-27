-- Unified Work Item table with per-project incremental IDs and automatic item_key generation (via triggers)
-- Save-only migration: do not execute from this repository tooling.
-- Execute in your Supabase project's SQL Editor manually when ready.

-- Prerequisites:
-- - public.projects table exists with a unique project_key column (see assets/sql/projects_setup.sql).
-- - pgcrypto extension available for gen_random_uuid() used in projects (not required here but safe to ensure).
create extension if not exists pgcrypto;

-- Idempotent cleanup for development re-runs (safe no-ops if first run)

-- Drop triggers if they exist (ignore if table doesn't exist yet)
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
  if exists (
    select 1 from information_schema.triggers
    where event_object_schema = 'public'
      and event_object_table = 'work_item'
      and trigger_name = 'work_item_set_item_key'
  ) then
    drop trigger work_item_set_item_key on public.work_item;
  end if;
exception when undefined_table then
  null; -- table does not exist yet
end $$;

-- Drop functions if they exist
drop function if exists public.fn_work_item_assign_incremental_id cascade;
drop function if exists public.fn_work_item_set_item_key cascade;

-- Create unified table
-- Notes:
-- - id is an integer that increments per project (not a global sequence).
-- - item_key is a plain text column, computed/maintained by trigger as <PROJECT_KEY>-<id> (e.g., KAI-1).
-- - Composite primary key: (project_id, id).
-- - Unique constraint on item_key for global uniqueness.
create table if not exists public.work_item (
  id integer not null,
  project_id uuid not null references public.projects(id) on delete cascade,
  item_key text null, -- set by trigger
  item_type text not null check (item_type in ('task','bug')),
  title varchar(200) not null,
  description text null,
  status varchar(40) not null default 'open',
  priority varchar(20) null,
  created_at timestamp with time zone not null default now(),
  constraint work_item_pk primary key (project_id, id),
  constraint work_item_item_key_unique unique (item_key)
);

-- Helpful indexes
create index if not exists idx_work_item_project on public.work_item (project_id);
create index if not exists idx_work_item_item_type on public.work_item (item_type);
create index if not exists idx_work_item_created_at on public.work_item (created_at desc);

-- Enable RLS (policies are environment-specific; add permissive or strict as needed)
alter table public.work_item enable row level security;

-- Optional permissive dev policies. Comment these lines out for production and replace with scoped policies.
do $$
begin
  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='work_item' and policyname='Allow select for all (dev)'
  ) then
    create policy "Allow select for all (dev)" on public.work_item for select using (true);
  end if;
  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='work_item' and policyname='Allow insert for all (dev)'
  ) then
    create policy "Allow insert for all (dev)" on public.work_item for insert with check (true);
  end if;
end $$;

-- Function: Assign the next incremental id within a project at insert time.
-- Rationale: We cannot use a plain sequence because the increment is per project.
create or replace function public.fn_work_item_assign_incremental_id()
returns trigger
language plpgsql
as $$
declare
  next_id integer;
begin
  -- Only assign if id is null or non-positive (allow explicit override for migrations if needed)
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

-- Function: Set or update item_key based on project's project_key and the per-project id.
-- Executes after id is assigned so it can use NEW.id.
create or replace function public.fn_work_item_set_item_key()
returns trigger
language plpgsql
as $$
declare
  pkey text;
begin
  -- Fetch the project key for the referenced project_id
  select project_key into pkey from public.projects where id = NEW.project_id;
  if pkey is null then
    -- Project not found; prevent insert/update to avoid dangling/invalid key
    raise exception 'Project with id % not found when computing item_key', NEW.project_id;
  end if;

  NEW.item_key := pkey || '-' || NEW.id::text;
  return NEW;
end;
$$;

-- Trigger: before insert, compute the next id per project.
create trigger work_item_assign_incremental_id
before insert on public.work_item
for each row
execute function public.fn_work_item_assign_incremental_id();

-- Trigger: before insert or update, compute/refresh item_key after id/project_id are finalized in NEW
-- Using BEFORE so NEW is writable; item_key stays consistent on id/project_id changes.
create trigger work_item_set_item_key
before insert or update of id, project_id on public.work_item
for each row
execute function public.fn_work_item_set_item_key();

-- Verification snippets (use in Supabase SQL Editor as needed):
-- -- Create a project and note the returned UUID
-- insert into public.projects (name, project_key) values ('Kai Project','KAI') returning id;
-- -- Insert work items and see id increment per project with item_key KAI-1, KAI-2, ...
-- insert into public.work_item (project_id, item_type, title) values ('<project_uuid>', 'task', 'Initial setup') returning *;
-- insert into public.work_item (project_id, item_type, title) values ('<project_uuid>', 'bug', 'Fix login issue') returning *;
-- select * from public.work_item where project_id = '<project_uuid>' order by id;
