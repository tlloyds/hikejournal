-- Public mobile accounts and user-managed places for the Google-authenticated app.
-- This migration is repeatable and keeps the existing Florida place catalog global.

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

create unique index if not exists app_users_lower_email_idx
on public.app_users (lower(email));

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

create index if not exists mobile_user_sessions_user_idx
on public.mobile_user_sessions (user_id, revoked_at, expires_at);

alter table public.hike_locations add column if not exists owner_subject text;
alter table public.hike_locations add column if not exists owner_email text;

create index if not exists hike_locations_owner_subject_idx
on public.hike_locations (owner_subject);

alter table public.app_users enable row level security;
alter table public.mobile_user_sessions enable row level security;
alter table public.app_users force row level security;
alter table public.mobile_user_sessions force row level security;

revoke all privileges on table public.app_users from anon, authenticated;
revoke all privileges on table public.mobile_user_sessions from anon, authenticated;

comment on table public.app_users is
'Server-managed Google identities for HikeJournal mobile. Direct client access is intentionally disabled.';
comment on table public.mobile_user_sessions is
'Rotating, server-managed mobile refresh sessions. Only SHA-256 refresh-token hashes are stored.';
comment on column public.hike_locations.owner_subject is
'Null for the shared Florida catalog; Google subject for a user-managed place.';

create or replace function public.delete_hikejournal_account(p_google_subject text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    account_email text;
begin
    if coalesce(trim(p_google_subject), '') = '' then
        raise exception 'A Google subject is required.';
    end if;

    select email into account_email
    from public.app_users
    where google_subject = trim(p_google_subject)
    for update;

    if account_email is null then
        raise exception 'HikeJournal account not found.';
    end if;

    delete from public.mobile_inat_credentials
    where lower(owner_email) = lower(account_email);

    delete from public.mobile_api_jobs
    where owner_key = encode(
        digest(
            convert_to(
                '{"subject":' || to_json(trim(p_google_subject))::text || '}',
                'UTF8'
            ),
            'sha256'
        ),
        'hex'
    );

    delete from public.species_quests
    where owner_subject = trim(p_google_subject)
       or lower(owner_email) = lower(account_email);

    delete from public.species_observations
    where hike_id is null
      and (
          owner_subject = trim(p_google_subject)
          or lower(owner_email) = lower(account_email)
      );

    delete from public.photos
    where hike_id is null
      and (
          owner_subject = trim(p_google_subject)
          or lower(owner_email) = lower(account_email)
      );

    delete from public.hikes
    where owner_subject = trim(p_google_subject)
       or lower(owner_email) = lower(account_email);

    delete from public.hike_locations
    where owner_subject = trim(p_google_subject)
       or lower(owner_email) = lower(account_email);

    delete from public.app_users
    where google_subject = trim(p_google_subject);
end;
$$;

revoke all on function public.delete_hikejournal_account(text) from public, anon, authenticated;
grant execute on function public.delete_hikejournal_account(text) to service_role;
