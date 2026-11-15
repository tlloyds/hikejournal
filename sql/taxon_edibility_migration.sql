-- Shared food-use references. Observation data is never copied into these tables.
begin;

create table if not exists public.edibility_source_releases (
    id uuid primary key default gen_random_uuid(),
    source_key text not null,
    version text not null,
    doi text not null,
    title text not null,
    attribution text not null,
    publisher text not null,
    license text not null,
    license_url text not null,
    archive_sha256 text not null check (archive_sha256 ~ '^[a-f0-9]{64}$'),
    modifications text not null,
    evidence_count integer not null check (evidence_count > 0),
    imported_at timestamptz not null default now(),
    active boolean not null default false,
    unique (source_key, version)
);
create unique index if not exists edibility_one_active_release_per_source
    on public.edibility_source_releases (source_key) where active;

create table if not exists public.taxon_food_use_evidence (
    release_id uuid not null references public.edibility_source_releases(id),
    record_key text not null,
    source_taxon_id text,
    scientific_name text not null,
    normalized_name text not null,
    authority text,
    rank text not null,
    family text not null,
    evidence_types text[] not null check (
        cardinality(evidence_types) > 0 and evidence_types <@ array[
            'food_documented', 'food_conditional', 'food_disputed', 'toxicity_concern', 'poison_use'
        ]
    ),
    parts text[] not null default '{}',
    food_use_notes text,
    toxicity_notes text,
    source_references jsonb not null,
    provenance jsonb not null,
    primary key (release_id, record_key)
);
create index if not exists taxon_food_use_name_idx
    on public.taxon_food_use_evidence (release_id, normalized_name);

create table if not exists public.taxon_edibility_profiles (
    release_id uuid not null references public.edibility_source_releases(id),
    taxon_id bigint not null check (taxon_id > 0),
    validated_at timestamptz not null,
    payload jsonb,
    primary key (release_id, taxon_id),
    check (payload is null or (
        payload ?& array['scientific_name', 'rank', 'food_use_status', 'toxicity_status',
                          'review_status', 'evidence_conflict', 'record_keys']
        and payload->>'rank' in ('species', 'subspecies', 'variety', 'form')
        and payload->>'food_use_status' in ('documented', 'conditional', 'disputed', 'unknown')
        and payload->>'toxicity_status' in ('documented_concern', 'unknown')
        and payload->>'review_status' in ('source_matched', 'reviewed')
        and jsonb_typeof(payload->'record_keys') = 'array'
        and jsonb_array_length(payload->'record_keys') > 0
    ))
);

create table if not exists public.taxon_edibility_matches (
    release_id uuid not null,
    taxon_id bigint not null,
    record_key text not null,
    accepted_name text not null,
    rank text not null,
    match_method text check (match_method in (
        'verified_identifier', 'exact_accepted_name', 'verified_synonym', 'manual_review'
    )),
    review_status text not null check (review_status in (
        'source_matched', 'reviewed', 'needs_review', 'rejected'
    )),
    reason text not null,
    review_basis jsonb check (review_basis is null or jsonb_typeof(review_basis) = 'object'),
    updated_at timestamptz not null default now(),
    primary key (release_id, taxon_id, record_key),
    foreign key (release_id, record_key)
        references public.taxon_food_use_evidence (release_id, record_key),
    foreign key (release_id, taxon_id)
        references public.taxon_edibility_profiles (release_id, taxon_id),
    check (review_status not in ('source_matched', 'reviewed') or match_method is not null)
);
create index if not exists taxon_edibility_match_evidence_idx
    on public.taxon_edibility_matches (release_id, record_key);
create index if not exists species_observations_edibility_taxon_idx
    on public.species_observations (taxon_id) where status = 'confirmed' and taxon_id is not null;

do $$
declare relation text;
begin
    foreach relation in array array[
        'edibility_source_releases', 'taxon_food_use_evidence',
        'taxon_edibility_matches', 'taxon_edibility_profiles'
    ] loop
        execute format('alter table public.%I enable row level security', relation);
        execute format('alter table public.%I force row level security', relation);
        execute format('revoke all on table public.%I from public, anon, authenticated', relation);
        execute format('grant all on table public.%I to service_role', relation);
    end loop;
end $$;

-- Activation and rollback publish an entire validated release in one transaction.
create or replace function public.set_edibility_release(p_release_id uuid, p_active boolean)
returns void language plpgsql security invoker set search_path = '' as $$
declare release_row public.edibility_source_releases;
begin
    select * into strict release_row from public.edibility_source_releases where id = p_release_id;
    perform pg_advisory_xact_lock(hashtext(release_row.source_key));
    if p_active then
        if release_row.evidence_count <> (
            select count(*) from public.taxon_food_use_evidence where release_id = p_release_id
        ) then
            raise exception 'Incomplete evidence import';
        end if;
        update public.edibility_source_releases set active = false
        where source_key = release_row.source_key and active and id <> p_release_id;
    end if;
    update public.edibility_source_releases set active = p_active where id = p_release_id;
