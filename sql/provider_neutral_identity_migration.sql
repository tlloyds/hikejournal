-- Provider-neutral mobile identities.
--
-- app_users.id is the canonical HikeJournal account ID. google_subject remains
-- as a nullable compatibility shadow so existing Android tokens and owner_subject
-- values keep their exact meaning. Apply this migration before enabling Apple
-- sign-in. Do not drop the shadow until all legacy ownership has been migrated.

create extension if not exists pgcrypto;

alter table public.app_users
alter column google_subject drop not null;

alter table public.app_users
alter column email drop not null;

-- Email is profile/contact data, never an identity key. Removing this uniqueness
-- is required so an Apple identity is not silently merged into a Google account
-- that happens to report the same address.
drop index if exists public.app_users_lower_email_idx;

create index if not exists app_users_lower_email_lookup_idx
on public.app_users (lower(email))
where email is not null;

create table if not exists public.user_identities (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.app_users(id) on delete cascade,
    provider text not null
        check (provider = lower(provider) and provider ~ '^[a-z][a-z0-9_-]{1,31}$'),
    provider_subject text not null check (char_length(trim(provider_subject)) between 1 and 512),
    email text,
    created_at timestamptz not null default timezone('utc', now()),
    last_signed_in_at timestamptz not null default timezone('utc', now()),
    unique (provider, provider_subject),
    unique (user_id, provider)
);

create index if not exists user_identities_user_idx
on public.user_identities (user_id);

insert into public.user_identities (
    user_id,
    provider,
    provider_subject,
    email,
    created_at,
    last_signed_in_at
)
select
    app_user.id,
    'google',
    app_user.google_subject,
    app_user.email,
    app_user.created_at,
    app_user.last_signed_in_at
from public.app_users as app_user
where nullif(trim(app_user.google_subject), '') is not null
on conflict do nothing;

alter table public.mobile_user_sessions
add column if not exists identity_id uuid
references public.user_identities(id) on delete cascade;

create index if not exists mobile_user_sessions_identity_idx
on public.mobile_user_sessions (identity_id, revoked_at, expires_at);

update public.mobile_user_sessions as session
set identity_id = identity.id
from public.user_identities as identity
where session.identity_id is null
  and identity.user_id = session.user_id
  and identity.provider = 'google';

alter table public.user_identities enable row level security;
alter table public.user_identities force row level security;
revoke all privileges on table public.user_identities from anon, authenticated;
grant all privileges on table public.user_identities to service_role;

comment on table public.app_users is
'Canonical HikeJournal accounts. google_subject is a nullable legacy compatibility shadow; identity bindings live in user_identities.';
comment on table public.user_identities is
'Server-managed provider subject bindings. Email is metadata and is never used to merge accounts.';
comment on column public.mobile_user_sessions.identity_id is
'Identity used to create/rotate this session; null only for legacy pre-migration Google sessions.';

