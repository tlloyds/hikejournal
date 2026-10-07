-- Owner-scoped summary and camera-bounded pins for the native map.
-- Requires sql/scalable_maps_migration.sql (photos.geom and route track_geom).

begin;

-- Replace the first draft's hike-ID signatures. Loading hikes through
-- PostgREST is itself subject to the row cap, so ownership is resolved here.
drop function if exists public.mobile_map_summary(uuid[], text, text, text, text, boolean, boolean);
drop function if exists public.mobile_map_viewport(
    uuid[], double precision, double precision, double precision, double precision,
    double precision, integer, text, text, text, text, boolean, boolean
);

create or replace function public.mobile_map_summary(
    p_owner_user_id text,
    p_owner_subject text,
    p_owner_email text,
    p_identity_provider text,
    p_include_all boolean,
    p_allow_legacy_email boolean
)
returns jsonb
language sql
stable
set search_path = public
as $$
with visible_hikes as (
    select hike.id
    from public.hikes as hike
    where public.hikejournal_mobile_owner_visible(
          to_jsonb(hike),
          p_owner_user_id,
          p_owner_subject,
          p_owner_email,
          p_identity_provider,
          p_include_all,
          p_allow_legacy_email
      )
), eligible_photos as (
    select photo.geom
    from public.photos as photo
    left join visible_hikes on visible_hikes.id = photo.hike_id
    where photo.geom is not null
      and photo.lat is not null
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
), eligible_routes as (
    select route.track_geom as geom
    from public.hike_route_imports as route
    join visible_hikes on visible_hikes.id = route.hike_id
    where route.track_geom is not null
), counts as (
    select count(*)::integer as photo_count from eligible_photos
), extent as (
    select st_extent(geom) as box
    from (
        select geom from eligible_photos
        union all
        select geom from eligible_routes
    ) as mapped_geometry
)
select jsonb_build_object(
    'photo_count', counts.photo_count,
    'bounds', case when extent.box is null then null else jsonb_build_array(
        st_xmin(extent.box), st_ymin(extent.box), st_xmax(extent.box), st_ymax(extent.box)
    ) end
)
from counts cross join extent;
$$;

