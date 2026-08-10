-- HikeJournal longitudinal natural-history foundation.
-- Safe to run once against an existing Supabase project. All changes are additive.

create extension if not exists pgcrypto;

alter table public.species_observations
add column if not exists observed_on date;

alter table public.species_observations
add column if not exists occurrence_precision text not null default 'unknown';

alter table public.species_observations
drop constraint if exists species_observations_occurrence_precision_check;
alter table public.species_observations
add constraint species_observations_occurrence_precision_check
check (occurrence_precision in ('exact', 'day', 'estimated', 'unknown'));

alter table public.species_observations
add column if not exists identification_confidence text not null default 'tentative';

alter table public.species_observations
drop constraint if exists species_observations_identification_confidence_check;
alter table public.species_observations
add constraint species_observations_identification_confidence_check
check (identification_confidence in ('tentative', 'likely', 'confident', 'externally_confirmed'));

alter table public.species_observations
add column if not exists identification_provenance text not null default 'legacy_import';

update public.species_observations as observation
set observed_on = coalesce(
        observation.observed_on,
        photo.taken_at::date,
        hike.hike_date,
        observation.identified_at::date
    ),
    occurrence_precision = case
        when observation.observed_on is not null then observation.occurrence_precision
        when photo.taken_at is not null then 'exact'
        when hike.hike_date is not null then 'day'
        else 'estimated'
    end,
    identification_confidence = case
        when observation.status = 'confirmed' and coalesce(observation.confidence, 0) >= 0.90 then 'confident'
        when observation.status = 'confirmed' then 'likely'
        else 'tentative'
    end,
    identification_provenance = case
        when observation.inat_observation_id is not null then 'inat_lookup'
        else 'legacy_import'
    end
from public.photos as photo
left join public.hikes as hike on hike.id = photo.hike_id
where photo.id = observation.photo_id;

