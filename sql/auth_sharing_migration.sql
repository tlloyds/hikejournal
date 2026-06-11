alter table public.hikes add column if not exists owner_subject text;
alter table public.hikes add column if not exists owner_email text;
alter table public.hikes add column if not exists is_archived boolean not null default false;

create table if not exists public.hike_collaborators (
    id uuid primary key default gen_random_uuid(),
    hike_id uuid not null references public.hikes(id) on delete cascade,
    collaborator_email text not null,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists hikes_owner_subject_idx on public.hikes (owner_subject);
create index if not exists hikes_owner_email_idx on public.hikes (owner_email);
create index if not exists hike_collaborators_hike_id_idx on public.hike_collaborators (hike_id);
create unique index if not exists hike_collaborators_unique_email_idx on public.hike_collaborators (hike_id, lower(collaborator_email));

alter table public.hike_collaborators enable row level security;

drop policy if exists "Open single-user access for hike collaborators" on public.hike_collaborators;
create policy "Open single-user access for hike collaborators"
on public.hike_collaborators
for all
using (true)
with check (true);
