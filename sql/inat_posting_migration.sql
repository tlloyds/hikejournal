alter table public.species_observations add column if not exists inat_observation_id bigint;
alter table public.species_observations add column if not exists inat_observation_url text;
alter table public.species_observations add column if not exists inat_posted_at timestamptz;
alter table public.species_observations add column if not exists inat_photo_attached boolean;

create index if not exists species_inat_observation_id_idx
on public.species_observations (inat_observation_id);
