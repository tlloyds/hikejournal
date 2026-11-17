-- Track shared reference lookups by taxon. No observation IDs or owners are stored.
begin;

create table if not exists public.taxon_edibility_lookups (
    taxon_id bigint primary key check (taxon_id > 0),
    claimed_at timestamptz not null,
    checked_at timestamptz,
    catalog_version text,
    source_release_id uuid references public.edibility_source_releases(id),
    reference jsonb check (reference is null or jsonb_typeof(reference) = 'object')
);

alter table public.taxon_edibility_lookups enable row level security;
alter table public.taxon_edibility_lookups force row level security;
revoke all on table public.taxon_edibility_lookups from public, anon, authenticated;
grant all on table public.taxon_edibility_lookups to service_role;

create or replace function public.claim_edibility_lookups(
    p_taxon_ids bigint[], p_catalog_version text, p_limit integer
) returns table (taxon_id bigint, claimed_at timestamptz, release_id uuid)
language sql volatile security invoker set search_path = '' as $$
    with source as (
        select (select r.id from public.edibility_source_releases r
                where r.active and r.source_key = 'wcfp') as release_id
    ), due as (
        select requested.id
        from (
            select id, min(priority) as priority
            from unnest(p_taxon_ids) with ordinality as input(id, priority)
            group by id
        ) requested
        left join public.taxon_edibility_lookups l on l.taxon_id = requested.id
        cross join source
        where (l.claimed_at is null or l.claimed_at <= statement_timestamp() - interval '90 seconds')
          and (l.checked_at is null or l.checked_at <= statement_timestamp() - interval '14 days'
              or l.catalog_version is distinct from p_catalog_version
              or l.source_release_id is distinct from source.release_id)
          and exists (
              select 1 from public.species_observations s
              where s.taxon_id = requested.id and s.status = 'confirmed'
          )
        order by requested.priority
        limit least(greatest(p_limit, 1), 8)
    ), claimed as (
        insert into public.taxon_edibility_lookups as l (taxon_id, claimed_at)
        select due.id, statement_timestamp() from due order by due.id
        on conflict on constraint taxon_edibility_lookups_pkey do update set claimed_at = excluded.claimed_at
        where l.claimed_at <= excluded.claimed_at - interval '90 seconds'
        returning l.taxon_id, l.claimed_at
    )
    select claimed.taxon_id, claimed.claimed_at, source.release_id
    from claimed cross join source
$$;

create or replace function public.finish_edibility_lookup(
    p_taxon_id bigint, p_claimed_at timestamptz, p_catalog_version text, p_release_id uuid,
    p_reference jsonb, p_assessment jsonb
) returns void language plpgsql security invoker set search_path = '' as $$
begin
    update public.taxon_edibility_lookups
    set checked_at = p_claimed_at, catalog_version = p_catalog_version, source_release_id = p_release_id,
        reference = nullif(p_reference, 'null'::jsonb)
    where taxon_id = p_taxon_id and claimed_at = p_claimed_at;
    if found and p_release_id is not null then
        if (p_assessment->>'taxon_id')::bigint is distinct from p_taxon_id then
            raise exception 'Assessment taxon must match its claim';
        end if;
        perform public.save_edibility_assessments(p_release_id, p_claimed_at, jsonb_build_array(p_assessment));
    end if;
end $$;

revoke all on function public.claim_edibility_lookups(bigint[], text, integer),
    public.finish_edibility_lookup(bigint, timestamptz, text, uuid, jsonb, jsonb) from public, anon, authenticated;
grant execute on function public.claim_edibility_lookups(bigint[], text, integer),
    public.finish_edibility_lookup(bigint, timestamptz, text, uuid, jsonb, jsonb) to service_role;

commit;
