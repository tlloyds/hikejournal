create extension if not exists pgcrypto;

create table if not exists public.app_users (
    id uuid primary key default gen_random_uuid(),
    google_subject text not null unique,
    email text not null,
    display_name text not null default '',
    picture_url text,
    created_at timestamptz not null default now(),
    last_signed_in_at timestamptz not null default now(),
    deletion_requested_at timestamptz
);

create table if not exists public.mobile_user_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.app_users(id) on delete cascade,
    device_id text not null,
    refresh_token_hash text not null unique,
    created_at timestamptz not null default now(),
    last_used_at timestamptz not null default now(),
    expires_at timestamptz not null,
    revoked_at timestamptz
);

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
    source_slug text,
    state text,
    region text,
    county text,
    manager_name text,
    manager_type text,
    lat double precision,
    lng double precision,
    aliases jsonb not null default '[]'::jsonb,
    owner_subject text,
    owner_email text,
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
    species_taxon_id bigint,
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
    identified_at timestamptz not null default timezone('utc', now()),
    observed_on date,
    occurrence_precision text not null default 'unknown' check (occurrence_precision in ('exact', 'day', 'estimated', 'unknown')),
    identification_confidence text not null default 'tentative' check (identification_confidence in ('tentative', 'likely', 'confident', 'externally_confirmed')),
    identification_provenance text not null default 'legacy_import'
);

