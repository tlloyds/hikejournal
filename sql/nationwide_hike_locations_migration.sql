begin;

alter table public.hike_locations add column if not exists source_slug text;
alter table public.hike_locations add column if not exists state text;
alter table public.hike_locations add column if not exists region text;
alter table public.hike_locations add column if not exists county text;
alter table public.hike_locations add column if not exists manager_name text;
alter table public.hike_locations add column if not exists manager_type text;

create index if not exists hike_locations_state_lower_name_idx
    on public.hike_locations (state, lower(name));

commit;
