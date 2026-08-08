-- Durable state for mobile identification and iNaturalist publishing batches.
-- Only the server-side service role can see or mutate these request payloads.
create extension if not exists pgcrypto;

create table if not exists public.mobile_api_jobs (
    id uuid primary key default gen_random_uuid(),
    job_type text not null check (char_length(job_type) between 1 and 80),
    owner_scope text not null default 'single-owner'
        check (char_length(owner_scope) between 1 and 80),
    owner_key text not null check (char_length(owner_key) = 64),
    client_request_id text,
    state text not null default 'queued'
        check (state in ('queued', 'running', 'completed', 'failed', 'cancelled')),
    payload jsonb not null default '{}'::jsonb,
    request_payload jsonb not null default '{}'::jsonb,
    request_fingerprint text,
    attempt_count integer not null default 0 check (attempt_count >= 0),
    max_attempts integer not null default 3 check (max_attempts between 1 and 20),
    next_attempt_at timestamptz,
    lease_owner text,
    lease_expires_at timestamptz,
    last_error text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    completed_at timestamptz,
    check (client_request_id is null or char_length(client_request_id) between 1 and 64),
    check (request_fingerprint is null or char_length(request_fingerprint) = 64)
);

alter table public.mobile_api_jobs
add column if not exists request_fingerprint text;

create unique index if not exists mobile_api_jobs_request_idempotency_idx
on public.mobile_api_jobs (job_type, owner_scope, owner_key, client_request_id)
where client_request_id is not null;

create index if not exists mobile_api_jobs_recovery_idx
on public.mobile_api_jobs (state, next_attempt_at, lease_expires_at, created_at)
where state in ('queued', 'running', 'failed');

drop function if exists public.update_mobile_api_job(uuid, jsonb);

create or replace function public.update_mobile_api_job(
    p_job_id uuid,
    p_payload_updates jsonb,
    p_expected_lease_owner text default null,
    p_lease_seconds integer default 1800
) returns setof public.mobile_api_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
    if p_payload_updates is null or jsonb_typeof(p_payload_updates) <> 'object' then
        raise exception 'Job payload updates must be a JSON object.';
    end if;

    return query
    update public.mobile_api_jobs as job
    set payload = job.payload || p_payload_updates,
        state = coalesce(nullif(p_payload_updates->>'state', ''), job.state),
        last_error = case
            when p_payload_updates ? 'error'
                then nullif(p_payload_updates->>'error', '')
            else job.last_error
        end,
        lease_owner = case
            when p_payload_updates ? 'state'
                and coalesce(nullif(p_payload_updates->>'state', ''), job.state)
                in ('completed', 'failed', 'cancelled') then null
            else job.lease_owner
        end,
        lease_expires_at = case
            when p_payload_updates ? 'state'
                and coalesce(nullif(p_payload_updates->>'state', ''), job.state)
                in ('completed', 'failed', 'cancelled') then null
            when p_expected_lease_owner is not null then
                timezone('utc', now())
                + make_interval(secs => greatest(1, least(coalesce(p_lease_seconds, 1800), 3600)))
            else job.lease_expires_at
        end,
        next_attempt_at = case
            when p_payload_updates ? 'state'
                and coalesce(nullif(p_payload_updates->>'state', ''), job.state)
                in ('completed', 'failed', 'cancelled')
                then null
            else job.next_attempt_at
        end,
        completed_at = case
            when p_payload_updates ? 'state'
                and coalesce(nullif(p_payload_updates->>'state', ''), job.state)
                in ('completed', 'failed', 'cancelled')
                then coalesce(job.completed_at, timezone('utc', now()))
            else job.completed_at
        end,
        updated_at = timezone('utc', now())
    where job.id = p_job_id
      and (
          p_expected_lease_owner is null
          or (
              job.state = 'running'
              and job.lease_owner = p_expected_lease_owner
          )
      )
    returning job.*;
end;
$$;

create or replace function public.claim_mobile_api_job(
    p_job_id uuid,
    p_lease_owner text,
    p_lease_seconds integer default 300
) returns setof public.mobile_api_jobs
language plpgsql
security definer
set search_path = public
as $$
begin
    if coalesce(trim(p_lease_owner), '') = '' then
        raise exception 'A lease owner is required.';
    end if;

    return query
    update public.mobile_api_jobs as job
    set state = 'running',
        payload = jsonb_set(job.payload, '{state}', to_jsonb('running'::text), true),
        attempt_count = job.attempt_count + 1,
        next_attempt_at = null,
        lease_owner = p_lease_owner,
        lease_expires_at = timezone('utc', now())
            + make_interval(secs => greatest(1, least(coalesce(p_lease_seconds, 300), 3600))),
        updated_at = timezone('utc', now())
    where job.id = p_job_id
      and job.attempt_count < job.max_attempts
      and (
          job.state = 'queued'
          or (
              job.state = 'failed'
              and job.next_attempt_at is not null
              and job.next_attempt_at <= timezone('utc', now())
          )
          or (
              job.state = 'running'
              and job.lease_expires_at is not null
              and job.lease_expires_at <= timezone('utc', now())
          )
      )
    returning job.*;
end;
$$;

create or replace function public.fail_expired_mobile_api_job(
    p_job_id uuid,
    p_expected_lease_owner text,
    p_error text
) returns setof public.mobile_api_jobs
language plpgsql
security definer
set search_path = public
as $$
declare
    failure_message text := coalesce(
        nullif(p_error, ''),
        'The background worker stopped after its lease expired.'
    );
begin
    if coalesce(trim(p_expected_lease_owner), '') = '' then
        raise exception 'An expected lease owner is required.';
    end if;

    return query
    update public.mobile_api_jobs as job
    set payload = job.payload || jsonb_build_object(
            'state', 'failed',
            'error', failure_message
        ),
        state = 'failed',
        last_error = failure_message,
        lease_owner = null,
        lease_expires_at = null,
        next_attempt_at = null,
        completed_at = coalesce(job.completed_at, timezone('utc', now())),
        updated_at = timezone('utc', now())
    where job.id = p_job_id
      and job.state = 'running'
      and job.lease_owner = p_expected_lease_owner
      and job.lease_expires_at is not null
      and job.lease_expires_at <= timezone('utc', now())
    returning job.*;
end;
$$;

alter table public.mobile_api_jobs enable row level security;
alter table public.mobile_api_jobs force row level security;

revoke all privileges on table public.mobile_api_jobs from anon, authenticated;
grant all privileges on table public.mobile_api_jobs to service_role;
revoke execute on function public.update_mobile_api_job(uuid, jsonb, text, integer)
from public, anon, authenticated;
grant execute on function public.update_mobile_api_job(uuid, jsonb, text, integer)
to service_role;
revoke execute on function public.claim_mobile_api_job(uuid, text, integer)
from public, anon, authenticated;
grant execute on function public.claim_mobile_api_job(uuid, text, integer)
to service_role;
revoke execute on function public.fail_expired_mobile_api_job(uuid, text, text)
from public, anon, authenticated;
grant execute on function public.fail_expired_mobile_api_job(uuid, text, text)
to service_role;
