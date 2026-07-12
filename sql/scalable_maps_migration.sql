-- Scalable, viewport-driven maps for HikeJournal.
-- Run this once in the Supabase SQL editor, then deploy the matching app code.

create extension if not exists postgis;

alter table public.photos
add column if not exists geom geometry(Point, 4326);

create or replace function public.sync_photo_geom()
returns trigger
language plpgsql
as $$
begin
    new.geom := case
        when new.lat is null or new.lng is null then null
        else st_setsrid(st_makepoint(new.lng, new.lat), 4326)
    end;
    return new;
end;
$$;

drop trigger if exists photos_sync_geom on public.photos;
create trigger photos_sync_geom
before insert or update of lat, lng on public.photos
for each row execute procedure public.sync_photo_geom();

update public.photos
set geom = st_setsrid(st_makepoint(lng, lat), 4326)
where lat is not null and lng is not null and geom is null;

create index if not exists photos_geom_gist_idx
on public.photos using gist (geom);

create index if not exists photos_map_order_idx
on public.photos (hike_id, taken_at, created_at, id)
where geom is not null;

alter table public.hike_route_imports
add column if not exists track_geom geometry(MultiLineString, 4326);

create or replace function public.sync_hike_route_geom()
returns trigger
language plpgsql
as $$
declare
    parsed geometry;
begin
    if new.track_geojson is null or new.track_geojson = '{}'::jsonb then
        new.track_geom := null;
        return new;
    end if;
    parsed := st_setsrid(st_geomfromgeojson(new.track_geojson::text), 4326);
    if geometrytype(parsed) = 'LINESTRING' then
        new.track_geom := st_multi(parsed);
    elsif geometrytype(parsed) = 'MULTILINESTRING' then
        new.track_geom := parsed;
    else
        new.track_geom := null;
    end if;
    return new;
exception when others then
    new.track_geom := null;
    return new;
end;
$$;

drop trigger if exists hike_route_imports_sync_geom on public.hike_route_imports;
create trigger hike_route_imports_sync_geom
before insert or update of track_geojson on public.hike_route_imports
for each row execute procedure public.sync_hike_route_geom();

-- Backfill existing imports explicitly. Assigning track_geojson to itself can be
-- optimized away by some migration runners, leaving the update trigger unused.
update public.hike_route_imports
set track_geom = case
    when track_geojson->>'type' = 'LineString' then
        st_multi(st_setsrid(st_geomfromgeojson(track_geojson::text), 4326))
    when track_geojson->>'type' = 'MultiLineString' then
        st_setsrid(st_geomfromgeojson(track_geojson::text), 4326)
    else null
end
where track_geom is null
  and track_geojson is not null
  and track_geojson <> '{}'::jsonb;

create index if not exists hike_route_imports_track_geom_gist_idx
on public.hike_route_imports using gist (track_geom);

create or replace function public.map_summary(
    p_hike_ids uuid[],
    p_hike_id uuid default null
)
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
with eligible_photos as (
    select p.id, p.geom
    from public.photos p
    where p.geom is not null
      and p.hike_id = any(coalesce(p_hike_ids, array[]::uuid[]))
      and (p_hike_id is null or p.hike_id = p_hike_id)
), bounds as (
    select
        count(*)::integer as photo_count
    from eligible_photos
), eligible_routes as (
    select r.track_geom as geom
    from public.hike_route_imports r
    where r.track_geom is not null
      and r.hike_id = any(coalesce(p_hike_ids, array[]::uuid[]))
      and (p_hike_id is null or r.hike_id = p_hike_id)
), combined_bounds as (
    select st_extent(geom) as extent
    from (
        select geom from eligible_photos
        union all
        select geom from eligible_routes
    ) all_geometries
), species as (
    select distinct coalesce(nullif(o.common_name, ''), nullif(o.scientific_name, ''), 'Confirmed species') as name
    from public.species_observations o
    join eligible_photos p on p.id = o.photo_id
    where o.status = 'confirmed'
), species_summary as (
    select count(*)::integer as species_count,
           coalesce(jsonb_agg(name order by name), '[]'::jsonb) as names
    from species
)
select jsonb_build_object(
    'photo_count', b.photo_count,
    'species_count', s.species_count,
    'species', s.names,
    'bounds', case when cb.extent is null then null else jsonb_build_array(
        st_xmin(cb.extent), st_ymin(cb.extent), st_xmax(cb.extent), st_ymax(cb.extent)
    ) end
)
from bounds b cross join combined_bounds cb cross join species_summary s;
$$;