create or replace function public.mobile_map_viewport(
    p_west double precision,
    p_south double precision,
    p_east double precision,
    p_north double precision,
    p_zoom double precision,
    p_max_features integer,
    p_owner_user_id text,
    p_owner_subject text,
    p_owner_email text,
    p_identity_provider text,
    p_include_all boolean,
    p_allow_legacy_email boolean
)
returns jsonb
language sql
stable
set search_path = public
as $$
with visible_hikes as (
    select hike.id, hike.title, hike.hike_date, hike.location_name
    from public.hikes as hike
    where public.hikejournal_mobile_owner_visible(
          to_jsonb(hike),
          p_owner_user_id,
          p_owner_subject,
          p_owner_email,
          p_identity_provider,
          p_include_all,
          p_allow_legacy_email
      )
), viewport as (
    select case when p_west <= p_east then p_east - p_west else 360.0 - p_west + p_east end as width
), viewport_photos as materialized (
    select
        photo.id,
        photo.hike_id,
        photo.lat,
        photo.lng,
        photo.caption,
        photo.taken_at,
        photo.public_url,
        photo.storage_path,
        photo.exif_json ->> 'hikejournal_thumbnail_storage_path' as thumbnail_storage_path,
        coalesce(visible_hikes.title, 'Everyday sighting') as hike_title,
        coalesce(visible_hikes.hike_date::text, '') as hike_date,
        coalesce(visible_hikes.location_name, '') as location_name,
        coalesce(primary_species.name, '') as species_name,
        coalesce(primary_species.scientific_name, '') as scientific_name,
        primary_species.id is not null as confirmed
    from public.photos as photo
    cross join viewport
    left join visible_hikes on visible_hikes.id = photo.hike_id
    left join lateral (
        select
            candidate.id,
            coalesce(nullif(candidate.common_name, ''), nullif(candidate.scientific_name, '')) as name,
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
    ) as primary_species on true
    where photo.geom is not null
      and photo.lat is not null
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
      and (
          (p_west <= p_east and photo.geom && st_makeenvelope(p_west, p_south, p_east, p_north, 4326))
          or (
              p_west > p_east
              and (
                  photo.geom && st_makeenvelope(p_west, p_south, 180.0, p_north, 4326)
                  or photo.geom && st_makeenvelope(-180.0, p_south, p_east, p_north, 4326)
              )
          )
      )
), map_points as materialized (
    select
        photo.*,
        jsonb_build_object(
            'kind', 'photo',
            'id', photo.id,
            'hike_id', photo.hike_id,
            'hike_title', photo.hike_title,
            'hike_date', photo.hike_date,
            'location_name', photo.location_name,
            'caption', coalesce(photo.caption, ''),
            'taken_at', photo.taken_at,
            'species_name', photo.species_name,
            'scientific_name', photo.scientific_name,
            'confirmed', photo.confirmed,
            'public_url', photo.public_url,
            'storage_path', photo.storage_path,
            'thumbnail_storage_path', photo.thumbnail_storage_path,
            'cluster_count', 0
        ) as properties
    from viewport_photos as photo
), point_stats as (
    select count(*)::integer as point_count from map_points
), settings as (
    select
        point_stats.point_count,
        (
            coalesce(p_zoom, 0) < 12
            or point_stats.point_count > greatest(1, least(2500, coalesce(p_max_features, 1500)))
        ) as cluster,
        greatest(
            0.000005,
            31.640625 / power(2.0, greatest(0.0, least(22.0, coalesce(p_zoom, 0)))),
            greatest(viewport.width, p_north - p_south)
                / greatest(1.0, floor(sqrt(least(2500, coalesce(p_max_features, 1500)))) - 1.0)
        ) as grid_size
    from point_stats cross join viewport
), clustered as (
    select jsonb_build_object(
        'type', 'Feature',
        'geometry', jsonb_build_object(
            'type', 'Point',
            'coordinates', jsonb_build_array(avg(photo.lng), avg(photo.lat))
        ),
        'properties', jsonb_build_object(
            'kind', 'cluster',
            'id', 'cluster:' || floor((avg(photo.lng) + 180.0) / settings.grid_size)::text
                || ':' || floor((avg(photo.lat) + 90.0) / settings.grid_size)::text,
            'cluster_count', count(*)::integer,
            'title', count(*)::text || ' photos'
        )
    ) as feature
    from map_points as photo
    cross join settings
    where settings.cluster
    group by floor((photo.lng + 180.0) / settings.grid_size),
             floor((photo.lat + 90.0) / settings.grid_size),
             settings.grid_size
), individual as (
    select jsonb_build_object(
        'type', 'Feature',
        'geometry', jsonb_build_object(
            'type', 'Point',
            'coordinates', jsonb_build_array(photo.lng, photo.lat)
        ),
        'properties', photo.properties
    ) as feature
    from map_points as photo
    cross join settings
    where not settings.cluster
    order by photo.taken_at nulls first, photo.id
    limit greatest(1, least(2500, coalesce(p_max_features, 1500)))
), rendered as (
    select feature from clustered
    union all
    select feature from individual
)
select jsonb_build_object(
    'type', 'FeatureCollection',
    'features', coalesce(jsonb_agg(rendered.feature), '[]'::jsonb),
    'meta', jsonb_build_object(
        'matched', (select point_count from point_stats),
        'clustered', (select cluster from settings)
    )
)
from rendered;
$$;

revoke all on function public.mobile_map_summary(text, text, text, text, boolean, boolean)
    from public, anon, authenticated;
revoke all on function public.mobile_map_viewport(double precision, double precision, double precision, double precision, double precision, integer, text, text, text, text, boolean, boolean)
    from public, anon, authenticated;
grant execute on function public.mobile_map_summary(text, text, text, text, boolean, boolean)
    to service_role;
grant execute on function public.mobile_map_viewport(double precision, double precision, double precision, double precision, double precision, integer, text, text, text, text, boolean, boolean)
    to service_role;

notify pgrst, 'reload schema';

commit;