create table if not exists public.identification_events (
    id uuid primary key default gen_random_uuid(),
    observation_id uuid not null references public.species_observations(id) on delete cascade,
    owner_subject text,
    owner_email text,
    taxon_id bigint,
    species_taxon_id bigint,
    scientific_name text,
    common_name text,
    source text not null check (
        source in (
            'user', 'inat_computer_vision', 'inat_lookup', 'inat_community',
            'external_expert', 'imported_record', 'legacy_import', 'migration'
        )
    ),
    confidence text not null check (
        confidence in ('tentative', 'likely', 'confident', 'externally_confirmed')
    ),
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
    mark_type text not null check (
        mark_type in ('wildlife', 'plant', 'trail_condition', 'water', 'campsite', 'hazard', 'note')
    ),
    note text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

-- Storage is available before a provider is configured; failed enrichment can never
-- prevent a hike from finishing.
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

create index if not exists species_observations_observed_on_idx
on public.species_observations (observed_on desc)
where status = 'confirmed';
create index if not exists identification_events_observation_created_idx
on public.identification_events (observation_id, created_at desc);
create index if not exists identification_events_owner_subject_idx
on public.identification_events (owner_subject);
create index if not exists observation_annotations_observation_idx
on public.observation_annotations (observation_id, category);
create index if not exists field_marks_hike_marked_idx
on public.field_marks (hike_id, marked_at);
create index if not exists field_marks_owner_subject_idx
on public.field_marks (owner_subject);
create index if not exists hike_weather_snapshots_hike_idx
on public.hike_weather_snapshots (hike_id, enriched_at desc);

insert into public.identification_events (
    observation_id,
    owner_subject,
    owner_email,
    taxon_id,
    species_taxon_id,
    scientific_name,
    common_name,
    source,
    confidence,
    source_reference_id,
    actor,
    note,
    became_current,
    created_at
)
select
    observation.id,
    observation.owner_subject,
    observation.owner_email,
    observation.taxon_id,
    observation.species_taxon_id,
    observation.scientific_name,
    observation.common_name,
    'legacy_import',
    observation.identification_confidence,
    observation.inat_observation_id::text,
    'HikeJournal migration',
    'Backfilled from the current confirmed identification.',
    true,
    observation.identified_at
from public.species_observations as observation
where observation.status = 'confirmed'
  and not exists (
      select 1
      from public.identification_events as event
      where event.observation_id = observation.id
  );

create or replace function public.hikejournal_normalize_identification_source(value text)
returns text
language sql
immutable
as $$
    select case lower(coalesce(value, ''))
        when 'user' then 'user'
        when 'manual' then 'user'
        when 'inat_cv' then 'inat_computer_vision'
        when 'inat_computer_vision' then 'inat_computer_vision'
        when 'inat_lookup' then 'inat_lookup'
        when 'inat_community' then 'inat_community'
        when 'external_expert' then 'external_expert'
        when 'imported_record' then 'imported_record'
        when 'migration' then 'migration'
        else 'legacy_import'
    end
$$;

create or replace function public.capture_identification_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if tg_op = 'INSERT'
       or old.taxon_id is distinct from new.taxon_id
       or old.species_taxon_id is distinct from new.species_taxon_id
       or old.scientific_name is distinct from new.scientific_name
       or old.common_name is distinct from new.common_name
       or old.identification_confidence is distinct from new.identification_confidence
       or old.identification_provenance is distinct from new.identification_provenance
       or old.status is distinct from new.status then
        insert into public.identification_events (
            observation_id, owner_subject, owner_email, taxon_id, species_taxon_id,
            scientific_name, common_name, source, confidence, source_reference_id,
            actor, became_current, created_at
        ) values (
            new.id, new.owner_subject, new.owner_email, new.taxon_id, new.species_taxon_id,
            new.scientific_name, new.common_name,
            public.hikejournal_normalize_identification_source(new.identification_provenance),
            new.identification_confidence, new.inat_observation_id::text,
            'HikeJournal', new.status = 'confirmed', timezone('utc', now())
        );
    end if;
    return new;
end;
$$;

create or replace function public.fill_observation_date()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    photo_taken_at timestamptz;
    outing_date date;
begin
    if new.observed_on is null then
        select photo.taken_at, hike.hike_date
        into photo_taken_at, outing_date
        from public.photos as photo
        left join public.hikes as hike on hike.id = photo.hike_id
        where photo.id = new.photo_id;
        new.observed_on = coalesce(photo_taken_at::date, outing_date, new.identified_at::date);
        new.occurrence_precision = case
            when photo_taken_at is not null then 'exact'
            when outing_date is not null then 'day'
            else 'estimated'
        end;
    end if;
    return new;
end;
$$;

drop trigger if exists species_observations_fill_observed_on on public.species_observations;
create trigger species_observations_fill_observed_on
before insert or update of photo_id, observed_on on public.species_observations
for each row execute procedure public.fill_observation_date();

drop trigger if exists species_observations_capture_identification on public.species_observations;
create trigger species_observations_capture_identification
after insert or update on public.species_observations
for each row execute procedure public.capture_identification_event();

drop trigger if exists observation_annotations_touch_updated_at on public.observation_annotations;
create trigger observation_annotations_touch_updated_at
before update on public.observation_annotations
for each row execute procedure public.touch_updated_at();

drop trigger if exists field_marks_touch_updated_at on public.field_marks;
create trigger field_marks_touch_updated_at
before update on public.field_marks
for each row execute procedure public.touch_updated_at();

create or replace function public.set_observation_natural_history(
    p_observation_id uuid,
    p_confidence text,
    p_provenance text,
    p_phenophases jsonb default '[]'::jsonb
) returns public.species_observations
language plpgsql
security definer
set search_path = public
as $$
declare
    updated_observation public.species_observations;
    annotation jsonb;
begin
    if p_confidence not in ('tentative', 'likely', 'confident', 'externally_confirmed') then
        raise exception 'Unsupported identification confidence.';
    end if;
    if public.hikejournal_normalize_identification_source(p_provenance) <> p_provenance then
        raise exception 'Unsupported identification provenance.';
    end if;
    if jsonb_typeof(coalesce(p_phenophases, '[]'::jsonb)) <> 'array' then
        raise exception 'Phenophases must be a JSON array.';
    end if;

    update public.species_observations
    set identification_confidence = p_confidence,
        identification_provenance = p_provenance
    where id = p_observation_id
    returning * into updated_observation;
    if updated_observation.id is null then
        raise exception 'Observation not found.';
    end if;

    delete from public.observation_annotations
    where observation_id = p_observation_id and category = 'phenophase';

    for annotation in select value from jsonb_array_elements(coalesce(p_phenophases, '[]'::jsonb))
    loop
        if coalesce(trim(annotation->>'code'), '') <> '' then
            insert into public.observation_annotations (
                observation_id, owner_subject, owner_email, category, code, metadata
            ) values (
                p_observation_id,
                updated_observation.owner_subject,
                updated_observation.owner_email,
                'phenophase',
                trim(annotation->>'code'),
                coalesce(annotation->'metadata', '{}'::jsonb)
            )
            on conflict (observation_id, category, code)
            do update set metadata = excluded.metadata, updated_at = timezone('utc', now());
        end if;
    end loop;
    return updated_observation;
end;
$$;

alter table public.identification_events enable row level security;
alter table public.observation_annotations enable row level security;
alter table public.field_marks enable row level security;
alter table public.hike_weather_snapshots enable row level security;
alter table public.identification_events force row level security;
alter table public.observation_annotations force row level security;
alter table public.field_marks force row level security;
alter table public.hike_weather_snapshots force row level security;

revoke all privileges on table public.identification_events from anon, authenticated;
revoke all privileges on table public.observation_annotations from anon, authenticated;
revoke all privileges on table public.field_marks from anon, authenticated;
revoke all privileges on table public.hike_weather_snapshots from anon, authenticated;
grant all privileges on table public.identification_events to service_role;
grant all privileges on table public.observation_annotations to service_role;
grant all privileges on table public.field_marks to service_role;
grant all privileges on table public.hike_weather_snapshots to service_role;

revoke execute on function public.set_observation_natural_history(uuid, text, text, jsonb)
from public, anon, authenticated;
grant execute on function public.set_observation_natural_history(uuid, text, text, jsonb)
to service_role;

-- Verification after applying:
-- select count(*) from public.species_observations where status = 'confirmed';
-- select count(distinct observation_id) from public.identification_events;
-- select count(*) from public.species_observations where observed_on is null;
