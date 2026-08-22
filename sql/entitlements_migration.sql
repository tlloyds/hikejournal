-- Server-authoritative HikeJournal Free / Plus / Lifetime entitlements.
--
-- Apply after public.app_users exists. provider_neutral_identity_migration.sql
-- may run before or after this migration; this file only relies on app_users.id
-- and never assumes that email or google_subject is present, unique, or non-null.
-- Existing Android endpoints are intentionally not gated by this migration.
-- Their current paid-download experience remains in an observe-only migration
-- stage until a separately controlled Android commercial release.
--
-- Recovery: tables are additive and existing ownership columns are preserved.
-- Before rollback, export app_entitlements/app_entitlement_events, stop callers
-- of the RPCs, then drop the new triggers/functions/tables. The owner_user_id
-- columns can remain safely because legacy owner_subject writes still work.

create extension if not exists pgcrypto;

alter table public.hikes
add column if not exists owner_user_id uuid;

alter table public.photos
add column if not exists owner_user_id uuid;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'hikes_owner_user_id_fkey'
          and conrelid = 'public.hikes'::regclass
    ) then
        alter table public.hikes
        add constraint hikes_owner_user_id_fkey
        foreign key (owner_user_id) references public.app_users(id) on delete set null;
    end if;

    if not exists (
        select 1
        from pg_constraint
        where conname = 'photos_owner_user_id_fkey'
          and conrelid = 'public.photos'::regclass
    ) then
        alter table public.photos
        add constraint photos_owner_user_id_fkey
        foreign key (owner_user_id) references public.app_users(id) on delete set null;
    end if;
end;
$$;

-- Backfill only an unambiguous immutable Google subject. Never infer account
-- ownership from email because provider-neutral accounts may share/change it.
with unique_google_subjects as (
    select
        google_subject,
        (array_agg(id order by id))[1] as user_id
    from public.app_users
    where google_subject is not null
      and trim(google_subject) <> ''
    group by google_subject
    having count(*) = 1
)
update public.hikes as hike
set owner_user_id = identity.user_id
from unique_google_subjects as identity
where hike.owner_user_id is null
  and hike.owner_subject = identity.google_subject;

update public.photos as photo
set owner_user_id = hike.owner_user_id
from public.hikes as hike
where photo.owner_user_id is null
  and photo.hike_id = hike.id
  and hike.owner_user_id is not null;

with unique_google_subjects as (
    select
        google_subject,
        (array_agg(id order by id))[1] as user_id
    from public.app_users
    where google_subject is not null
      and trim(google_subject) <> ''
    group by google_subject
    having count(*) = 1
)
update public.photos as photo
set owner_user_id = identity.user_id
from unique_google_subjects as identity
where photo.owner_user_id is null
  and photo.owner_subject = identity.google_subject;

create index if not exists hikes_owner_user_id_idx
on public.hikes (owner_user_id);

create index if not exists photos_owner_user_id_idx
on public.photos (owner_user_id);

-- Preserve legacy Android writes while endpoint integration is staged. New
-- provider-neutral callers should always send owner_user_id explicitly; this
-- trigger only fills a missing value from a hike or one unambiguous immutable
-- Google subject. It deliberately never falls back to email.
create or replace function public.fill_owner_user_id_from_legacy_subject()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    inferred_user_id uuid;
begin
    if new.owner_user_id is not null then
        return new;
    end if;

    if tg_table_name = 'photos' and new.hike_id is not null then
        select hike.owner_user_id into inferred_user_id
        from public.hikes as hike
        where hike.id = new.hike_id;
    end if;

    if inferred_user_id is null and coalesce(trim(new.owner_subject), '') <> '' then
        select (array_agg(account.id order by account.id))[1] into inferred_user_id
        from public.app_users as account
        where account.google_subject = new.owner_subject
        having count(*) = 1;
    end if;

    new.owner_user_id := inferred_user_id;
    return new;
end;
$$;

drop trigger if exists hikes_fill_owner_user_id on public.hikes;
create trigger hikes_fill_owner_user_id
before insert or update on public.hikes
for each row execute function public.fill_owner_user_id_from_legacy_subject();

