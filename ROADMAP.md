# HikeJournal Refactor Roadmap

This roadmap is the practical bridge between "great home-built app" and "stable, flagship-quality product."

## Principles

- Build the flagship surfaces first.
- Stabilize routing and state before adding another large layer of complexity.
- Refactor along real seams, not theoretical purity.
- Keep HikeJournal centered on the archive -> review -> field guide loop.

## Phase 1: Flagship Archive

- Goal: make `Library` the centerpiece of the app.
- Why first: it is the primary entry point and the clearest expression of the product.
- Risk: low to medium
- Build first:
  - redesign archive rows and action hierarchy
  - strengthen pagination and grouping UX
  - make standalone sightings feel like a first-class archive lane
  - improve mobile archive scanning
- Stabilize after:
  - extract library helpers from the main app controller
  - centralize archive filtering/grouping utilities

### File targets

- [/Users/adl/Documents/Playground/hike-journal/app.py](/Users/adl/Documents/Playground/hike-journal/app.py)
- [/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/theme.py](/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/theme.py)
- [/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/components.py](/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/components.py)

### Status

- Complete

### What shipped

- Library became a true archive surface instead of a generic list.
- Archive rows, cover-photo presence, and action hierarchy were redesigned.
- Standalone sightings were promoted into their own first-class archive lane.
- Library pagination now applies to outings without treating standalone sightings like just another hike row.
- The top control band was simplified into a clearer archive browsing model:
  - `Everything`
  - `Current outings`
  - `Archived outings`
  - `Everyday`
- Archive actions now read more clearly:
  - primary outing entry
  - supporting map / sightings access
  - separate management action

### Follow-up stabilization still worth doing later

- Extract library helpers from the main controller once the controller/state refactor begins.
- Pull archive filtering/grouping/state into a more dedicated seam.

## Phase 2: Review Inbox

- Goal: turn `Species Review` into a calm, high-throughput review and publish surface.
- Why second: it is the operational heart of the app.
- Risk: medium
- Build first:
  - split review and publish states more clearly
  - improve bulk action ergonomics
  - make alternative iNaturalist suggestions more visual
  - expose posting states more clearly
- Stabilize after:
  - separate selection state logic from rendering
  - extract publishing workflow helpers

### File targets

- [/Users/adl/Documents/Playground/hike-journal/app.py](/Users/adl/Documents/Playground/hike-journal/app.py)
- [/Users/adl/Documents/Playground/hike-journal/hike_journal/services/inat.py](/Users/adl/Documents/Playground/hike-journal/hike_journal/services/inat.py)
- [/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/theme.py](/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/theme.py)

### Status

- In progress

### What is already materially better

- Species Review now has a more compact working header instead of an oversized hero.
- Species Review now separates `Review` and `Publish` into explicit workspace modes instead of always stacking both long flows on one page.
- Review mode now has an explicit queue-state filter, so large queues can be narrowed to waiting / ready / confirmed / rejected work.
- Alternate iNaturalist suggestions are now surfaced inline instead of being buried in a popover.
- Review-state context is clearer at the row level.
- Publishing lane naming and queue structure are more understandable than before.
- Publishing lane now has a clearer queue-state filter, compact summary rail, and denser operator-style row layout.
- Batch actions and posting state visibility are stronger than the earliest version.

### What still does not satisfy the phase goal

- Review and publish are still two long sections stacked on the same page, rather than a truly calm high-throughput inbox.
- Bulk action ergonomics are functional but not yet great for large queues.
- Alternate iNaturalist suggestions exist, but they are not yet visual enough to feel like first-class ranked options.
- Posting state is visible, but not yet woven deeply enough into the triage flow.
- Selection state, pagination state, and workflow logic are still too entangled with rendering.

### What Phase 2 should now focus on

1. Make large-queue work calmer:
   - clearer state grouping
   - faster scan rhythm
   - less repeated chrome
2. Reduce state/render coupling where possible before Phase 5.

## Phase 3: Field Guide

- Goal: make `Species Log` feel like a personal field guide instead of filtered results.
- Why third: it becomes extraordinary once archive and review are already strong.
- Risk: medium
- Build first:
  - move toward master-detail species browsing
  - improve encounter grouping and image discipline
  - add stronger species-level summaries
  - improve viewer handoff from species context
- Stabilize after:
  - pull species-log shaping/grouping into dedicated helpers

### File targets

- [/Users/adl/Documents/Playground/hike-journal/app.py](/Users/adl/Documents/Playground/hike-journal/app.py)
- [/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/components.py](/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/components.py)
- [/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/theme.py](/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/theme.py)

