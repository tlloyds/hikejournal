# HikeJournal API — scoped map reads

## Release scope

API only. `VERSION` stays at `0.8.45`; the Android, iOS, and Web clients have
no functional changes. No mobile artifacts were built or published.

## Map and replay data

- Map pins now come from one owner-scoped database function. It returns only
  geotagged photos for visible hikes or the signed-in user's standalone
  photos, along with the primary confirmed species label. The API response
  keeps its existing shape.
- The all-hikes route list now queries only the signed-in user's visible hike
  IDs and selects route GeoJSON, omitting the duplicate PostGIS index geometry
  and unrelated route-import fields.
- Hike replay still receives the complete recorded route and its recording
  metadata, while its database read omits the duplicate PostGIS geometry.
  Playback remains local to the Android client.

## iOS, Android, and Web

No functional changes. No mobile artifacts were built or shipped.

## Debug-log triage

Historical Supabase request logs did not retain enough detail to attribute the
previous egress burst to a particular endpoint. The map reads found by code
inspection have been scoped and narrowed; future usage data is needed to
measure the reduction.

## Validation

The focused API/repository suite passed (99 tests, one dependency deprecation
warning). Production migration execution and Cloud Run health verification are
recorded in the release evidence.
