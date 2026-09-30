-- Return only the current account's geotagged map pins and their primary
-- confirmed species. Route geometry is fetched through a separate, scoped
-- projection by the mobile API.

begin;

create or replace function public.mobile_map_sightings(
    p_hike_ids uuid[],
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
    caption text,
    public_url text,
    storage_path text,
    thumbnail_storage_path text,
    taken_at timestamptz,
    created_at timestamptz,
    lat double precision,
    lng double precision,
    species_name text,
    scientific_name text,
    confirmed boolean
)
language sql
stable
set search_path = public
as $$
with visible_hikes as (
    select hike.id
    from public.hikes as hike
    where hike.id = any(coalesce(p_hike_ids, array[]::uuid[]))
      and public.hikejournal_mobile_owner_visible(
          to_jsonb(hike),
          p_owner_user_id,
          p_owner_subject,
          p_owner_email,
          p_identity_provider,
          p_include_all,
          p_allow_legacy_email
      )
), map_photos as (
    select photo.*
    from public.photos as photo
    left join visible_hikes on visible_hikes.id = photo.hike_id
    where photo.lat is not null
      and photo.lng is not null
      and (
          visible_hikes.id is not null
          or (
              photo.hike_id is null
              and public.hikejournal_mobile_owner_visible(
                  to_jsonb(photo),
                  p_owner_user_id,
                  p_owner_subject,
                  p_owner_email,
                  p_identity_provider,
                  p_include_all,
                  p_allow_legacy_email
              )
          )
      )
)
select
    photo.id,
    photo.hike_id,
    photo.caption,
    photo.public_url,
    photo.storage_path,
    photo.exif_json ->> 'hikejournal_thumbnail_storage_path' as thumbnail_storage_path,
    photo.taken_at,
    photo.created_at,
    photo.lat,
    photo.lng,
    observation.common_name as species_name,
    observation.scientific_name,
    observation.id is not null as confirmed
from map_photos as photo
left join lateral (
    select
        candidate.id,
        candidate.common_name,
        candidate.scientific_name
    from public.species_observations as candidate
    where candidate.photo_id = photo.id
      and candidate.status = 'confirmed'
      and (
          candidate.hike_id in (select visible_hikes.id from visible_hikes)
          or (
              candidate.hike_id is null
              and public.hikejournal_mobile_owner_visible(
                  to_jsonb(candidate),
                  p_owner_user_id,
                  p_owner_subject,
                  p_owner_email,
                  p_identity_provider,
                  p_include_all,
                  p_allow_legacy_email
              )
          )
      )
    order by candidate.is_primary desc nulls last,
             candidate.identified_at desc nulls last,
             candidate.id
    limit 1
) as observation on true;
$$;

revoke all on function public.mobile_map_sightings(uuid[], text, text, text, text, boolean, boolean)
    from public, anon, authenticated;
grant execute on function public.mobile_map_sightings(uuid[], text, text, text, text, boolean, boolean)
    to service_role;

notify pgrst, 'reload schema';

commit;