create or replace function public.resolve_hikejournal_identity(
    p_provider text,
    p_provider_subject text,
    p_email text default null,
    p_display_name text default '',
    p_picture_url text default null,
    p_signed_in_at timestamptz default timezone('utc', now())
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    normalized_provider text := lower(trim(coalesce(p_provider, '')));
    normalized_subject text := trim(coalesce(p_provider_subject, ''));
    normalized_email text := nullif(lower(trim(coalesce(p_email, ''))), '');
    selected_user public.app_users%rowtype;
    selected_identity public.user_identities%rowtype;
begin
    if normalized_provider !~ '^[a-z][a-z0-9_-]{1,31}$' then
        raise exception 'A valid identity provider is required.';
    end if;
    if normalized_subject = '' or char_length(normalized_subject) > 512 then
        raise exception 'A valid provider subject is required.';
    end if;

    -- Serialize first sign-in for one provider subject. This prevents concurrent
    -- requests from creating two app_users while preserving email neutrality.
    perform pg_advisory_xact_lock(
        hashtextextended(normalized_provider || chr(31) || normalized_subject, 0)
    );

    select identity.* into selected_identity
    from public.user_identities as identity
    where identity.provider = normalized_provider
      and identity.provider_subject = normalized_subject
    for update;

    if selected_identity.id is not null then
        select app_user.* into selected_user
        from public.app_users as app_user
        where app_user.id = selected_identity.user_id
        for update;
    elsif normalized_provider = 'google' then
        -- Claim the exact historical app_users row by its durable Google shadow.
        -- There is deliberately no email lookup or email-based merge here.
        select app_user.* into selected_user
        from public.app_users as app_user
        where app_user.google_subject = normalized_subject
        for update;
    end if;

    if selected_user.id is null then
        insert into public.app_users (
            google_subject,
            email,
            display_name,
            picture_url,
            last_signed_in_at,
            deletion_requested_at
        ) values (
            case when normalized_provider = 'google' then normalized_subject else null end,
            normalized_email,
            coalesce(nullif(trim(p_display_name), ''), normalized_email, 'Hiker'),
            nullif(trim(coalesce(p_picture_url, '')), ''),
            p_signed_in_at,
            null
        )
        returning * into selected_user;
    else
        update public.app_users as app_user
        set google_subject = case
                when normalized_provider = 'google' then normalized_subject
                else app_user.google_subject
            end,
            email = coalesce(normalized_email, app_user.email),
            display_name = coalesce(
                nullif(trim(p_display_name), ''),
                nullif(app_user.display_name, ''),
                normalized_email,
                'Hiker'
            ),
            picture_url = coalesce(
                nullif(trim(coalesce(p_picture_url, '')), ''),
                app_user.picture_url
            ),
            last_signed_in_at = p_signed_in_at,
            deletion_requested_at = null
        where app_user.id = selected_user.id
        returning * into selected_user;
    end if;

    insert into public.user_identities (
        user_id,
        provider,
        provider_subject,
        email,
        last_signed_in_at
    ) values (
        selected_user.id,
        normalized_provider,
        normalized_subject,
        normalized_email,
        p_signed_in_at
    )
    on conflict (provider, provider_subject) do update
    set email = coalesce(excluded.email, user_identities.email),
        last_signed_in_at = excluded.last_signed_in_at
    returning * into selected_identity;

    if selected_identity.user_id <> selected_user.id then
        raise exception 'Identity ownership changed during resolution.';
    end if;

    return jsonb_build_object(
        'user', to_jsonb(selected_user),
        'identity', to_jsonb(selected_identity)
    );
end;
$$;

revoke all on function public.resolve_hikejournal_identity(text, text, text, text, text, timestamptz)
from public, anon, authenticated;
grant execute on function public.resolve_hikejournal_identity(text, text, text, text, text, timestamptz)
to service_role;

-- Canonicalize iNaturalist credentials without breaking old Google clients.
-- owner_email remains as the legacy storage key; new rows use a non-email
-- `user:<uuid>` key and user_id is authoritative. This permits two provider
-- accounts with the same reported email without sharing or overwriting tokens.
alter table public.mobile_inat_credentials
add column if not exists user_id uuid;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'mobile_inat_credentials_user_id_fkey'
          and conrelid = 'public.mobile_inat_credentials'::regclass
    ) then
        alter table public.mobile_inat_credentials
        add constraint mobile_inat_credentials_user_id_fkey
        foreign key (user_id) references public.app_users(id) on delete cascade;
    end if;
end;
$$;

with google_email_matches as (
    select
        lower(app_user.email) as normalized_email,
        (array_agg(app_user.id order by app_user.id))[1] as user_id
    from public.app_users as app_user
    where app_user.google_subject is not null
      and app_user.email is not null
    group by lower(app_user.email)
    having count(*) = 1
)
update public.mobile_inat_credentials as credential
set user_id = matched.user_id
from google_email_matches as matched
where credential.user_id is null
  and lower(credential.owner_email) = matched.normalized_email;

create unique index if not exists mobile_inat_credentials_user_id_idx
on public.mobile_inat_credentials (user_id)
where user_id is not null;

comment on column public.mobile_inat_credentials.user_id is
'Canonical account owner. Null only for an unresolved legacy Google email credential.';

