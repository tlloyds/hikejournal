create table if not exists public.hike_locations (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    slug text not null unique,
    location_type text,
    source text,
    source_url text,
    lat double precision,
    lng double precision,
    aliases jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.hike_location_tags (
    hike_id uuid not null references public.hikes(id) on delete cascade,
    location_id uuid not null references public.hike_locations(id) on delete cascade,
    is_primary boolean not null default false,
    created_at timestamptz not null default timezone('utc', now()),
    primary key (hike_id, location_id)
);

alter table public.hike_locations add column if not exists location_type text;
alter table public.hike_locations add column if not exists source text;
alter table public.hike_locations add column if not exists source_url text;
alter table public.hike_locations add column if not exists lat double precision;
alter table public.hike_locations add column if not exists lng double precision;
alter table public.hike_locations add column if not exists aliases jsonb not null default '[]'::jsonb;

create index if not exists hike_locations_lower_name_idx on public.hike_locations (lower(name));
create index if not exists hike_location_tags_location_id_idx on public.hike_location_tags (location_id);

alter table public.hike_locations enable row level security;
alter table public.hike_location_tags enable row level security;

drop policy if exists "Open single-user access for hike locations" on public.hike_locations;
create policy "Open single-user access for hike locations"
on public.hike_locations
for all
using (true)
with check (true);

drop policy if exists "Open single-user access for hike location tags" on public.hike_location_tags;
create policy "Open single-user access for hike location tags"
on public.hike_location_tags
for all
using (true)
with check (true);