drop trigger if exists photos_fill_owner_user_id on public.photos;
create trigger photos_fill_owner_user_id
before insert or update on public.photos
for each row execute function public.fill_owner_user_id_from_legacy_subject();

create table if not exists public.app_entitlement_policies (
    plan text primary key
        check (plan in ('free', 'plus', 'lifetime')),
    cloud_hikes_limit integer
        check (cloud_hikes_limit is null or cloud_hikes_limit >= 0),
    cloud_media_limit integer
        check (cloud_media_limit is null or cloud_media_limit >= 0),
    features jsonb not null default '{}'::jsonb
        check (jsonb_typeof(features) = 'object'),
    policy_version text not null,
    updated_at timestamptz not null default timezone('utc', now())
);

insert into public.app_entitlement_policies (
    plan,
    cloud_hikes_limit,
    cloud_media_limit,
    features,
    policy_version
)
values
    (
        'free',
        3,
        50,
        '{
          "basic_maps": true,
          "cloud_journals": true,
          "cloud_media": true,
          "field_guide_basic": true,
          "gps_recording": true,
          "route_viewing": true,
          "field_briefing": false,
          "historical_weather": false,
          "hike_comparison": false,
          "offline_maps": false,
          "phenology_history": false,
          "place_profiles": false,
          "provenance_history": false,
          "species_intelligence": false
        }'::jsonb,
        '2026-08-21'
    ),
    (
        'plus',
        null,
        10000,
        '{
          "basic_maps": true,
          "cloud_journals": true,
          "cloud_media": true,
          "field_guide_basic": true,
          "gps_recording": true,
          "route_viewing": true,
          "field_briefing": true,
          "historical_weather": true,
          "hike_comparison": true,
          "offline_maps": true,
          "phenology_history": true,
          "place_profiles": true,
          "provenance_history": true,
          "species_intelligence": true
        }'::jsonb,
        '2026-08-21'
    ),
    (
        'lifetime',
        null,
        10000,
        '{
          "basic_maps": true,
          "cloud_journals": true,
          "cloud_media": true,
          "field_guide_basic": true,
          "gps_recording": true,
          "route_viewing": true,
          "field_briefing": true,
          "historical_weather": true,
          "hike_comparison": true,
          "offline_maps": true,
          "phenology_history": true,
          "place_profiles": true,
          "provenance_history": true,
          "species_intelligence": true
        }'::jsonb,
        '2026-08-21'
    )
on conflict (plan) do nothing;

create table if not exists public.app_entitlements (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.app_users(id) on delete cascade,
    plan text not null
        check (plan in ('free', 'plus', 'lifetime')),
    source text not null
        check (source in (
            'free',
            'apple_subscription',
            'google_play_subscription',
            'google_play_legacy',
            'admin'
        )),
    external_entitlement_id text not null
        check (char_length(external_entitlement_id) between 1 and 255),
    product_id text,
    billing_period text
        check (billing_period is null or billing_period in ('monthly', 'annual', 'lifetime')),
    status text not null
        check (status in ('active', 'grace', 'canceled', 'expired', 'revoked', 'refunded')),
    started_at timestamptz,
    expires_at timestamptz,
    grace_expires_at timestamptz,
    revoked_at timestamptz,
    refunded_at timestamptz,
    original_transaction_id text,
    purchase_token_hash text,
    environment text,
    last_event_at timestamptz not null,
    metadata jsonb not null default '{}'::jsonb
        check (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint app_entitlements_source_external_key
        unique (source, external_entitlement_id),
    constraint app_entitlements_original_transaction_key
        unique (source, original_transaction_id),
    constraint app_entitlements_purchase_token_key
        unique (source, purchase_token_hash),
    check (purchase_token_hash is null or purchase_token_hash ~ '^[0-9a-f]{64}$'),
    check (source <> 'apple_subscription' or coalesce(trim(original_transaction_id), '') <> ''),
    check (
        source <> 'google_play_legacy'
        or (
            plan = 'lifetime'
            and billing_period = 'lifetime'
            and purchase_token_hash is not null
        )
    ),
    check (
        plan <> 'lifetime'
        or source in ('google_play_legacy', 'admin')
    ),
    check (
        status <> 'grace'
        or coalesce(grace_expires_at, expires_at) is not null
    ),
    check (revoked_at is null or refunded_at is null)
);

create index if not exists app_entitlements_user_resolution_idx
on public.app_entitlements (user_id, plan, status, last_event_at desc);

create table if not exists public.app_entitlement_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.app_users(id) on delete cascade,
    entitlement_id uuid references public.app_entitlements(id) on delete set null,
    source text not null
        check (source in (
            'apple_subscription',
            'google_play_subscription',
            'google_play_legacy',
            'admin'
        )),
    external_event_id text not null
        check (char_length(external_event_id) between 1 and 255),
    event_type text not null
        check (char_length(event_type) between 1 and 120),
    event_fingerprint text not null
        check (event_fingerprint ~ '^[0-9a-f]{64}$'),
    occurred_at timestamptz not null,
    metadata jsonb not null default '{}'::jsonb
        check (jsonb_typeof(metadata) = 'object'),
    received_at timestamptz not null default timezone('utc', now()),
    constraint app_entitlement_events_idempotency_key
        unique (source, external_event_id)
);

