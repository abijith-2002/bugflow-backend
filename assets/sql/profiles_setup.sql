-- Supabase SQL: Basic public.profiles table for user display names
-- Execute this script in Supabase SQL Editor. Assumes Supabase Auth is enabled.

create extension if not exists pgcrypto;

-- Create profiles table if it doesn't exist
create table if not exists public.profiles (
  id uuid primary key,                 -- matches auth.users.id
  display_name text null,              -- preferred display name
  updated_at timestamp with time zone not null default now()
);

-- Helpful index for lookups
create index if not exists idx_profiles_id on public.profiles (id);

-- Enable RLS and add permissive dev policies (tighten for production)
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

-- Optional: sync profile on signup via trigger could be done via Edge Functions or database triggers.
-- For now, frontend/backend may insert/update as needed.