create or replace function public.save_mobile_inat_token_for_user(
    p_user_id uuid,
    p_access_token text,
    p_encryption_key text
) returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    updated_rows integer;
begin
    if not exists (select 1 from public.app_users where id = p_user_id) then
        raise exception 'HikeJournal account not found.';
    end if;

    update public.mobile_inat_credentials
    set encrypted_access_token = extensions.pgp_sym_encrypt(p_access_token, p_encryption_key),
        updated_at = timezone('utc', now())
    where user_id = p_user_id;
    get diagnostics updated_rows = row_count;

    if updated_rows = 0 then
        insert into public.mobile_inat_credentials (
            owner_email,
            user_id,
            encrypted_access_token,
            updated_at
        ) values (
            'user:' || p_user_id::text,
            p_user_id,
            extensions.pgp_sym_encrypt(p_access_token, p_encryption_key),
            timezone('utc', now())
        )
        on conflict (owner_email) do update
        set user_id = excluded.user_id,
            encrypted_access_token = excluded.encrypted_access_token,
            updated_at = excluded.updated_at;
    end if;
end;
$$;

create or replace function public.load_mobile_inat_token_for_user(
    p_user_id uuid,
    p_encryption_key text
) returns text
language sql
security definer
set search_path = public
as $$
    select extensions.pgp_sym_decrypt(encrypted_access_token, p_encryption_key)
    from public.mobile_inat_credentials
    where user_id = p_user_id
    limit 1;
$$;

-- Preserve the old signatures for pre-uid Google sessions. They resolve only
-- to an unambiguous Google app_user; Apple identities are never candidates.
create or replace function public.save_mobile_inat_token(
    p_owner_email text,
    p_access_token text,
    p_encryption_key text
) returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    resolved_user_id uuid;
begin
    select (array_agg(app_user.id order by app_user.id))[1]
    into resolved_user_id
    from public.app_users as app_user
    where app_user.google_subject is not null
      and lower(app_user.email) = lower(trim(p_owner_email))
    having count(*) = 1;

    if resolved_user_id is not null then
        perform public.save_mobile_inat_token_for_user(
            resolved_user_id,
            p_access_token,
            p_encryption_key
        );
        return;
    end if;

    insert into public.mobile_inat_credentials (
        owner_email,
        encrypted_access_token,
        updated_at
    ) values (
        lower(trim(p_owner_email)),
        extensions.pgp_sym_encrypt(p_access_token, p_encryption_key),
        timezone('utc', now())
    )
    on conflict (owner_email) do update
    set encrypted_access_token = excluded.encrypted_access_token,
        updated_at = excluded.updated_at;
end;
$$;

create or replace function public.load_mobile_inat_token(
    p_owner_email text,
    p_encryption_key text
) returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    resolved_user_id uuid;
    access_token text;
begin
    select (array_agg(app_user.id order by app_user.id))[1]
    into resolved_user_id
    from public.app_users as app_user
    where app_user.google_subject is not null
      and lower(app_user.email) = lower(trim(p_owner_email))
    having count(*) = 1;

    if resolved_user_id is not null then
        select public.load_mobile_inat_token_for_user(
            resolved_user_id,
            p_encryption_key
        ) into access_token;
        if access_token is not null then
            return access_token;
        end if;
    end if;

    select extensions.pgp_sym_decrypt(encrypted_access_token, p_encryption_key)
    into access_token
    from public.mobile_inat_credentials
    where user_id is null
      and owner_email = lower(trim(p_owner_email))
    limit 1;
    return access_token;
end;
$$;

revoke all on function public.save_mobile_inat_token_for_user(uuid, text, text)
from public, anon, authenticated;
revoke all on function public.load_mobile_inat_token_for_user(uuid, text)
from public, anon, authenticated;
revoke all on function public.save_mobile_inat_token(text, text, text)
from public, anon, authenticated;
revoke all on function public.load_mobile_inat_token(text, text)
from public, anon, authenticated;
grant execute on function public.save_mobile_inat_token_for_user(uuid, text, text)
to service_role;
grant execute on function public.load_mobile_inat_token_for_user(uuid, text)
to service_role;
grant execute on function public.save_mobile_inat_token(text, text, text)
to service_role;
grant execute on function public.load_mobile_inat_token(text, text)
to service_role;