### Status

- In progress

### What is already materially better

- Species Log now behaves more like a field guide and less like a long feed of expandable rows.
- The page now has a master-detail structure:
  - species index on the left
  - focused species record and encounters on the right
- A single species can now stay in focus while you review its encounters, map links, outing links, and reference material.
- Species guide links and summaries are more naturally integrated into the focused record.

### What still does not satisfy the phase goal

- The species index is still fairly utilitarian and could become more visual and more scan-friendly.
- Encounter strips are improved from earlier versions, but they can still feel a bit like app rows rather than beautiful field notes.
- The detail pane could do more with species-level context:
  - posting state
  - richer encounter summaries
  - stronger photo navigation rhythm

### What Phase 3 should now focus on

1. Make the species index feel more like a real field-guide table of contents.
2. Refine encounter presentation so it feels more editorial and less like utility rows.
3. Tighten the species detail pane so the focused record feels unmistakably premium.

## Phase 4: Mobile Shell

- Goal: make the browser experience feel native enough that public/mobile deployment is obvious.
- Why fourth: the information architecture should be settled before we tune the shell around it.
- Risk: medium
- Build first:
  - reduce top-of-page ceremony on small screens
  - tighten tap-target and sticky action behavior
  - improve viewer ergonomics
  - make navigation more thumb-friendly
- Stabilize after:
  - unify responsive patterns across archive, review, map, and viewer

### File targets

- [/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/theme.py](/Users/adl/Documents/Playground/hike-journal/hike_journal/ui/theme.py)
- [/Users/adl/Documents/Playground/hike-journal/app.py](/Users/adl/Documents/Playground/hike-journal/app.py)

## Phase 5: Controller and State Refactor

- Goal: reduce fragility in routing, filters, viewer state, and per-surface orchestration.
- Why now: by this point we will know which abstractions are real.
- Risk: high
- Stabilize first:
  - split page controllers out of the monolithic app controller
  - isolate query-param hydration
  - isolate viewer state and navigation context
  - isolate standalone sightings behavior
- Build after:
  - only small UX upgrades while the seam work is underway

### Status

- In progress

### Stabilization completed

- Moved top-level application orchestration into `hike_journal/application.py`.
- Centralized session defaults in `hike_journal/ui/state.py`.
- Centralized cached repository reads and invalidation in `hike_journal/queries.py`.
- Isolated query-parameter hydration, navigation state, URL construction, and viewer selection in `hike_journal/navigation.py`.
- Isolated standalone-journal activation and record filtering from the main controller.
- Extracted Library, Map, and Species Log renderers behind tested callback contracts.
- Added authenticated route verification for Library, Map, Species Log, hike Journal, and standalone Journal.

### Next stabilization seam

1. Extract Journal rendering and photo-management orchestration.
2. Extract Species Review selection state before moving its renderer.
3. Split publishing orchestration only after its state transitions have direct characterization coverage.

### File targets

- [/Users/adl/Documents/Playground/hike-journal/app.py](/Users/adl/Documents/Playground/hike-journal/app.py)
- [/Users/adl/Documents/Playground/hike-journal/hike_journal/services/repositories.py](/Users/adl/Documents/Playground/hike-journal/hike_journal/services/repositories.py)
- [/Users/adl/Documents/Playground/hike-journal/hike_journal/config.py](/Users/adl/Documents/Playground/hike-journal/hike_journal/config.py)

## Phase 6: Data and Safety Cleanup

- Goal: make the app safer and easier to evolve.
- Why last: this is important, but it should follow product-shaping work.
- Risk: medium
- Stabilize first:
  - normalize schema drift
  - audit ownership and visibility rules
  - revisit permissive RLS policies
  - improve test coverage around risky flows

### File targets

- [/Users/adl/Documents/Playground/hike-journal/sql/schema.sql](/Users/adl/Documents/Playground/hike-journal/sql/schema.sql)
- [/Users/adl/Documents/Playground/hike-journal/sql](/Users/adl/Documents/Playground/hike-journal/sql)
- [/Users/adl/Documents/Playground/hike-journal/tests](/Users/adl/Documents/Playground/hike-journal/tests)

## Build vs Stabilize Order

### Build first

1. Library flagship redesign
2. Species Review inbox redesign
3. Species Log field-guide redesign
4. Mobile shell pass

### Stabilize first

1. Controller/state refactor
2. Schema/security/test cleanup

The reasoning is simple: the product already has enough depth. The highest-leverage move now is to make the flagship surfaces exceptional, then do the deeper structural cleanup once we know the product shape we want to preserve.