create index if not exists app_entitlement_events_user_idx
on public.app_entitlement_events (user_id, occurred_at desc);

create table if not exists public.app_quota_reservations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.app_users(id) on delete cascade,
    resource_type text not null
        check (resource_type in ('cloud_hikes', 'cloud_media')),
    request_id text not null
        check (char_length(request_id) between 1 and 128),
    resource_id uuid not null,
    state text not null default 'reserved'
        check (state in ('reserved', 'committed', 'released', 'expired')),
    plan_at_reservation text not null
        check (plan_at_reservation in ('free', 'plus', 'lifetime')),
    limit_at_reservation integer
        check (limit_at_reservation is null or limit_at_reservation >= 0),
    expires_at timestamptz,
    committed_at timestamptz,
    released_at timestamptz,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint app_quota_reservations_request_key
        unique (user_id, resource_type, request_id)
);

create unique index if not exists app_quota_reservations_active_resource_idx
on public.app_quota_reservations (user_id, resource_type, resource_id)
where state in ('reserved', 'committed');

create index if not exists app_quota_reservations_expiration_idx
on public.app_quota_reservations (state, expires_at)
where state = 'reserved';

create or replace function public.effective_app_entitlement_plan(
    p_user_id uuid,
    p_at timestamptz default timezone('utc', now())
) returns text
language sql
stable
security definer
set search_path = public
as $$
    with normalized as (
        select
            entitlement.plan,
            case
                when entitlement.refunded_at is not null
                  or entitlement.status = 'refunded' then 'refunded'
                when entitlement.revoked_at is not null
                  or entitlement.status = 'revoked' then 'revoked'
                when entitlement.status = 'expired' then 'expired'
                when entitlement.status = 'grace'
                  and coalesce(entitlement.grace_expires_at, entitlement.expires_at) > p_at
                  then 'grace'
                when entitlement.status = 'grace' then 'expired'
                when entitlement.expires_at is not null
                  and entitlement.expires_at <= p_at then 'expired'
                when entitlement.status = 'canceled'
                  and entitlement.expires_at > p_at then 'canceled_but_unexpired'
                when entitlement.status = 'canceled' then 'expired'
                else 'active'
            end as resolved_status,
            entitlement.last_event_at,
            entitlement.id
        from public.app_entitlements as entitlement
        where entitlement.user_id = p_user_id
    )
    select coalesce(
        (
            select normalized.plan
            from normalized
            where normalized.plan in ('plus', 'lifetime')
              and normalized.resolved_status in ('active', 'grace', 'canceled_but_unexpired')
            order by
                case normalized.plan when 'lifetime' then 2 else 1 end desc,
                normalized.last_event_at desc,
                normalized.id desc
            limit 1
        ),
        'free'
    );
$$;

create or replace function public.app_quota_usage(
    p_user_id uuid,
    p_resource_type text
) returns bigint
language plpgsql
stable
security definer
set search_path = public
as $$
begin
    if p_resource_type = 'cloud_hikes' then
        return (
            select count(*)
            from public.hikes as hike
            where hike.owner_user_id = p_user_id
        );
    elsif p_resource_type = 'cloud_media' then
        return (
            select count(*)
            from public.photos as photo
            where photo.owner_user_id = p_user_id
        );
    end if;
    raise exception 'Unknown quota resource type: %', p_resource_type
        using errcode = '22023';
