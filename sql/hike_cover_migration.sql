alter table public.hikes add column if not exists cover_photo_id uuid;

alter table public.hikes drop constraint if exists hikes_cover_photo_id_fkey;
alter table public.hikes
add constraint hikes_cover_photo_id_fkey
foreign key (cover_photo_id) references public.photos(id) on delete set null;

create index if not exists hikes_cover_photo_id_idx
on public.hikes (cover_photo_id);
