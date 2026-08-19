# Nationwide location library

## Product behavior

HikeJournal loads one state place pack at a time. First-run setup asks the hiker
to choose a state or use a one-time coarse location lookup. The device's
geocoder resolves the lookup; HikeJournal stores only the resulting two-letter
state code and does not send the coordinates to its API.

The selected state can be changed in Settings. Each state response is cached in
a separate file so a previously loaded pack remains usable offline. Personal
places are included alongside every selected state pack.

## Source strategy

The release baseline uses three layers:

1. Existing FloridaHikes-derived records retain the deeper Florida coverage.
2. The public-domain USGS National Digital Trails service supplies named,
   explicitly pedestrian-compatible trails. USGS aggregates reviewed data from
   federal agencies, 36 state partners, trail organizations, and some local
   sources.
3. The public-domain USGS Protected Areas Database of the United States
   (PAD-US) supplies open-access state parks, forests, preserves, recreation
   areas, wildlife lands, local parks, and other hiking-scale public lands. The
   builder deliberately ranks non-federal managers ahead of federal managers.

The reproducible builder is `scripts/build_nationwide_hike_locations.py`. It:

- obtains current state boundaries from Census TIGERweb;
- spatially assigns USGS trail segments to states;
- keeps only named terra trails whose source explicitly marks pedestrian use;
- collapses repeated segments into one searchable place per normalized name;
- prefers nationally designated and longer trails;
- reserves up to 75 slots for open-access PAD-US places of at least 20 acres,
  preferring state, local, regional, and nonprofit managers, then uses more
  public lands to backfill states where explicit pedestrian trail data is thin;
- stores an in-state representative coordinate, aliases, state, source, and
  source URL; and
- caps the generated layer at 250 places per state so mobile search and GPS matching
  remain responsive.

The build is restartable through ignored per-state cache files in
`.runtime/hike-location-pack-cache`. Re-running it replaces only records whose
source is `usgs_national_digital_trails` or `usgs_pad_us` and preserves curated
records.

## Adding FloridaHikes-like depth safely

Commercial and community trail catalogs can identify gaps, but their names,
descriptions, coordinates, photos, ratings, and route data must not be copied
unless their license or written permission allows redistribution in a Play Store
app. FloridaHikes, Washington Trails Association, HikeArizona, TrailLink,
AllTrails, and similar sites should therefore be treated as discovery leads until
permission is documented.

High-value partnership candidates for the next depth pass are FloridaHikes
(Florida), Washington Trails Association's Hiking Guide (Washington),
HikeArizona (Arizona), Oregon Hikers Field Guide (Oregon and southwest
Washington), and Trail Finder (Vermont and New Hampshire). Trail Finder is
especially promising because its listings are developed with trail managers;
Oregon Hikers explicitly says its content may not be reused without permission.
Treat all five as outreach targets, not scrape targets.

Expansion should prefer, in order:

1. direct state park/forest/wildlife agency open-data APIs and GIS downloads;
2. state or regional open-data portals with explicit public-domain or compatible
   licenses;
3. land-manager feeds already cross-walked by USGS National Digital Trails; and
4. permissioned third-party catalogs.

Each new feed needs a registry entry recording publisher, URL, license, retrieved
date, state coverage, fields used, update cadence, and attribution requirements.
The current registry is `data/hike_location_sources.json`; an unresolved license
status is a release blocker, not permission to redistribute.
Only stable facts needed by HikeJournal should be imported: canonical name,
aliases, representative trailhead/route coordinate, state/region/county, place
type, public-land manager, stable source identifier, and source URL. Descriptions, photos, reviews,
difficulty, and current conditions are out of scope unless separately licensed
and maintained.

Every build also writes `data/hike_location_coverage.json`, a reviewable state
and source count report with a non-federal public-land count for each state.

## Quality gates

A generated release seed must:

- cover all 50 states;
- contain no duplicate slugs;
- give every shared location a valid state code and finite U.S. coordinate;
- retain source provenance for every generated record;
- include non-federal public-land options in every state where PAD-US exposes
  qualifying records;
- keep each non-Florida state pack within its configured cap;
- retain the existing Florida curated layer;
- return only the requested state plus the signed-in hiker's personal places;
- preserve state-specific offline caches when the selected state changes; and
- pass API, Android parser, picker, GPS-suggestion, and migration tests.

## Same-day release order

1. Apply `sql/nationwide_hike_locations_migration.sql`.
2. Deploy the backward-compatible mobile API.
3. Import the regenerated seed through the web Location Library tool and verify
   counts for several small and large states.
4. Smoke-test first-run manual selection, current-location selection, changing
   states, offline reopening, place search, and post-recording GPS suggestion.
5. Build and verify the permanently signed AAB/APK using the repository release
   process. Upload only after the migration, API, and production seed are proven.

The historical FloridaHikes-derived data also needs documented redistribution
permission or a replacement open-data source before a public consumer release.
Until permission is recorded, build a separate public seed without modifying the
review copy:

```bash
python3 scripts/build_nationwide_hike_locations.py \
  --exclude-source cfl_hike_planner_places \
  --exclude-source cfl_hike_planner_routes \
  --output data/hike_locations_seed_public.json \
  --coverage-output data/hike_location_coverage_public.json
```
