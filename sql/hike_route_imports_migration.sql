create table if not exists public.hike_route_imports (
    id uuid primary key default gen_random_uuid(),
    hike_id uuid not null references public.hikes(id) on delete cascade,
    source_type text not null default 'mapmyrun_tcx',
    source_file_name text,
    source_storage_path text,
    source_public_url text,
    started_at timestamptz,
    distance_miles numeric(7,3),
    duration_seconds integer,
    track_point_count integer,
    start_lat double precision,
    start_lng double precision,
    end_lat double precision,
    end_lng double precision,
    track_geojson jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (hike_id)
);

alter table public.hike_route_imports enable row level security;

create index if not exists hike_route_imports_hike_id_idx on public.hike_route_imports (hike_id);

create or replace function public.touch_updated_at()
returns trigger as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$ language plpgsql;

drop trigger if exists hike_route_imports_touch_updated_at on public.hike_route_imports;
create trigger hike_route_imports_touch_updated_at
before update on public.hike_route_imports
for each row execute procedure public.touch_updated_at();

drop policy if exists "Open single-user access for hike route imports" on public.hike_route_imports;
create policy "Open single-user access for hike route imports"
on public.hike_route_imports
for all
using (true)
with check (true);
