# Trail Medals

## Product placement

Trail Medals are nested under the Library header instead of becoming a sixth
bottom-navigation destination. Badges summarize progress across outings,
distance, Field Quests, and the Field Guide, so the personal journal is their
natural home. The existing primary destinations keep their current jobs.

The collection is a full-screen mobile surface reached from **Trail Medals** in
the HikeJournal header. It shows the closest upcoming medal first, followed by
the complete collection. Tapping a medal opens its exact requirement and
current progress.

## Unlock model

Medals are derived from existing journal data and do not add a second source of
truth. They work from cached data when the phone is offline and refresh species
and quest progress when the collection opens.

- **Hiking:** 1, 5, 10, 25, 50, and 100 logged outings.
- **Distance:** 25, 100, 250, 500, and 1,000 lifetime miles, plus 10- and
  20-mile single-outing milestones.
- **Field Quests:** 1, 5, and 10 completed quests. A quest is complete when
  every selected focus find has been collected. Less-often-reported finds have
  distinct 1- and 5-species medals.
- **Field Guide:** 1, 25, 50, 100, and 250 distinct species.
- **Specialties:** 25, 50, and 100 distinct plants, mammals, and fungi, plus
  25- and 50-species bird and insect tracks.

Archived outings remain part of lifetime progress. Species are deduplicated by
taxon identity, and the same rare find appearing in multiple quests receives
credit once.

## Visual system

Medals use a pressed botanical-enamel treatment that belongs to HikeJournal's
forest, parchment, and trail-orange palette. Bronze, silver, gold, and
evergreen finishes communicate increasing depth without adding game-like
points, streak pressure, or competitive ranking.

Motion is deliberately restrained:

1. Medals enter in a short stagger when the collection opens.
2. A pressed medal settles slightly under the finger.
3. Progress animates when a medal detail is opened.

## Extension path

The catalog and progress engine are separate from the screen. Future tracks can
be added without changing navigation or storing duplicate unlock state. If
time-stamped celebrations or social sharing are added later, the server can
persist the first unlock event while continuing to derive eligibility from the
journal.