create table if not exists public.identification_events (
    id uuid primary key default gen_random_uuid(),
    observation_id uuid not null references public.species_observations(id) on delete cascade,
    owner_subject text,
    owner_email text,
    taxon_id bigint,
    species_taxon_id bigint,
    scientific_name text,
    common_name text,
    source text not null check (source in ('user', 'inat_computer_vision', 'inat_lookup', 'inat_community', 'external_expert', 'imported_record', 'legacy_import', 'migration')),
    confidence text not null check (confidence in ('tentative', 'likely', 'confident', 'externally_confirmed')),
    source_reference_id text,
    actor text,
    note text,
    became_current boolean not null default true,
    created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.observation_annotations (
    id uuid primary key default gen_random_uuid(),
    observation_id uuid not null references public.species_observations(id) on delete cascade,
    owner_subject text,
    owner_email text,
    category text not null,
    code text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (observation_id, category, code)
);

create table if not exists public.field_marks (
    id uuid primary key,
    hike_id uuid not null references public.hikes(id) on delete cascade,
    recording_session_id uuid,
    owner_subject text,
    owner_email text,
    marked_at timestamptz not null,
    lat double precision not null check (lat between -90 and 90),
    lng double precision not null check (lng between -180 and 180),
    accuracy_meters double precision check (accuracy_meters is null or accuracy_meters >= 0),
    mark_type text not null check (mark_type in ('wildlife', 'plant', 'trail_condition', 'water', 'campsite', 'hazard', 'note')),
    note text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.hike_weather_snapshots (
    id uuid primary key default gen_random_uuid(),
    hike_id uuid not null references public.hikes(id) on delete cascade,
    owner_subject text,
    owner_email text,
    provider text not null,
    provider_dataset text,
    algorithm_version text not null,
    anchor_lat double precision not null check (anchor_lat between -90 and 90),
    anchor_lng double precision not null check (anchor_lng between -180 and 180),
    interval_started_at timestamptz not null,
    interval_ended_at timestamptz not null,
    temperature_min_c double precision,
    temperature_mean_c double precision,
    temperature_max_c double precision,
    apparent_temperature_mean_c double precision,
    precipitation_total_mm double precision,
    relative_humidity_mean_percent double precision,
    cloud_cover_mean_percent double precision,
    wind_speed_mean_kph double precision,
    condition_label text,
    raw_response_json jsonb not null default '{}'::jsonb,
    enriched_at timestamptz not null default timezone('utc', now()),
    unique (hike_id, provider, algorithm_version)
);

create table if not exists public.species_discovery_snapshots (
    cache_key text primary key,
    algorithm_version text not null,
    lat double precision not null,
    lng double precision not null,
    radius_km integer not null check (radius_km in (5, 10, 25)),
    months smallint[] not null,
    iconic_taxon text,
    observed_after date not null,
    taxa jsonb not null default '[]'::jsonb,
    fetched_at timestamptz not null,
    expires_at timestamptz not null,
    created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.species_quests (
    id uuid primary key default gen_random_uuid(),
    owner_subject text,
    owner_email text,
    location_id uuid references public.hike_locations(id) on delete set null,
    linked_hike_id uuid references public.hikes(id) on delete set null,
    title text not null,
    status text not null default 'active' check (status in ('active', 'archived')),
    area_name text not null,
    lat double precision not null,
    lng double precision not null,
    radius_km integer not null check (radius_km in (5, 10, 25)),
    target_date date not null,
    months smallint[] not null,
    iconic_taxon text,
    algorithm_version text not null,
    target_count integer not null default 0 check (target_count between 0 and 100),
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.species_quest_taxa (
    quest_id uuid not null references public.species_quests(id) on delete cascade,
    taxon_id bigint not null,
    common_name text not null,
    scientific_name text,
    rank text not null default 'species',
    iconic_taxon_name text,
    observation_count integer not null default 0,
    nearby_rank integer not null,
    frequency_band text not null,
    reference_photo_url text,
    reference_photo_attribution text,
    reference_photo_license text,
    wikipedia_url text,
    wikipedia_summary text,
    focus_order smallint check (focus_order between 1 and 10),
    created_at timestamptz not null default timezone('utc', now()),
    primary key (quest_id, taxon_id)
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
alter table public.species_observations add column if not exists species_taxon_id bigint;
alter table public.species_observations add column if not exists observed_on date;
alter table public.species_observations add column if not exists occurrence_precision text not null default 'unknown';
alter table public.species_observations add column if not exists identification_confidence text not null default 'tentative';
alter table public.species_observations add column if not exists identification_provenance text not null default 'legacy_import';
update public.species_observations
set species_taxon_id = taxon_id
where species_taxon_id is null
  and taxon_id is not null
  and (
      lower(coalesce(rank, '')) = 'species'
      or (
          coalesce(trim(rank), '') = ''
          and trim(coalesce(scientific_name, '')) ~
              '^[A-Za-z][A-Za-z.-]+[[:space:]]+[A-Za-z][A-Za-z.-]+$'
      )
  );
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
alter table public.hike_locations add column if not exists source_slug text;
alter table public.hike_locations add column if not exists state text;
alter table public.hike_locations add column if not exists region text;
alter table public.hike_locations add column if not exists county text;
alter table public.hike_locations add column if not exists manager_name text;
alter table public.hike_locations add column if not exists manager_type text;
alter table public.hike_locations add column if not exists lat double precision;
alter table public.hike_locations add column if not exists lng double precision;
alter table public.hike_locations add column if not exists aliases jsonb not null default '[]'::jsonb;
alter table public.hike_locations add column if not exists owner_subject text;
alter table public.hike_locations add column if not exists owner_email text;
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

drop trigger if exists species_quests_touch_updated_at on public.species_quests;
create trigger species_quests_touch_updated_at
before update on public.species_quests
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
create index if not exists species_observations_species_taxon_id_idx
on public.species_observations (species_taxon_id)
where status = 'confirmed';
create index if not exists species_observations_observed_on_idx on public.species_observations (observed_on desc) where status = 'confirmed';
create index if not exists identification_events_observation_created_idx on public.identification_events (observation_id, created_at desc);
create index if not exists observation_annotations_observation_idx on public.observation_annotations (observation_id, category);
create index if not exists field_marks_hike_marked_idx on public.field_marks (hike_id, marked_at);
create index if not exists hike_weather_snapshots_hike_idx on public.hike_weather_snapshots (hike_id, enriched_at desc);
create unique index if not exists species_quest_taxa_focus_order_idx
on public.species_quest_taxa (quest_id, focus_order)
where focus_order is not null;
create index if not exists species_quests_owner_subject_idx on public.species_quests (owner_subject);
create index if not exists species_quests_owner_email_idx on public.species_quests (owner_email);
create index if not exists species_quests_status_idx on public.species_quests (status);
create index if not exists species_quest_taxa_taxon_id_idx on public.species_quest_taxa (taxon_id);
create index if not exists species_discovery_snapshots_expires_at_idx
on public.species_discovery_snapshots (expires_at);
create index if not exists hike_collaborators_hike_id_idx on public.hike_collaborators (hike_id);
create unique index if not exists hike_collaborators_unique_email_idx on public.hike_collaborators (hike_id, lower(collaborator_email));
create index if not exists hike_locations_lower_name_idx on public.hike_locations (lower(name));
create index if not exists hike_locations_state_lower_name_idx on public.hike_locations (state, lower(name));
create index if not exists hike_locations_owner_subject_idx on public.hike_locations (owner_subject);
create unique index if not exists app_users_lower_email_idx on public.app_users (lower(email));
create index if not exists mobile_user_sessions_user_idx on public.mobile_user_sessions (user_id, revoked_at, expires_at);
create index if not exists hike_location_tags_location_id_idx on public.hike_location_tags (location_id);

alter table public.hikes enable row level security;
alter table public.photos enable row level security;
alter table public.species_observations enable row level security;
alter table public.hike_collaborators enable row level security;
alter table public.hike_route_imports enable row level security;
alter table public.hike_locations enable row level security;
alter table public.hike_location_tags enable row level security;
alter table public.species_discovery_snapshots enable row level security;
alter table public.species_quests enable row level security;
alter table public.species_quest_taxa enable row level security;
alter table public.identification_events enable row level security;
alter table public.observation_annotations enable row level security;
alter table public.field_marks enable row level security;
alter table public.hike_weather_snapshots enable row level security;
alter table public.app_users enable row level security;
alter table public.mobile_user_sessions enable row level security;
alter table public.hikes force row level security;
alter table public.photos force row level security;
alter table public.species_observations force row level security;
alter table public.hike_collaborators force row level security;
alter table public.hike_route_imports force row level security;
alter table public.hike_locations force row level security;
alter table public.hike_location_tags force row level security;
alter table public.species_discovery_snapshots force row level security;
alter table public.species_quests force row level security;
alter table public.species_quest_taxa force row level security;
alter table public.identification_events force row level security;
alter table public.observation_annotations force row level security;
alter table public.field_marks force row level security;
alter table public.hike_weather_snapshots force row level security;
alter table public.app_users force row level security;
alter table public.mobile_user_sessions force row level security;

drop policy if exists "Open single-user access for hikes" on public.hikes;
drop policy if exists "Open single-user access for photos" on public.photos;
drop policy if exists "Open single-user access for species observations" on public.species_observations;
drop policy if exists "Open single-user access for hike collaborators" on public.hike_collaborators;
drop policy if exists "Open single-user access for hike route imports" on public.hike_route_imports;
drop policy if exists "Open single-user access for hike locations" on public.hike_locations;
drop policy if exists "Open single-user access for hike location tags" on public.hike_location_tags;

revoke all privileges on table public.hikes from anon, authenticated;
revoke all privileges on table public.photos from anon, authenticated;
revoke all privileges on table public.species_observations from anon, authenticated;
revoke all privileges on table public.hike_collaborators from anon, authenticated;
revoke all privileges on table public.hike_route_imports from anon, authenticated;
revoke all privileges on table public.hike_locations from anon, authenticated;
revoke all privileges on table public.hike_location_tags from anon, authenticated;
revoke all privileges on table public.species_discovery_snapshots from anon, authenticated;
revoke all privileges on table public.species_quests from anon, authenticated;
revoke all privileges on table public.species_quest_taxa from anon, authenticated;
revoke all privileges on table public.identification_events from anon, authenticated;
revoke all privileges on table public.observation_annotations from anon, authenticated;
revoke all privileges on table public.field_marks from anon, authenticated;
revoke all privileges on table public.hike_weather_snapshots from anon, authenticated;

insert into storage.buckets (id, name, public)
values ('hike-journal', 'hike-journal', true)
on conflict (id) do nothing;

drop policy if exists "Public read for hike journal bucket" on storage.objects;
create policy "Public read for hike journal bucket"
on storage.objects for select
using (bucket_id = 'hike-journal');

drop policy if exists "App key can insert hike journal objects" on storage.objects;
drop policy if exists "App key can update hike journal objects" on storage.objects;
drop policy if exists "App key can delete hike journal objects" on storage.objects;

revoke execute on function public.touch_updated_at() from public, anon, authenticated;
grant execute on function public.touch_updated_at() to service_role;

alter default privileges in schema public
revoke all privileges on tables from anon, authenticated;
alter default privileges in schema public
revoke execute on functions from public, anon, authenticated;
alter default privileges in schema public
grant all privileges on tables to service_role;
alter default privileges in schema public
grant execute on functions to service_role;

-- Durable state for mobile identification and iNaturalist publishing batches.
create table if not exists public.mobile_api_jobs (
    id uuid primary key default gen_random_uuid(),
    job_type text not null check (char_length(job_type) between 1 and 80),
    owner_scope text not null default 'single-owner'
        check (char_length(owner_scope) between 1 and 80),
    owner_key text not null check (char_length(owner_key) = 64),
    client_request_id text,
    state text not null default 'queued'
        check (state in ('queued', 'running', 'completed', 'failed', 'cancelled')),
    payload jsonb not null default '{}'::jsonb,
    request_payload jsonb not null default '{}'::jsonb,
    request_fingerprint text,
    attempt_count integer not null default 0 check (attempt_count >= 0),
    max_attempts integer not null default 3 check (max_attempts between 1 and 20),
    next_attempt_at timestamptz,
    lease_owner text,
    lease_expires_at timestamptz,
    last_error text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    completed_at timestamptz,
    check (client_request_id is null or char_length(client_request_id) between 1 and 64),
    check (request_fingerprint is null or char_length(request_fingerprint) = 64)
);

alter table public.mobile_api_jobs
add column if not exists request_fingerprint text;

create unique index if not exists mobile_api_jobs_request_idempotency_idx
on public.mobile_api_jobs (job_type, owner_scope, owner_key, client_request_id)
where client_request_id is not null;

create index if not exists mobile_api_jobs_recovery_idx
on public.mobile_api_jobs (state, next_attempt_at, lease_expires_at, created_at)
where state in ('queued', 'running', 'failed');

drop function if exists public.update_mobile_api_job(uuid, jsonb);

create or replace function public.update_mobile_api_job(
    p_job_id uuid,
    p_payload_updates jsonb,
    p_expected_lease_owner text default null,
    p_lease_seconds integer default 1800
) returns setof public.mobile_api_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
    if p_payload_updates is null or jsonb_typeof(p_payload_updates) <> 'object' then
        raise exception 'Job payload updates must be a JSON object.';
    end if;

    return query
    update public.mobile_api_jobs as job
    set payload = job.payload || p_payload_updates,
        state = coalesce(nullif(p_payload_updates->>'state', ''), job.state),
        last_error = case
            when p_payload_updates ? 'error'
                then nullif(p_payload_updates->>'error', '')
            else job.last_error
        end,
        lease_owner = case
            when p_payload_updates ? 'state'
                and coalesce(nullif(p_payload_updates->>'state', ''), job.state)
                in ('completed', 'failed', 'cancelled') then null
            else job.lease_owner
        end,
        lease_expires_at = case
            when p_payload_updates ? 'state'
                and coalesce(nullif(p_payload_updates->>'state', ''), job.state)
                in ('completed', 'failed', 'cancelled') then null
            when p_expected_lease_owner is not null then
                timezone('utc', now())
                + make_interval(secs => greatest(1, least(coalesce(p_lease_seconds, 1800), 3600)))
            else job.lease_expires_at
        end,
        next_attempt_at = case
            when p_payload_updates ? 'state'
                and coalesce(nullif(p_payload_updates->>'state', ''), job.state)
                in ('completed', 'failed', 'cancelled')
                then null
            else job.next_attempt_at
        end,
        completed_at = case
            when p_payload_updates ? 'state'
                and coalesce(nullif(p_payload_updates->>'state', ''), job.state)
                in ('completed', 'failed', 'cancelled')
                then coalesce(job.completed_at, timezone('utc', now()))
            else job.completed_at
        end,
        updated_at = timezone('utc', now())
    where job.id = p_job_id
      and (
          p_expected_lease_owner is null
          or (
              job.state = 'running'
              and job.lease_owner = p_expected_lease_owner
          )
      )
    returning job.*;
end;
$$;

create or replace function public.claim_mobile_api_job(
    p_job_id uuid,
    p_lease_owner text,
    p_lease_seconds integer default 300
) returns setof public.mobile_api_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
    if coalesce(trim(p_lease_owner), '') = '' then
        raise exception 'A lease owner is required.';
    end if;

    return query
    update public.mobile_api_jobs as job
    set state = 'running',
        payload = jsonb_set(job.payload, '{state}', to_jsonb('running'::text), true),
        attempt_count = job.attempt_count + 1,
        next_attempt_at = null,
        lease_owner = p_lease_owner,
        lease_expires_at = timezone('utc', now())
            + make_interval(secs => greatest(1, least(coalesce(p_lease_seconds, 300), 3600))),
        updated_at = timezone('utc', now())
    where job.id = p_job_id
      and job.attempt_count < job.max_attempts
      and (
          job.state = 'queued'
          or (
              job.state = 'failed'
              and job.next_attempt_at is not null
              and job.next_attempt_at <= timezone('utc', now())
          )
          or (
              job.state = 'running'
              and job.lease_expires_at is not null
              and job.lease_expires_at <= timezone('utc', now())
          )
      )
    returning job.*;
end;
$$;

create or replace function public.fail_expired_mobile_api_job(
    p_job_id uuid,
    p_expected_lease_owner text,
    p_error text
) returns setof public.mobile_api_jobs
language plpgsql
security definer
set search_path = public
as $$
declare
    failure_message text := coalesce(
        nullif(p_error, ''),
        'The background worker stopped after its lease expired.'
    );
begin
    if coalesce(trim(p_expected_lease_owner), '') = '' then
        raise exception 'An expected lease owner is required.';
    end if;

    return query
    update public.mobile_api_jobs as job
    set payload = job.payload || jsonb_build_object(
            'state', 'failed',
            'error', failure_message
        ),
        state = 'failed',
        last_error = failure_message,
        lease_owner = null,
        lease_expires_at = null,
        next_attempt_at = null,
        completed_at = coalesce(job.completed_at, timezone('utc', now())),
        updated_at = timezone('utc', now())
    where job.id = p_job_id
      and job.state = 'running'
      and job.lease_owner = p_expected_lease_owner
      and job.lease_expires_at is not null
      and job.lease_expires_at <= timezone('utc', now())
    returning job.*;
end;
$$;

alter table public.mobile_api_jobs enable row level security;
alter table public.mobile_api_jobs force row level security;
revoke all privileges on table public.mobile_api_jobs from anon, authenticated;
grant all privileges on table public.mobile_api_jobs to service_role;
revoke execute on function public.update_mobile_api_job(uuid, jsonb, text, integer)
from public, anon, authenticated;
grant execute on function public.update_mobile_api_job(uuid, jsonb, text, integer)
to service_role;
revoke execute on function public.claim_mobile_api_job(uuid, text, integer)
from public, anon, authenticated;
grant execute on function public.claim_mobile_api_job(uuid, text, integer)
to service_role;
revoke execute on function public.fail_expired_mobile_api_job(uuid, text, text)
from public, anon, authenticated;
grant execute on function public.fail_expired_mobile_api_job(uuid, text, text)
to service_role;
