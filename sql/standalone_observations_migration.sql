alter table public.photos add column if not exists owner_subject text;
alter table public.photos add column if not exists owner_email text;
alter table public.photos alter column hike_id drop not null;

alter table public.species_observations add column if not exists owner_subject text;
alter table public.species_observations add column if not exists owner_email text;
alter table public.species_observations alter column hike_id drop not null;

create index if not exists photos_owner_subject_idx on public.photos (owner_subject);
create index if not exists photos_owner_email_idx on public.photos (owner_email);
create index if not exists species_owner_subject_idx on public.species_observations (owner_subject);
create index if not exists species_owner_email_idx on public.species_observations (owner_email);