create or replace function public.map_viewport(
    p_hike_ids uuid[],
    p_hike_id uuid,
    p_west double precision,
    p_south double precision,
    p_east double precision,
    p_north double precision,
    p_zoom double precision,
    p_layer_mode text default 'Both',
    p_species_filter text default null,
    p_range_start integer default 1,
    p_range_end integer default 2147483647,
    p_max_features integer default 2500
)
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
with ranked_photos as materialized (
    select p.id, p.hike_id, p.geom, p.lat, p.lng,
           row_number() over (order by p.taken_at nulls first, p.created_at, p.id) as photo_number
    from public.photos p
    where p.geom is not null
      and p.hike_id = any(coalesce(p_hike_ids, array[]::uuid[]))
      and (p_hike_id is null or p.hike_id = p_hike_id)
), viewport_photos as materialized (
    select p.*
    from ranked_photos p
    where p.photo_number between greatest(1, p_range_start) and greatest(p_range_start, p_range_end)
      and p.geom && st_makeenvelope(p_west, p_south, p_east, p_north, 4326)
), map_points as materialized (
    select
        'photo'::text as layer,
        p.id as photo_id,
        p.lng,
        p.lat,
        jsonb_build_object(
            'kind', 'point', 'layer', 'photo', 'photo_id', p.id,
            'hike_id', p.hike_id, 'photo_number', p.photo_number,
            'title', coalesce(primary_species.name, 'Trail photo')
        ) as properties
    from viewport_photos p
    left join lateral (
        select coalesce(nullif(o.common_name, ''), nullif(o.scientific_name, '')) as name
        from public.species_observations o
        where o.photo_id = p.id and o.status = 'confirmed'
        order by o.is_primary desc, o.identified_at desc
        limit 1
    ) primary_species on true
    where p_layer_mode in ('Both', 'Photos')

    union all

    select
        'species'::text,
        p.id,
        p.lng,
        p.lat,
        jsonb_build_object(
            'kind', 'point', 'layer', 'species', 'photo_id', p.id,
            'hike_id', p.hike_id,
            'title', coalesce(nullif(o.common_name, ''), nullif(o.scientific_name, ''), 'Confirmed species'),
            'scientific_name', o.scientific_name,
            'is_primary', o.is_primary,
            'confidence', o.confidence
        )
    from viewport_photos p
    join public.species_observations o on o.photo_id = p.id and o.status = 'confirmed'
    where p_layer_mode in ('Both', 'Species')
      and (
        p_species_filter is null
        or p_species_filter = 'All confirmed species'
        or coalesce(nullif(o.common_name, ''), nullif(o.scientific_name, ''), 'Confirmed species') = p_species_filter
      )
), point_stats as (
    select count(*)::integer as point_count from map_points
), settings as (
    select greatest(0.000005, 31.640625 / power(2.0, greatest(0.0, least(22.0, p_zoom)))) as grid_size,
           (p_zoom < 14 or point_count > p_max_features) as cluster
    from point_stats
), rendered as (
    select jsonb_build_object(
        'type', 'Feature',
        'geometry', jsonb_build_object('type', 'Point', 'coordinates', jsonb_build_array(avg(p.lng), avg(p.lat))),
        'properties', jsonb_build_object(
            'kind', 'cluster', 'layer', p.layer, 'count', count(*)::integer,
            'title', case when p.layer = 'species' then count(*)::text || ' species records' else count(*)::text || ' photos' end
        )
    ) as feature
    from map_points p cross join settings s
    where s.cluster
    group by p.layer, floor((p.lng + 180.0) / s.grid_size), floor((p.lat + 90.0) / s.grid_size)

    union all

    select jsonb_build_object(
        'type', 'Feature',
        'geometry', jsonb_build_object('type', 'Point', 'coordinates', jsonb_build_array(p.lng, p.lat)),
        'properties', p.properties
    )
    from map_points p cross join settings s
    where not s.cluster
    limit p_max_features
)
select jsonb_build_object(
    'type', 'FeatureCollection',
    'features', coalesce(jsonb_agg(feature), '[]'::jsonb),
    'meta', jsonb_build_object(
        'matched', (select point_count from point_stats),
        'clustered', (select cluster from settings)
    )
)
from rendered;
$$;

