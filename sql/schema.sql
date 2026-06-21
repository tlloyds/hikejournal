create extension if not exists pgcrypto;

create table if not exists public.hikes (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    hike_date date not null,
    distance_miles numeric(6,2),
    location_name text,
    notes text,
    owner_subject text,
    owner_email text,
    cover_photo_id uuid,
    is_archived boolean not null default false,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.photos (
    id uuid primary key default gen_random_uuid(),
    hike_id uuid references public.hikes(id) on delete cascade,
    owner_subject text,
    owner_email text,
    storage_path text not null,
    public_url text not null,
    caption text,
    taken_at timestamptz,
    lat double precision,
    lng double precision,
    width integer,
    height integer,
    file_size integer,
    content_type text,
    processing_status text not null default 'ready',
    exif_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.hike_collaborators (
    id uuid primary key default gen_random_uuid(),
    hike_id uuid not null references public.hikes(id) on delete cascade,
    collaborator_email text not null,
    created_at timestamptz not null default timezone('utc', now())
);

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

create table if not exists public.species_observations (
    id uuid primary key default gen_random_uuid(),
    hike_id uuid references public.hikes(id) on delete cascade,
    owner_subject text,
    owner_email text,
    photo_id uuid not null references public.photos(id) on delete cascade,
    taxon_id bigint,
    common_name text,
    scientific_name text,
    preferred_common_name text,
    english_common_name text,
    rank text,
    iconic_taxon_name text,
    wikipedia_url text,
    wikipedia_summary text,
    alias_names jsonb not null default '[]'::jsonb,
    confidence numeric(6,4),
    is_primary boolean not null default false,
    status text not null default 'pending' check (status in ('pending', 'confirmed', 'rejected')),
    inat_observation_id bigint,
    inat_observation_url text,
    inat_posted_at timestamptz,
    inat_photo_attached boolean,
    source text not null,
    raw_response_json jsonb not null default '{}'::jsonb,
    identified_at timestamptz not null default timezone('utc', now())
);

alter table public.species_observations add column if not exists preferred_common_name text;
alter table public.species_observations add column if not exists english_common_name text;
alter table public.species_observations add column if not exists rank text;
alter table public.species_observations add column if not exists iconic_taxon_name text;
alter table public.species_observations add column if not exists wikipedia_url text;
alter table public.species_observations add column if not exists wikipedia_summary text;
alter table public.species_observations add column if not exists alias_names jsonb not null default '[]'::jsonb;
alter table public.species_observations add column if not exists is_primary boolean not null default false;
alter table public.species_observations add column if not exists owner_subject text;
alter table public.species_observations add column if not exists owner_email text;
alter table public.species_observations add column if not exists inat_observation_id bigint;
alter table public.species_observations add column if not exists inat_observation_url text;
alter table public.species_observations add column if not exists inat_posted_at timestamptz;
alter table public.species_observations add column if not exists inat_photo_attached boolean;
alter table public.photos add column if not exists owner_subject text;
alter table public.photos add column if not exists owner_email text;
alter table public.photos alter column hike_id drop not null;
alter table public.species_observations alter column hike_id drop not null;
update public.species_observations set is_primary = true where is_primary = false and id in (
    select id from (
        select distinct on (photo_id) id
        from public.species_observations
        order by photo_id, identified_at desc
    ) ranked
);
alter table public.species_observations
drop constraint if exists species_observations_photo_id_key;
alter table public.hikes add column if not exists cover_photo_id uuid;
alter table public.hike_route_imports add column if not exists source_type text not null default 'mapmyrun_tcx';
alter table public.hike_route_imports add column if not exists source_file_name text;
alter table public.hike_route_imports add column if not exists source_storage_path text;
alter table public.hike_route_imports add column if not exists source_public_url text;
alter table public.hike_route_imports add column if not exists started_at timestamptz;
alter table public.hike_route_imports add column if not exists distance_miles numeric(7,3);
alter table public.hike_route_imports add column if not exists duration_seconds integer;
alter table public.hike_route_imports add column if not exists track_point_count integer;
alter table public.hike_route_imports add column if not exists start_lat double precision;
alter table public.hike_route_imports add column if not exists start_lng double precision;
alter table public.hike_route_imports add column if not exists end_lat double precision;
alter table public.hike_route_imports add column if not exists end_lng double precision;
alter table public.hike_route_imports add column if not exists track_geojson jsonb not null default '{}'::jsonb;
alter table public.hike_route_imports add column if not exists updated_at timestamptz not null default timezone('utc', now());
alter table public.hike_locations add column if not exists location_type text;
alter table public.hike_locations add column if not exists source text;
alter table public.hike_locations add column if not exists source_url text;
alter table public.hike_locations add column if not exists lat double precision;
alter table public.hike_locations add column if not exists lng double precision;
alter table public.hike_locations add column if not exists aliases jsonb not null default '[]'::jsonb;
alter table public.hikes drop constraint if exists hikes_cover_photo_id_fkey;
alter table public.hikes
add constraint hikes_cover_photo_id_fkey
foreign key (cover_photo_id) references public.photos(id) on delete set null;
create index if not exists species_photo_id_idx on public.species_observations (photo_id);
create unique index if not exists species_primary_per_photo_idx
on public.species_observations (photo_id)
where is_primary = true;

create or replace function public.touch_updated_at()
returns trigger as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$ language plpgsql;


drop trigger if exists hikes_touch_updated_at on public.hikes;
create trigger hikes_touch_updated_at
before update on public.hikes
for each row execute procedure public.touch_updated_at();

drop trigger if exists hike_route_imports_touch_updated_at on public.hike_route_imports;
create trigger hike_route_imports_touch_updated_at
before update on public.hike_route_imports
for each row execute procedure public.touch_updated_at();

create index if not exists hikes_date_idx on public.hikes (hike_date desc);
create index if not exists hikes_owner_subject_idx on public.hikes (owner_subject);
create index if not exists hikes_owner_email_idx on public.hikes (owner_email);
create index if not exists hikes_cover_photo_id_idx on public.hikes (cover_photo_id);
create index if not exists hike_route_imports_hike_id_idx on public.hike_route_imports (hike_id);
create index if not exists photos_hike_id_idx on public.photos (hike_id);
create index if not exists photos_owner_subject_idx on public.photos (owner_subject);
create index if not exists photos_owner_email_idx on public.photos (owner_email);
create index if not exists photos_geo_idx on public.photos (lat, lng);
create index if not exists species_hike_id_idx on public.species_observations (hike_id);
create index if not exists species_owner_subject_idx on public.species_observations (owner_subject);
create index if not exists species_owner_email_idx on public.species_observations (owner_email);
create index if not exists species_status_idx on public.species_observations (status);
create index if not exists species_inat_observation_id_idx on public.species_observations (inat_observation_id);
create index if not exists hike_collaborators_hike_id_idx on public.hike_collaborators (hike_id);
create unique index if not exists hike_collaborators_unique_email_idx on public.hike_collaborators (hike_id, lower(collaborator_email));
create index if not exists hike_locations_lower_name_idx on public.hike_locations (lower(name));
create index if not exists hike_location_tags_location_id_idx on public.hike_location_tags (location_id);

alter table public.hikes enable row level security;
alter table public.photos enable row level security;
alter table public.species_observations enable row level security;
alter table public.hike_collaborators enable row level security;
alter table public.hike_route_imports enable row level security;
alter table public.hike_locations enable row level security;
alter table public.hike_location_tags enable row level security;

drop policy if exists "Open single-user access for hikes" on public.hikes;
create policy "Open single-user access for hikes"
on public.hikes
for all
using (true)
with check (true);

drop policy if exists "Open single-user access for photos" on public.photos;
create policy "Open single-user access for photos"
on public.photos
for all
using (true)
with check (true);

drop policy if exists "Open single-user access for species observations" on public.species_observations;
create policy "Open single-user access for species observations"
on public.species_observations
for all
using (true)
with check (true);

drop policy if exists "Open single-user access for hike collaborators" on public.hike_collaborators;
create policy "Open single-user access for hike collaborators"
on public.hike_collaborators
for all
using (true)
with check (true);

drop policy if exists "Open single-user access for hike route imports" on public.hike_route_imports;
create policy "Open single-user access for hike route imports"
on public.hike_route_imports
for all
using (true)
with check (true);

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

insert into storage.buckets (id, name, public)
values ('hike-journal', 'hike-journal', true)
on conflict (id) do nothing;

drop policy if exists "Public read for hike journal bucket" on storage.objects;
create policy "Public read for hike journal bucket"
on storage.objects for select
using (bucket_id = 'hike-journal');

drop policy if exists "App key can insert hike journal objects" on storage.objects;
create policy "App key can insert hike journal objects"
on storage.objects for insert
with check (bucket_id = 'hike-journal');

drop policy if exists "App key can update hike journal objects" on storage.objects;
create policy "App key can update hike journal objects"
on storage.objects for update
using (bucket_id = 'hike-journal');

drop policy if exists "App key can delete hike journal objects" on storage.objects;
create policy "App key can delete hike journal objects"
on storage.objects for delete
using (bucket_id = 'hike-journal');
