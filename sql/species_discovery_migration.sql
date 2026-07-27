alter table public.species_observations
add column if not exists species_taxon_id bigint;

alter table public.species_observations
add column if not exists rank text;

alter table public.species_observations
add column if not exists iconic_taxon_name text;

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

create index if not exists species_observations_species_taxon_id_idx
on public.species_observations (species_taxon_id)
where status = 'confirmed';

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

create unique index if not exists species_quest_taxa_focus_order_idx
on public.species_quest_taxa (quest_id, focus_order)
where focus_order is not null;

create index if not exists species_quests_owner_subject_idx on public.species_quests (owner_subject);
create index if not exists species_quests_owner_email_idx on public.species_quests (owner_email);
create index if not exists species_quests_status_idx on public.species_quests (status);
create index if not exists species_quest_taxa_taxon_id_idx on public.species_quest_taxa (taxon_id);
create index if not exists species_discovery_snapshots_expires_at_idx
on public.species_discovery_snapshots (expires_at);

alter table public.species_quest_taxa
add column if not exists wikipedia_url text;

alter table public.species_quest_taxa
add column if not exists wikipedia_summary text;

alter table public.species_quests
drop constraint if exists species_quests_target_count_check;

alter table public.species_quests
add constraint species_quests_target_count_check
check (target_count between 0 and 100);

alter table public.species_quest_taxa
drop constraint if exists species_quest_taxa_focus_order_check;

alter table public.species_quest_taxa
add constraint species_quest_taxa_focus_order_check
check (focus_order between 1 and 10);

create or replace function public.touch_updated_at()
returns trigger as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$ language plpgsql;

drop trigger if exists species_quests_touch_updated_at on public.species_quests;
create trigger species_quests_touch_updated_at
before update on public.species_quests
for each row execute procedure public.touch_updated_at();

alter table public.species_discovery_snapshots enable row level security;
alter table public.species_quests enable row level security;
alter table public.species_quest_taxa enable row level security;
alter table public.species_discovery_snapshots force row level security;
alter table public.species_quests force row level security;
alter table public.species_quest_taxa force row level security;

revoke all privileges on table public.species_discovery_snapshots from anon, authenticated;
revoke all privileges on table public.species_quests from anon, authenticated;
revoke all privileges on table public.species_quest_taxa from anon, authenticated;
grant all privileges on table public.species_discovery_snapshots to service_role;
grant all privileges on table public.species_quests to service_role;
grant all privileges on table public.species_quest_taxa to service_role;
