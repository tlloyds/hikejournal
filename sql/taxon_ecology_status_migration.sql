-- HikeJournal place-aware native / introduced / invasive status.
-- Safe to run once against an existing Supabase project. All changes are additive.

create extension if not exists pgcrypto;

create table if not exists public.taxon_ecology_statuses (
    id uuid primary key default gen_random_uuid(),
    taxon_id bigint not null,
    species_taxon_id bigint,
    region_code text not null default 'unknown',
    place_id bigint,
    place_name text not null default '',
    label text not null default 'unknown'
        check (label in ('native', 'non_native', 'invasive', 'unknown')),
    establishment_status text not null default 'unknown'
        check (establishment_status in ('native', 'introduced', 'endemic', 'unknown')),
    invasive_status text not null default 'unknown'
        check (invasive_status in ('invasive', 'unknown')),
    establishment_means text not null default 'unknown',
    source text not null default 'inaturalist',
    source_url text not null default '',
    raw_response_json jsonb not null default '{}'::jsonb,
    assessed_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    unique (taxon_id, region_code)
);

create index if not exists taxon_ecology_statuses_species_taxon_id_idx
on public.taxon_ecology_statuses (species_taxon_id);

create index if not exists taxon_ecology_statuses_region_label_idx
on public.taxon_ecology_statuses (region_code, label);

alter table public.taxon_ecology_statuses enable row level security;
alter table public.taxon_ecology_statuses force row level security;
revoke all privileges on table public.taxon_ecology_statuses from anon, authenticated;
grant all privileges on table public.taxon_ecology_statuses to service_role;

create or replace function public.touch_updated_at()
returns trigger as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$ language plpgsql;

drop trigger if exists taxon_ecology_statuses_touch_updated_at on public.taxon_ecology_statuses;
create trigger taxon_ecology_statuses_touch_updated_at
before update on public.taxon_ecology_statuses
for each row execute procedure public.touch_updated_at();

