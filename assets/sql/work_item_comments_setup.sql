-- Supabase SQL: Comments for unified work items
-- Execute this script in Supabase SQL Editor after setting up projects and work_item tables.

create extension if not exists pgcrypto;

-- Drop triggers/functions for dev re-runs
do $$
begin
  if exists (
    select 1 from information_schema.triggers
    where event_object_schema = 'public'
      and event_object_table = 'work_item_comment'
      and trigger_name = 'work_item_comment_assign_incremental_id'
  ) then
    drop trigger work_item_comment_assign_incremental_id on public.work_item_comment;
  end if;
exception when undefined_table then
  null;
end $$;

drop function if exists public.fn_work_item_comment_assign_incremental_id cascade;

-- Table to store comments per work item
create table if not exists public.work_item_comment (
  project_id uuid not null,
  item_id integer not null,
  id integer not null, -- increments per (project_id, item_id)
  body text not null,
  author_id uuid null, -- optional: reference to auth.users.id (cannot FK across schemas by default)
  created_at timestamp with time zone not null default now(),
  constraint work_item_comment_pk primary key (project_id, item_id, id),
  constraint work_item_comment_work_item_fk foreign key (project_id, item_id)
    references public.work_item (project_id, id)
    on delete cascade
);

-- Helpful index for listing comments by time
create index if not exists idx_work_item_comment_created_at on public.work_item_comment (project_id, item_id, created_at);

-- RLS
alter table public.work_item_comment enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='work_item_comment' and policyname='Allow select for all (dev)'
  ) then
    create policy "Allow select for all (dev)" on public.work_item_comment for select using (true);
  end if;
  if not exists (
    select 1 from pg_policies where schemaname='public' and tablename='work_item_comment' and policyname='Allow insert for all (dev)'
  ) then
    create policy "Allow insert for all (dev)" on public.work_item_comment for insert with check (true);
  end if;
end $$;

-- Function to assign next comment id per (project_id, item_id)
create or replace function public.fn_work_item_comment_assign_incremental_id()
returns trigger
language plpgsql
as $$
declare
  next_id integer;
begin
  if NEW.id is null or NEW.id <= 0 then
    select coalesce(max(c.id), 0) + 1
      into next_id
      from public.work_item_comment c
     where c.project_id = NEW.project_id
       and c.item_id = NEW.item_id;
    NEW.id := next_id;
  end if;
  return NEW;
end;
$$;

-- Trigger
create trigger work_item_comment_assign_incremental_id
before insert on public.work_item_comment
for each row
execute function public.fn_work_item_comment_assign_incremental_id();

-- Verification (optional):
-- insert into public.work_item_comment (project_id, item_id, body) values ('<proj_uuid>', 1, 'First comment') returning *;
-- select * from public.work_item_comment where project_id = '<proj_uuid>' and item_id = 1 order by id;