end;
$$;

create or replace function public.app_quota_reserved_usage(
    p_user_id uuid,
    p_resource_type text,
    p_at timestamptz default timezone('utc', now())
) returns bigint
language sql
stable
security definer
set search_path = public
as $$
    select count(*)
    from public.app_quota_reservations as reservation
    where reservation.user_id = p_user_id
      and reservation.resource_type = p_resource_type
      and reservation.state = 'reserved'
      and reservation.expires_at > p_at
      and (
          (
              p_resource_type = 'cloud_hikes'
              and not exists (
                  select 1
                  from public.hikes as hike
                  where hike.id = reservation.resource_id
                    and hike.owner_user_id = p_user_id
              )
          )
          or (
              p_resource_type = 'cloud_media'
              and not exists (
                  select 1
                  from public.photos as photo
                  where photo.id = reservation.resource_id
                    and photo.owner_user_id = p_user_id
              )
          )
      );
$$;

create or replace function public.reserve_app_quota(
    p_user_id uuid,
    p_resource_type text,
    p_request_id text,
    p_resource_id uuid,
    p_ttl_seconds integer default 900
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    current_time timestamptz := timezone('utc', now());
    existing_reservation public.app_quota_reservations%rowtype;
    active_resource_reservation public.app_quota_reservations%rowtype;
    effective_plan text;
    quota_limit integer;
    actual_usage bigint;
    reserved_usage bigint;
    new_reservation_id uuid;
    is_reused boolean := false;
begin
    if p_user_id is null or not exists (
        select 1 from public.app_users where id = p_user_id
    ) then
        raise exception 'A valid HikeJournal user is required.' using errcode = '22023';
    end if;
    if p_resource_type not in ('cloud_hikes', 'cloud_media') then
        raise exception 'Unknown quota resource type: %', p_resource_type using errcode = '22023';
    end if;
    if coalesce(trim(p_request_id), '') = '' or char_length(p_request_id) > 128 then
        raise exception 'A quota request ID between 1 and 128 characters is required.'
            using errcode = '22023';
    end if;
    if p_resource_id is null then
        raise exception 'A durable resource ID is required.' using errcode = '22023';
    end if;

    -- All competing reservations for one account/resource serialize inside the
    -- same transaction, so concurrent requests cannot both consume the final slot.
    perform pg_advisory_xact_lock(
        hashtextextended(p_user_id::text || ':' || p_resource_type, 0)
    );

    update public.app_quota_reservations as reservation
    set state = 'expired',
        updated_at = current_time
    where reservation.user_id = p_user_id
      and reservation.resource_type = p_resource_type
      and reservation.state = 'reserved'
      and reservation.expires_at <= current_time;

    select reservation.* into existing_reservation
    from public.app_quota_reservations as reservation
    where reservation.user_id = p_user_id
      and reservation.resource_type = p_resource_type
      and reservation.request_id = p_request_id
    for update;

    if found then
        if existing_reservation.resource_id <> p_resource_id then
            raise exception 'Quota request ID was already used for a different resource.'
                using errcode = '22023';
        end if;
        if existing_reservation.state in ('reserved', 'committed') then
            actual_usage := public.app_quota_usage(p_user_id, p_resource_type);
            reserved_usage := public.app_quota_reserved_usage(
                p_user_id,
                p_resource_type,
                current_time
            );
            return jsonb_build_object(
                'allowed', true,
                'idempotent', true,
                'reservation_id', existing_reservation.id,
                'resource', p_resource_type,
                'resource_id', p_resource_id,
                'plan', existing_reservation.plan_at_reservation,
                'limit', existing_reservation.limit_at_reservation,
                'used', actual_usage,
                'reserved', reserved_usage,
                'remaining', case
                    when existing_reservation.limit_at_reservation is null then null
                    else greatest(
                        existing_reservation.limit_at_reservation
                        - actual_usage
                        - reserved_usage,
                        0
                    )
                end,
                'reason', null
            );
        elsif existing_reservation.state = 'released' then
            return jsonb_build_object(
                'allowed', false,
                'idempotent', true,
                'reservation_id', existing_reservation.id,
                'resource', p_resource_type,
                'resource_id', p_resource_id,
                'plan', existing_reservation.plan_at_reservation,
                'limit', existing_reservation.limit_at_reservation,
                'used', public.app_quota_usage(p_user_id, p_resource_type),
                'reserved', public.app_quota_reserved_usage(p_user_id, p_resource_type, current_time),
                'remaining', null,
                'reason', 'reservation_released'
            );
        end if;
        is_reused := true;
    end if;

    select reservation.* into active_resource_reservation
    from public.app_quota_reservations as reservation
    where reservation.user_id = p_user_id
      and reservation.resource_type = p_resource_type
      and reservation.resource_id = p_resource_id
      and reservation.state in ('reserved', 'committed')
    limit 1
    for update;

    if found then
        return jsonb_build_object(
            'allowed', false,
            'idempotent', false,
            'reservation_id', active_resource_reservation.id,
            'resource', p_resource_type,
            'resource_id', p_resource_id,
            'plan', active_resource_reservation.plan_at_reservation,
            'limit', active_resource_reservation.limit_at_reservation,
            'used', public.app_quota_usage(p_user_id, p_resource_type),
            'reserved', public.app_quota_reserved_usage(p_user_id, p_resource_type, current_time),
            'remaining', null,
            'reason', 'resource_already_reserved'
        );
    end if;

    effective_plan := public.effective_app_entitlement_plan(p_user_id, current_time);
    select
        case
            when p_resource_type = 'cloud_hikes' then policy.cloud_hikes_limit
            else policy.cloud_media_limit
        end
    into quota_limit
    from public.app_entitlement_policies as policy
    where policy.plan = effective_plan;

    if not found then
        raise exception 'No entitlement policy is configured for plan %.', effective_plan;
    end if;

    actual_usage := public.app_quota_usage(p_user_id, p_resource_type);
    reserved_usage := public.app_quota_reserved_usage(
        p_user_id,
        p_resource_type,
        current_time
    );
    if quota_limit is not null and actual_usage + reserved_usage >= quota_limit then
        return jsonb_build_object(
            'allowed', false,
            'idempotent', false,
            'reservation_id', null,
            'resource', p_resource_type,
            'resource_id', p_resource_id,
            'plan', effective_plan,
            'limit', quota_limit,
            'used', actual_usage,
            'reserved', reserved_usage,
            'remaining', 0,
            'reason', 'quota_exceeded'
        );
    end if;

    if is_reused then
        update public.app_quota_reservations as reservation
        set state = 'reserved',
            plan_at_reservation = effective_plan,
            limit_at_reservation = quota_limit,
            expires_at = current_time + make_interval(
                secs => greatest(60, least(coalesce(p_ttl_seconds, 900), 3600))
            ),
            committed_at = null,
            released_at = null,
            updated_at = current_time
        where reservation.id = existing_reservation.id
        returning reservation.id into new_reservation_id;
    else
        insert into public.app_quota_reservations (
            user_id,
            resource_type,
            request_id,
            resource_id,
            state,
            plan_at_reservation,
            limit_at_reservation,
            expires_at
        ) values (
            p_user_id,
            p_resource_type,
            p_request_id,
            p_resource_id,
            'reserved',
            effective_plan,
            quota_limit,
            current_time + make_interval(
                secs => greatest(60, least(coalesce(p_ttl_seconds, 900), 3600))
            )
        )
        returning id into new_reservation_id;
    end if;

    reserved_usage := reserved_usage + 1;
    return jsonb_build_object(
        'allowed', true,
        'idempotent', false,
        'reservation_id', new_reservation_id,
        'resource', p_resource_type,
        'resource_id', p_resource_id,
        'plan', effective_plan,
        'limit', quota_limit,
        'used', actual_usage,
        'reserved', reserved_usage,
        'remaining', case
            when quota_limit is null then null
            else greatest(quota_limit - actual_usage - reserved_usage, 0)
        end,
        'reason', null
    );
end;
$$;

create or replace function public.release_app_quota_reservation(
    p_user_id uuid,
    p_resource_type text,
    p_request_id text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    released_id uuid;
begin
    perform pg_advisory_xact_lock(
        hashtextextended(p_user_id::text || ':' || p_resource_type, 0)
    );
    update public.app_quota_reservations as reservation
    set state = 'released',
        released_at = timezone('utc', now()),
        expires_at = null,
        updated_at = timezone('utc', now())
    where reservation.user_id = p_user_id
      and reservation.resource_type = p_resource_type
      and reservation.request_id = p_request_id
      and reservation.state = 'reserved'
    returning reservation.id into released_id;
    return jsonb_build_object(
        'released', released_id is not null,
        'reservation_id', released_id
    );
end;
$$;

create or replace function public.sync_app_quota_reservation()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    quota_resource text := case
        when tg_table_name = 'hikes' then 'cloud_hikes'
        else 'cloud_media'
    end;
begin
    if tg_op = 'DELETE' then
        if old.owner_user_id is not null then
            update public.app_quota_reservations as reservation
            set state = 'released',
                released_at = timezone('utc', now()),
                expires_at = null,
                updated_at = timezone('utc', now())
            where reservation.user_id = old.owner_user_id
              and reservation.resource_type = quota_resource
              and reservation.resource_id = old.id
              and reservation.state in ('reserved', 'committed');
        end if;
        return old;
    end if;

    if tg_op = 'UPDATE'
       and old.owner_user_id is distinct from new.owner_user_id
       and old.owner_user_id is not null then
        update public.app_quota_reservations as reservation
        set state = 'released',
            released_at = timezone('utc', now()),
            expires_at = null,
            updated_at = timezone('utc', now())
        where reservation.user_id = old.owner_user_id
          and reservation.resource_type = quota_resource
          and reservation.resource_id = old.id
          and reservation.state in ('reserved', 'committed');
    end if;

    if new.owner_user_id is not null then
        update public.app_quota_reservations as reservation
        set state = 'committed',
            committed_at = coalesce(reservation.committed_at, timezone('utc', now())),
            expires_at = null,
            updated_at = timezone('utc', now())
        where reservation.user_id = new.owner_user_id
          and reservation.resource_type = quota_resource
          and reservation.resource_id = new.id
          and reservation.state = 'reserved';
    end if;
    return new;
end;
$$;

drop trigger if exists hikes_sync_app_quota_reservation on public.hikes;
create trigger hikes_sync_app_quota_reservation
after insert or update or delete on public.hikes
for each row execute function public.sync_app_quota_reservation();

drop trigger if exists photos_sync_app_quota_reservation on public.photos;
create trigger photos_sync_app_quota_reservation
after insert or update or delete on public.photos
for each row execute function public.sync_app_quota_reservation();

create or replace function public.apply_app_entitlement_event(
    p_projection jsonb
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    projection_user_id uuid;
    projection_source text;
    projection_event_id text;
    projection_entitlement_id text;
    projection_event_type text;
    projection_fingerprint text;
    projection_occurred_at timestamptz;
    projection_plan text;
    projection_status text;
    projection_product_id text;
    projection_billing_period text;
    projection_started_at timestamptz;
    projection_expires_at timestamptz;
    projection_grace_expires_at timestamptz;
    projection_revoked_at timestamptz;
    projection_refunded_at timestamptz;
    projection_original_transaction_id text;
    projection_purchase_token_hash text;
    projection_environment text;
    projection_metadata jsonb;
    existing_event public.app_entitlement_events%rowtype;
    entitlement public.app_entitlements%rowtype;
    entitlement_row_id uuid;
    should_apply boolean := true;
begin
    if p_projection is null or jsonb_typeof(p_projection) <> 'object' then
        raise exception 'Entitlement projection must be a JSON object.' using errcode = '22023';
    end if;

    projection_user_id := nullif(p_projection->>'user_id', '')::uuid;
    projection_source := nullif(p_projection->>'source', '');
    projection_event_id := nullif(p_projection->>'external_event_id', '');
    projection_entitlement_id := nullif(p_projection->>'external_entitlement_id', '');
    projection_event_type := nullif(p_projection->>'event_type', '');
    projection_fingerprint := nullif(p_projection->>'event_fingerprint', '');
    projection_occurred_at := nullif(p_projection->>'occurred_at', '')::timestamptz;
    projection_plan := nullif(p_projection->>'plan', '');
    projection_status := nullif(p_projection->>'status', '');
    projection_product_id := nullif(p_projection->>'product_id', '');
    projection_billing_period := nullif(p_projection->>'billing_period', '');
    projection_started_at := nullif(p_projection->>'started_at', '')::timestamptz;
    projection_expires_at := nullif(p_projection->>'expires_at', '')::timestamptz;
    projection_grace_expires_at := nullif(p_projection->>'grace_expires_at', '')::timestamptz;
    projection_revoked_at := nullif(p_projection->>'revoked_at', '')::timestamptz;
    projection_refunded_at := nullif(p_projection->>'refunded_at', '')::timestamptz;
    projection_original_transaction_id := nullif(p_projection->>'original_transaction_id', '');
    projection_purchase_token_hash := nullif(p_projection->>'purchase_token_hash', '');
    projection_environment := nullif(p_projection->>'environment', '');
    projection_metadata := coalesce(p_projection->'metadata', '{}'::jsonb);

    if projection_user_id is null
       or projection_source not in (
           'apple_subscription',
           'google_play_subscription',
           'google_play_legacy',
           'admin'
       )
       or projection_event_id is null
       or projection_entitlement_id is null
       or projection_event_type is null
       or projection_fingerprint is null
       or projection_fingerprint !~ '^[0-9a-f]{64}$'
       or projection_occurred_at is null
       or projection_plan not in ('free', 'plus', 'lifetime')
       or projection_status not in ('active', 'grace', 'canceled', 'expired', 'revoked', 'refunded')
       or jsonb_typeof(projection_metadata) <> 'object' then
        raise exception 'Entitlement projection is incomplete or invalid.' using errcode = '22023';
    end if;

    -- Serializes duplicate notifications and out-of-order transaction updates.
    perform pg_advisory_xact_lock(
        hashtextextended(projection_source || ':' || projection_entitlement_id, 0)
    );

    select event.* into existing_event
    from public.app_entitlement_events as event
    where event.source = projection_source
      and event.external_event_id = projection_event_id
    for update;

    if found then
        if existing_event.event_fingerprint <> projection_fingerprint then
            raise exception 'Entitlement event ID was reused for different verified data.'
                using errcode = '22023';
        end if;
        return jsonb_build_object(
            'applied', false,
            'duplicate', true,
            'stale', false,
            'entitlement_id', existing_event.entitlement_id,
            'event_id', existing_event.id
        );
    end if;

    select current_entitlement.* into entitlement
    from public.app_entitlements as current_entitlement
    where current_entitlement.source = projection_source
      and current_entitlement.external_entitlement_id = projection_entitlement_id
    for update;

    if found and entitlement.user_id <> projection_user_id then
        raise exception 'Verified store entitlement is already linked to another HikeJournal account.'
            using errcode = '23505';
    end if;

    if not found then
        insert into public.app_entitlements (
            user_id,
            plan,
            source,
            external_entitlement_id,
            product_id,
            billing_period,
            status,
            started_at,
            expires_at,
            grace_expires_at,
            revoked_at,
            refunded_at,
            original_transaction_id,
            purchase_token_hash,
            environment,
            last_event_at,
            metadata
        ) values (
            projection_user_id,
            projection_plan,
            projection_source,
            projection_entitlement_id,
            projection_product_id,
            projection_billing_period,
            projection_status,
            projection_started_at,
            projection_expires_at,
            projection_grace_expires_at,
            projection_revoked_at,
            projection_refunded_at,
            projection_original_transaction_id,
            projection_purchase_token_hash,
            projection_environment,
            projection_occurred_at,
            projection_metadata
        ) returning id into entitlement_row_id;
    else
        entitlement_row_id := entitlement.id;
        should_apply := projection_occurred_at > entitlement.last_event_at
            or (
                projection_occurred_at = entitlement.last_event_at
                and case projection_status
                    when 'refunded' then 60
                    when 'revoked' then 50
                    when 'expired' then 40
                    when 'canceled' then 30
                    when 'grace' then 20
                    else 10
                end >= case entitlement.status
                    when 'refunded' then 60
                    when 'revoked' then 50
                    when 'expired' then 40
                    when 'canceled' then 30
                    when 'grace' then 20
                    else 10
                end
            );
        if should_apply then
            update public.app_entitlements as current_entitlement
            set plan = projection_plan,
                product_id = projection_product_id,
                billing_period = projection_billing_period,
                status = projection_status,
                started_at = projection_started_at,
                expires_at = projection_expires_at,
                grace_expires_at = projection_grace_expires_at,
                revoked_at = projection_revoked_at,
                refunded_at = projection_refunded_at,
                original_transaction_id = projection_original_transaction_id,
                purchase_token_hash = projection_purchase_token_hash,
                environment = projection_environment,
                last_event_at = projection_occurred_at,
                metadata = projection_metadata,
                updated_at = timezone('utc', now())
            where current_entitlement.id = entitlement_row_id;
        end if;
    end if;

    insert into public.app_entitlement_events (
        user_id,
        entitlement_id,
        source,
        external_event_id,
        event_type,
        event_fingerprint,
        occurred_at,
        metadata
    ) values (
        projection_user_id,
        entitlement_row_id,
        projection_source,
        projection_event_id,
        projection_event_type,
        projection_fingerprint,
        projection_occurred_at,
        projection_metadata
    ) returning id into existing_event.id;

    return jsonb_build_object(
        'applied', should_apply,
        'duplicate', false,
        'stale', not should_apply,
        'entitlement_id', entitlement_row_id,
        'event_id', existing_event.id
    );
end;
$$;

alter table public.app_entitlement_policies enable row level security;
alter table public.app_entitlements enable row level security;
alter table public.app_entitlement_events enable row level security;
alter table public.app_quota_reservations enable row level security;
alter table public.app_entitlement_policies force row level security;
alter table public.app_entitlements force row level security;
alter table public.app_entitlement_events force row level security;
alter table public.app_quota_reservations force row level security;

revoke all privileges on table public.app_entitlement_policies from anon, authenticated;
revoke all privileges on table public.app_entitlements from anon, authenticated;
revoke all privileges on table public.app_entitlement_events from anon, authenticated;
revoke all privileges on table public.app_quota_reservations from anon, authenticated;
grant select on table public.app_entitlement_policies to service_role;
grant all privileges on table public.app_entitlements to service_role;
grant all privileges on table public.app_entitlement_events to service_role;
grant all privileges on table public.app_quota_reservations to service_role;

revoke execute on function public.effective_app_entitlement_plan(uuid, timestamptz)
from public, anon, authenticated;
revoke execute on function public.app_quota_usage(uuid, text)
from public, anon, authenticated;
revoke execute on function public.app_quota_reserved_usage(uuid, text, timestamptz)
from public, anon, authenticated;
revoke execute on function public.reserve_app_quota(uuid, text, text, uuid, integer)
from public, anon, authenticated;
revoke execute on function public.release_app_quota_reservation(uuid, text, text)
from public, anon, authenticated;
revoke execute on function public.apply_app_entitlement_event(jsonb)
from public, anon, authenticated;
revoke execute on function public.fill_owner_user_id_from_legacy_subject()
from public, anon, authenticated;
revoke execute on function public.sync_app_quota_reservation()
from public, anon, authenticated;

grant execute on function public.effective_app_entitlement_plan(uuid, timestamptz)
to service_role;
grant execute on function public.app_quota_usage(uuid, text)
to service_role;
grant execute on function public.app_quota_reserved_usage(uuid, text, timestamptz)
to service_role;
grant execute on function public.reserve_app_quota(uuid, text, text, uuid, integer)
to service_role;
grant execute on function public.release_app_quota_reservation(uuid, text, text)
to service_role;
grant execute on function public.apply_app_entitlement_event(jsonb)
to service_role;

comment on table public.app_entitlements is
'Server-managed account access. Store purchase state is evidence; this table is HikeJournal access authority.';
comment on table public.app_entitlement_events is
'Idempotent audit ledger for verified provider/admin events; raw signed payloads and purchase tokens are not stored.';
comment on table public.app_quota_reservations is
'Short transactional reservations that serialize Free cloud limits before resource creation; deletion releases committed rows.';
comment on column public.app_entitlements.purchase_token_hash is
'HMAC-SHA256 of verified Google purchase/license evidence; never a raw token or client ownership boolean.';