end $$;

-- Persist audit decisions and replace their canonical profile atomically. A null
-- payload also records a completed assessment so an earlier job cannot restore it.
create or replace function public.save_edibility_assessments(
    p_release_id uuid, p_validated_at timestamptz, p_assessments jsonb
) returns void language plpgsql security invoker set search_path = '' as $$
declare assessment jsonb;
declare target_id bigint;
begin
    if p_validated_at > now() then
        raise exception 'Assessment timestamp must not be in the future';
    end if;
    for assessment in
        select value from jsonb_array_elements(p_assessments) order by (value->>'taxon_id')::bigint
    loop
        target_id := (assessment->>'taxon_id')::bigint;
        insert into public.taxon_edibility_profiles (release_id, taxon_id, validated_at, payload)
        values (p_release_id, target_id, p_validated_at, nullif(assessment->'profile', 'null'::jsonb))
        on conflict (release_id, taxon_id) do update
        set validated_at = excluded.validated_at, payload = excluded.payload
        where public.taxon_edibility_profiles.validated_at < excluded.validated_at;
        if found then
            if exists (
                select 1 from public.taxon_edibility_matches m
                where m.release_id = p_release_id and m.taxon_id = target_id and m.review_basis is not null
                  and not exists (
                      select 1 from jsonb_array_elements(assessment->'matches') as incoming(item)
                      where incoming.item->>'record_key' = m.record_key
                        and jsonb_typeof(incoming.item->'review_basis') = 'object'
                  )
            ) then
                raise exception 'Assessment omitted a stored review decision';
            end if;
            delete from public.taxon_edibility_matches
            where release_id = p_release_id and taxon_id = target_id;
            insert into public.taxon_edibility_matches (
                release_id, taxon_id, record_key, accepted_name, rank, match_method, review_status, reason, review_basis
            )
            select p_release_id, target_id, match.record_key, match.accepted_name, match.rank,
                   match.match_method, match.review_status, match.reason, match.review_basis
            from jsonb_to_recordset(assessment->'matches') as match(
                record_key text, accepted_name text, rank text, match_method text,
                review_status text, reason text, review_basis jsonb
            );
            if jsonb_typeof(assessment->'profile') = 'object' and exists (
                select 1 from jsonb_array_elements_text(assessment->'profile'->'record_keys') as record(key)
                where not exists (
                    select 1 from public.taxon_edibility_matches m
                    where m.release_id = p_release_id and m.taxon_id = target_id
                      and m.record_key = record.key and m.review_status in ('source_matched', 'reviewed')
                )
            ) then
                raise exception 'Profile evidence must have a current accepted match';
            end if;
        end if;
    end loop;
end $$;

create or replace function public.edibility_observed_taxa(p_after bigint, p_limit integer)
returns table (taxon_id bigint, enrichment jsonb)
language sql stable security invoker set search_path = '' as $$
    select distinct on (s.taxon_id)
        s.taxon_id, s.raw_response_json->'taxon_enrichment'
    from public.species_observations s
    where s.status = 'confirmed' and s.taxon_id is not null and s.taxon_id > p_after
    order by s.taxon_id, (s.raw_response_json->'taxon_enrichment' is not null) desc,
        s.identified_at desc nulls last, s.id
    limit least(greatest(p_limit, 1), 100)
$$;

-- Read the release and its profiles together. Keep the initial allowlist
-- limited to WCFP so staging other datasets cannot expose them to clients.
create or replace function public.current_edibility_reference(p_taxon_ids bigint[])
returns jsonb language sql stable security invoker set search_path = '' as $$
    select jsonb_build_object(
        'release_id', r.id,
        'source', jsonb_build_object(
            'title', r.title, 'version', r.version, 'url', 'https://doi.org/' || r.doi,
            'attribution', r.attribution, 'publisher', r.publisher, 'license', r.license,
            'license_url', r.license_url, 'modifications', r.modifications
        ),
        'profiles', coalesce((
            select jsonb_object_agg(p.taxon_id, p.payload || jsonb_build_object(
                'updated_at', p.validated_at,
                'expires_at', least(now() + interval '24 hours', p.validated_at + interval '30 days')
            ))
            from public.taxon_edibility_profiles p
            where p.release_id = r.id and p.taxon_id = any(p_taxon_ids)
              and p.payload is not null and p.validated_at > now() - interval '30 days'
        ), '{}'::jsonb)
    )
    from public.edibility_source_releases r where r.active and r.source_key = 'wcfp'
$$;

revoke all on function public.set_edibility_release(uuid, boolean),
    public.save_edibility_assessments(uuid, timestamptz, jsonb),
    public.edibility_observed_taxa(bigint, integer),
    public.current_edibility_reference(bigint[]) from public, anon, authenticated;
grant execute on function public.set_edibility_release(uuid, boolean),
    public.save_edibility_assessments(uuid, timestamptz, jsonb),
    public.edibility_observed_taxa(bigint, integer),
    public.current_edibility_reference(bigint[]) to service_role;

commit;