create or replace function public.map_routes_viewport(
    p_hike_ids uuid[],
    p_hike_id uuid,
    p_west double precision,
    p_south double precision,
    p_east double precision,
    p_north double precision,
    p_zoom double precision
)
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
with settings as (
    select st_makeenvelope(p_west, p_south, p_east, p_north, 4326) as viewport,
           case
               when p_zoom >= 17 then 0.000001
               when p_zoom >= 15 then 0.000005
               when p_zoom >= 13 then 0.00002
               when p_zoom >= 10 then 0.00008
               else 0.0004
           end as tolerance
), features as (
    select jsonb_build_object(
        'type', 'Feature',
        'geometry', st_asgeojson(
            st_intersection(st_simplifypreservetopology(r.track_geom, s.tolerance), s.viewport),
            6
        )::jsonb,
        'properties', jsonb_build_object('hike_id', r.hike_id, 'title', 'Hike path')
    ) as feature
    from public.hike_route_imports r cross join settings s
    where r.track_geom is not null
      and r.hike_id = any(coalesce(p_hike_ids, array[]::uuid[]))
      and (p_hike_id is null or r.hike_id = p_hike_id)
      and r.track_geom && s.viewport
)
select jsonb_build_object(
    'type', 'FeatureCollection',
    'features', coalesce(jsonb_agg(feature), '[]'::jsonb)
)
from features;
$$;

create or replace function public.map_photo_detail(
    p_photo_id uuid,
    p_hike_ids uuid[]
)
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
select jsonb_build_object(
    'photo_id', p.id,
    'hike_id', p.hike_id,
    'lat', p.lat,
    'lng', p.lng,
    'caption', p.caption,
    'image_url', p.public_url,
    'taken_at', p.taken_at,
    'width', p.width,
    'height', p.height,
    'observations', coalesce((
        select jsonb_agg(jsonb_build_object(
            'common_name', o.common_name,
            'scientific_name', o.scientific_name,
            'confidence', o.confidence,
            'is_primary', o.is_primary
        ) order by o.is_primary desc, o.identified_at desc)
        from public.species_observations o
        where o.photo_id = p.id and o.status = 'confirmed'
    ), '[]'::jsonb)
)
from public.photos p
where p.id = p_photo_id
  and p.hike_id = any(coalesce(p_hike_ids, array[]::uuid[]));
$$;

grant execute on function public.map_summary(uuid[], uuid) to anon, authenticated, service_role;
grant execute on function public.map_viewport(uuid[], uuid, double precision, double precision, double precision, double precision, double precision, text, text, integer, integer, integer) to anon, authenticated, service_role;
grant execute on function public.map_routes_viewport(uuid[], uuid, double precision, double precision, double precision, double precision, double precision) to anon, authenticated, service_role;
grant execute on function public.map_photo_detail(uuid, uuid[]) to anon, authenticated, service_role;