create or replace function public.delete_hikejournal_account_by_user_id(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    account public.app_users%rowtype;
    ownership_subjects text[] := array[]::text[];
    allow_legacy_email_cleanup boolean := false;
begin
    select app_user.* into account
    from public.app_users as app_user
    where app_user.id = p_user_id
    for update;

    if account.id is null then
        raise exception 'HikeJournal account not found.';
    end if;

    select coalesce(
        array_agg(
            distinct case
                when identity.provider = 'google' then identity.provider_subject
                else identity.provider || ':' || identity.provider_subject
            end
        ),
        array[]::text[]
    ) into ownership_subjects
    from public.user_identities as identity
    where identity.user_id = account.id;

    if account.google_subject is not null
       and not (account.google_subject = any(ownership_subjects)) then
        ownership_subjects := array_append(ownership_subjects, account.google_subject);
    end if;

    -- Email-only cleanup exists solely for unambiguous historical Google data.
    -- Once two accounts share an address, leaving an ambiguous legacy row is
    -- safer than deleting another account's data.
    if account.google_subject is not null and account.email is not null then
        select count(*) = 1 into allow_legacy_email_cleanup
        from public.app_users as candidate
        where lower(candidate.email) = lower(account.email);
    end if;

    if allow_legacy_email_cleanup then
        delete from public.mobile_inat_credentials
        where lower(owner_email) = lower(account.email);
    end if;

    delete from public.mobile_api_jobs as job
    where job.owner_key in (
        select encode(
            digest(
                convert_to(
                    '{"subject":' || to_json(subject_value)::text || '}',
                    'UTF8'
                ),
                'sha256'
            ),
            'hex'
        )
        from unnest(ownership_subjects) as subject_value
    );

    delete from public.species_quests as quest
    where quest.owner_subject = any(ownership_subjects)
       or (
           allow_legacy_email_cleanup
           and quest.owner_subject is null
           and lower(quest.owner_email) = lower(account.email)
       );

    delete from public.species_observations as observation
    where observation.hike_id is null
      and (
          observation.owner_subject = any(ownership_subjects)
          or (
              allow_legacy_email_cleanup
              and observation.owner_subject is null
              and lower(observation.owner_email) = lower(account.email)
          )
      );

    delete from public.photos as photo
    where photo.hike_id is null
      and (
          photo.owner_subject = any(ownership_subjects)
          or (
              allow_legacy_email_cleanup
              and photo.owner_subject is null
              and lower(photo.owner_email) = lower(account.email)
          )
      );

    delete from public.hikes as hike
    where hike.owner_subject = any(ownership_subjects)
       or (
           allow_legacy_email_cleanup
           and hike.owner_subject is null
           and lower(hike.owner_email) = lower(account.email)
       );

    delete from public.hike_locations as location
    where location.owner_subject = any(ownership_subjects)
       or (
           allow_legacy_email_cleanup
           and location.owner_subject is null
           and lower(location.owner_email) = lower(account.email)
       );

    -- The entitlement migration may independently add canonical owner_user_id
    -- columns. Use them when present without making either migration depend on
    -- deployment order.
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'photos'
          and column_name = 'owner_user_id'
    ) then
        execute 'delete from public.photos where owner_user_id = $1'
        using account.id;
    end if;

    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'hikes'
          and column_name = 'owner_user_id'
    ) then
        execute 'delete from public.hikes where owner_user_id = $1'
        using account.id;
    end if;

    delete from public.app_users
    where id = account.id;
end;
$$;

revoke all on function public.delete_hikejournal_account_by_user_id(uuid)
from public, anon, authenticated;
grant execute on function public.delete_hikejournal_account_by_user_id(uuid)
to service_role;

-- Keep the Android/web deletion wrapper and its parameter name unchanged.
create or replace function public.delete_hikejournal_account(p_google_subject text)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    account_id uuid;
begin
    if coalesce(trim(p_google_subject), '') = '' then
        raise exception 'A Google subject is required.';
    end if;

    select app_user.id into account_id
    from public.app_users as app_user
    where app_user.google_subject = trim(p_google_subject);

    if account_id is null then
        select identity.user_id into account_id
        from public.user_identities as identity
        where identity.provider = 'google'
          and identity.provider_subject = trim(p_google_subject);
    end if;

    if account_id is null then
        raise exception 'HikeJournal account not found.';
    end if;

    perform public.delete_hikejournal_account_by_user_id(account_id);
end;
$$;

revoke all on function public.delete_hikejournal_account(text)
from public, anon, authenticated;
grant execute on function public.delete_hikejournal_account(text)
to service_role;
