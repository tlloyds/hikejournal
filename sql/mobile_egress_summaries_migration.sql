-- Compact, owner-scoped database results for the native journal archive.
-- This replaces large PostgREST photo/observation row sets on summary reads;
-- photo detail remains paged and uses explicit column projections.

begin;

create or replace function public.hikejournal_mobile_owner_visible(
    p_record jsonb,
    p_owner_user_id text,
    p_owner_subject text,
    p_owner_email text,
    p_identity_provider text,
    p_include_all boolean,
    p_allow_legacy_email boolean
)
returns boolean
language sql
immutable
parallel safe
set search_path = public
as $$
    select coalesce(p_include_all, false)
        or case
            when nullif(trim(coalesce(p_record ->> 'owner_user_id', '')), '') is not null
                then nullif(trim(coalesce(p_owner_user_id, '')), '') is not null
                    and trim(p_record ->> 'owner_user_id') = trim(p_owner_user_id)
            when nullif(trim(coalesce(p_record ->> 'owner_subject', '')), '') is not null
                then nullif(trim(coalesce(p_owner_subject, '')), '') is not null
                    and trim(p_record ->> 'owner_subject') = trim(p_owner_subject)
            when coalesce(p_allow_legacy_email, false)
                then nullif(lower(trim(coalesce(p_record ->> 'owner_email', ''))), '') is not null
                    and lower(trim(coalesce(p_record ->> 'owner_email', '')))
                        = lower(trim(coalesce(p_owner_email, '')))
            else false
        end;
$$;

create or replace function public.mobile_hike_library_summaries(
    p_hike_ids uuid[],
    p_owner_user_id text,
    p_owner_subject text,
    p_owner_email text,
    p_identity_provider text,
    p_include_all boolean,
    p_allow_legacy_email boolean
)
returns table (
    hike_id uuid,
    photo_count bigint,
    id uuid,
    public_url text,
    storage_path text,
    thumbnail_storage_path text,
    taken_at timestamptz,
    created_at timestamptz,
    species_count bigint
)
language sql
stable
set search_path = public
as $$
    with requested as (
        select hike.id, hike.cover_photo_id
        from unnest(coalesce(p_hike_ids, array[]::uuid[])) as requested(hike_id)
        join public.hikes as hike on hike.id = requested.hike_id
    ), photo_counts as (
        select photo.hike_id, count(*)::bigint as photo_count
        from public.photos as photo
        join requested on requested.id = photo.hike_id
        group by photo.hike_id
    ), covers as (
        select distinct on (photo.hike_id)
            photo.hike_id,
            photo.id,
            photo.public_url,
            photo.storage_path,
            photo.exif_json ->> 'hikejournal_thumbnail_storage_path' as thumbnail_storage_path,
            photo.taken_at,
            photo.created_at
        from public.photos as photo
        join requested on requested.id = photo.hike_id
        where requested.cover_photo_id is null
           or photo.id = requested.cover_photo_id
        order by
            photo.hike_id,
            photo.taken_at desc nulls last,
            photo.created_at desc nulls last,
            photo.id desc
    ), observation_keys as (
        select
            observation.hike_id as resolved_hike_id,
            case
                when coalesce(observation.species_taxon_id, observation.taxon_id) is not null
                    then 'taxon:' || coalesce(observation.species_taxon_id, observation.taxon_id)::text
                when nullif(trim(coalesce(observation.scientific_name, '')), '') is not null
                    then 'scientific:' || lower(trim(observation.scientific_name))
                else 'common:' || lower(coalesce(nullif(trim(observation.common_name), ''), 'unknown'))
            end as species_key
        from public.species_observations as observation
        join requested on requested.id = observation.hike_id
        where observation.status = 'confirmed'

        union all

        select
            photo.hike_id as resolved_hike_id,
            case
                when coalesce(observation.species_taxon_id, observation.taxon_id) is not null
                    then 'taxon:' || coalesce(observation.species_taxon_id, observation.taxon_id)::text
                when nullif(trim(coalesce(observation.scientific_name, '')), '') is not null
                    then 'scientific:' || lower(trim(observation.scientific_name))
                else 'common:' || lower(coalesce(nullif(trim(observation.common_name), ''), 'unknown'))
            end as species_key
        from public.species_observations as observation
        join public.photos as photo on photo.id = observation.photo_id
        join requested on requested.id = photo.hike_id
        where observation.status = 'confirmed'
          and observation.hike_id is null
          and public.hikejournal_mobile_owner_visible(
              to_jsonb(observation),
              p_owner_user_id,
              p_owner_subject,
              p_owner_email,
              p_identity_provider,
              p_include_all,
              p_allow_legacy_email
          )
    ), species_counts as (
        select observation.resolved_hike_id, count(distinct observation.species_key)::bigint as species_count
        from observation_keys as observation
        group by observation.resolved_hike_id
    )
    select
        requested.id as hike_id,
        coalesce(photo_counts.photo_count, 0)::bigint as photo_count,
        covers.id,
        covers.public_url,
        covers.storage_path,
        covers.thumbnail_storage_path,
        covers.taken_at,
        covers.created_at,
        coalesce(species_counts.species_count, 0)::bigint as species_count
    from requested
    left join photo_counts on photo_counts.hike_id = requested.id
    left join covers on covers.hike_id = requested.id
    left join species_counts on species_counts.resolved_hike_id = requested.id;
$$;

