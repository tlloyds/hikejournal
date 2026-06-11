alter table public.species_observations add column if not exists is_primary boolean not null default false;

update public.species_observations set is_primary = true where id in (
    select id from (
        select distinct on (photo_id) id
        from public.species_observations
        order by photo_id, identified_at desc
    ) ranked
);

alter table public.species_observations
drop constraint if exists species_observations_photo_id_key;
create index if not exists species_photo_id_idx on public.species_observations (photo_id);
create unique index if not exists species_primary_per_photo_idx
on public.species_observations (photo_id)
where is_primary = true;
