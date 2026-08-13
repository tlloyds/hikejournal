begin;

create temporary table hike_location_redirects (
    old_slug text primary key,
    canonical_slug text not null
) on commit drop;

insert into hike_location_redirects (old_slug, canonical_slug) values
    ('black-bear-wilderness-loop', 'black-bear-wilderness-area'),
    ('black-bear-wilderness-loop-trail', 'black-bear-wilderness-area'),
    ('black-bear-wilderness-walk', 'black-bear-wilderness-area'),
    ('econ-river-wilderness-area', 'econ-river-wilderness'),
    ('florida-trail-little-big-econ-state-forest', 'little-big-econ-state-forest'),
    ('florida-trail-mills-creek-woodlands', 'mills-creek-woodlands'),
    ('florida-trail-seminole-ranch', 'seminole-ranch-conservation-area'),
    ('hal-scott-preserve-loop', 'hal-scott-preserve'),
    ('little-manatee-river-trail', 'little-manatee-river-state-park'),
    ('lower-wekiva-river-preserve', 'lower-wekiva-river-preserve-state-park'),
    ('st-sebastian-river-preserve-yellow-trail', 'fellsmere-trailhead-preserve'),
    ('werner-boyce-salt-springs-trail', 'werner-boyce-salt-springs-state-park'),
    ('wuesthoff-trail', 'wuesthoff-park');

-- Copy every historical association to the canonical place first. If a hike
-- already has both rows, retain primary status from either association.
insert into public.hike_location_tags (hike_id, location_id, is_primary, created_at)
select
    tags.hike_id,
    canonical.id,
    bool_or(tags.is_primary),
    min(tags.created_at)
from public.hike_location_tags as tags
join public.hike_locations as duplicate on duplicate.id = tags.location_id
join hike_location_redirects as redirects on redirects.old_slug = duplicate.slug
join public.hike_locations as canonical on canonical.slug = redirects.canonical_slug
group by tags.hike_id, canonical.id
on conflict (hike_id, location_id) do update
set is_primary = public.hike_location_tags.is_primary or excluded.is_primary;

update public.species_quests as quests
set location_id = canonical.id
from public.hike_locations as duplicate
join hike_location_redirects as redirects on redirects.old_slug = duplicate.slug
join public.hike_locations as canonical on canonical.slug = redirects.canonical_slug
where quests.location_id = duplicate.id;

delete from public.hike_location_tags as tags
using public.hike_locations as duplicate, hike_location_redirects as redirects
where tags.location_id = duplicate.id
  and duplicate.slug = redirects.old_slug;

delete from public.hike_locations as duplicate
using hike_location_redirects as redirects
where duplicate.slug = redirects.old_slug;

insert into public.hike_locations (
    name,
    slug,
    location_type,
    source,
    source_url,
    lat,
    lng,
    aliases
) values (
    'William Beardall Tosohatchee Wildlife Management Area',
    'william-beardall-tosohatchee-wildlife-management-area',
    'wildlife_management_area',
    'manual_curated',
    'https://myfwc.com/recreation/lead/tosohatchee/',
    28.498384,
    -80.998595,
    '["Tosohatchee Wildlife Management Area", "Tosohatchee WMA", "Tosohatchee"]'::jsonb
)
on conflict (slug) do update set
    name = excluded.name,
    location_type = excluded.location_type,
    source = excluded.source,
    source_url = excluded.source_url,
    lat = excluded.lat,
    lng = excluded.lng,
    aliases = excluded.aliases;

with alias_updates (slug, aliases) as (
    values
        ('black-bear-wilderness-area', array[
            'Black Bear Wilderness Loop',
            'Black Bear Wilderness Loop Trail',
            'Black Bear Wilderness Walk'
        ]::text[]),
        ('econ-river-wilderness', array['Econ River Wilderness Area']::text[]),
        ('fellsmere-trailhead-preserve', array['St. Sebastian River Preserve Yellow Trail']::text[]),
        ('little-big-econ-state-forest', array[
            'Little-Big Econ State Forest',
            'Little Big Econ',
            'LBESF',
            'Florida Trail, Little Big Econ State Forest',
            'Florida Trail, Chuluota to Oviedo',
            'Florida Trail, Lockwood Trailhead',
            'Lockwood Trailhead'
        ]::text[]),
        ('mills-creek-woodlands', array[
            'Florida Trail, Mills Creek Woodlands',
            'Florida Trail, Mills Creek to Lockwood',
            'Florida Trail Panorama Trailhead',
            'Panorama Trailhead'
        ]::text[]),
        ('seminole-ranch-conservation-area', array[
            'Seminole Ranch',
            'Florida Trail, Seminole Ranch'
        ]::text[]),
        ('hal-scott-preserve', array['Hal Scott Preserve Loop']::text[]),
        ('little-manatee-river-state-park', array['Little Manatee River Trail']::text[]),
        ('lower-wekiva-river-preserve-state-park', array['Lower Wekiva River Preserve']::text[]),
        ('pine-lily-preserve', array['Pine Lilly Preserve']::text[]),
        ('werner-boyce-salt-springs-state-park', array['Werner-Boyce Salt Springs Trail']::text[]),
        ('wuesthoff-park', array['Wuesthoff Trail']::text[])
)
update public.hike_locations as locations
set aliases = (
    select coalesce(jsonb_agg(alias order by lower(alias)), '[]'::jsonb)
    from (
        select distinct alias
        from (
            select jsonb_array_elements_text(coalesce(locations.aliases, '[]'::jsonb)) as alias
            union all
            select unnest(alias_updates.aliases) as alias
        ) as combined_aliases
    ) as unique_aliases
)
from alias_updates
where locations.slug = alias_updates.slug;

commit;