create or replace function public.mobile_standalone_library_summary(
    p_owner_user_id text,
    p_owner_subject text,
    p_owner_email text,
    p_identity_provider text,
    p_include_all boolean,
    p_allow_legacy_email boolean
)
returns table (
    photo_count bigint,
    species_count bigint,
    latest_date text,
    cover_photo_id uuid,
    public_url text,
    storage_path text,
    thumbnail_storage_path text
)
language sql
stable
set search_path = public
as $$
    with visible_photos as (
        select photo.*
        from public.photos as photo
        where photo.hike_id is null
          and public.hikejournal_mobile_owner_visible(
              to_jsonb(photo),
              p_owner_user_id,
              p_owner_subject,
              p_owner_email,
              p_identity_provider,
              p_include_all,
              p_allow_legacy_email
          )
    ), photo_stats as (
        select count(*)::bigint as photo_count from visible_photos
    ), latest_photo as (
        select coalesce(photo.taken_at, photo.created_at)::text as latest_date
        from visible_photos as photo
        where photo.taken_at is not null or photo.created_at is not null
        order by photo.taken_at desc nulls first, photo.created_at desc nulls first, photo.id desc
        limit 1
    ), cover as (
        select
            photo.id as cover_photo_id,
            photo.public_url,
            photo.storage_path,
            photo.exif_json ->> 'hikejournal_thumbnail_storage_path' as thumbnail_storage_path
        from visible_photos as photo
        order by photo.taken_at desc nulls last, photo.created_at desc nulls last, photo.id desc
        limit 1
    ), observation_keys as (
        select case
            when coalesce(observation.species_taxon_id, observation.taxon_id) is not null
                then 'taxon:' || coalesce(observation.species_taxon_id, observation.taxon_id)::text
            when nullif(trim(coalesce(observation.scientific_name, '')), '') is not null
                then 'scientific:' || lower(trim(observation.scientific_name))
            else 'common:' || lower(coalesce(nullif(trim(observation.common_name), ''), 'unknown'))
        end as species_key
        from public.species_observations as observation
        join visible_photos as photo on photo.id = observation.photo_id
        where observation.status = 'confirmed'
          and observation.hike_id is null
          and public.hikejournal_mobile_owner_visible(
              to_jsonb(observation),
              p_owner_user_id,
              p_owner_subject,
              p_owner_email,
              p_identity_provider,
              p_include_all,
              p_allow_legacy_email
          )
    ), species_stats as (
        select count(distinct species_key)::bigint as species_count from observation_keys
    )
    select
        photo_stats.photo_count,
        species_stats.species_count,
        latest_photo.latest_date,
        cover.cover_photo_id,
        cover.public_url,
        cover.storage_path,
        cover.thumbnail_storage_path
    from photo_stats
    cross join species_stats
    left join latest_photo on true
    left join cover on true;
$$;

create or replace function public.mobile_standalone_photo_page(
    p_offset integer,
    p_limit integer,
    p_owner_user_id text,
    p_owner_subject text,
    p_owner_email text,
    p_identity_provider text,
    p_include_all boolean,
    p_allow_legacy_email boolean
)
returns table (
    id uuid,
    hike_id uuid,
    owner_subject text,
    owner_email text,
    caption text,
    public_url text,
    storage_path text,
    lat double precision,
    lng double precision,
    taken_at timestamptz,
    created_at timestamptz,
    width integer,
    height integer,
    content_type text,
    processing_status text,
    thumbnail_storage_path text
)
language sql
stable
set search_path = public
as $$
    select
        photo.id,
        photo.hike_id,
        photo.owner_subject,
        photo.owner_email,
        photo.caption,
        photo.public_url,
        photo.storage_path,
        photo.lat,
        photo.lng,
        photo.taken_at,
        photo.created_at,
        photo.width,
        photo.height,
        photo.content_type,
        photo.processing_status,
        photo.exif_json ->> 'hikejournal_thumbnail_storage_path' as thumbnail_storage_path
    from public.photos as photo
    where photo.hike_id is null
      and public.hikejournal_mobile_owner_visible(
          to_jsonb(photo),
          p_owner_user_id,
          p_owner_subject,
          p_owner_email,
          p_identity_provider,
          p_include_all,
          p_allow_legacy_email
      )
    order by photo.taken_at desc nulls first, photo.created_at desc nulls first, photo.id desc
    offset greatest(coalesce(p_offset, 0), 0)
    limit greatest(least(coalesce(p_limit, 50), 100), 1);
$$;

revoke all on function public.hikejournal_mobile_owner_visible(jsonb, text, text, text, text, boolean, boolean)
    from public, anon, authenticated;
revoke all on function public.mobile_hike_library_summaries(uuid[], text, text, text, text, boolean, boolean)
    from public, anon, authenticated;
revoke all on function public.mobile_standalone_library_summary(text, text, text, text, boolean, boolean)
    from public, anon, authenticated;
revoke all on function public.mobile_standalone_photo_page(integer, integer, text, text, text, text, boolean, boolean)
    from public, anon, authenticated;

grant execute on function public.hikejournal_mobile_owner_visible(jsonb, text, text, text, text, boolean, boolean)
    to service_role;
grant execute on function public.mobile_hike_library_summaries(uuid[], text, text, text, text, boolean, boolean)
    to service_role;
grant execute on function public.mobile_standalone_library_summary(text, text, text, text, boolean, boolean)
    to service_role;
grant execute on function public.mobile_standalone_photo_page(integer, integer, text, text, text, text, boolean, boolean)
    to service_role;

notify pgrst, 'reload schema';

commit;
