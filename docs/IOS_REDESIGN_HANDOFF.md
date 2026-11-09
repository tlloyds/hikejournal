# iOS redesign handoff

This Android release applies the supplied HikeJournal brand to the Android UI
and the public site. It does not change iOS source or behavior. Use this note as
the starting point for a separate iOS visual redesign.

## Brand assets

The designer supplied a compact, reusable asset set at
[`design/hikejournal-brand`](../design/hikejournal-brand):

- `logos/svg/` and `logos/png/`: horizontal, stacked, icon, white, black, and
  color logo variants.
- `icons/svg/` and `icons/png/`: Hikes, Species, Review, Publish, and Map
  navigation icons in green and white, plus the contour patterns.
- `patterns/`: green and white pattern JPGs.
- `Hiking-Journal-Style-Guide.jpg`: the visual reference sheet.

The original Illustrator documents remain in the designer's Downloads folder;
they are intentionally not copied into the repository. Screen references are
in `Sceens - Interface Design` in that folder, including Hikes, Species Review,
Publish, Field Guide, and Trail Medals. The exported artboards are examples,
not a complete inventory of app flows.

## Visual system

| Token | Hex | Use |
| --- | --- | --- |
| Moss | `#324223` | Main brand surface, navigation, headings |
| Moss soft | `#465A32` | Secondary forest surfaces |
| Fern | `#AECE76` | Primary highlight, selected tabs, actions |
| Parchment | `#F5F1E7` | Main reading background |
| Paper | `#F4ECEB` | Light logo and text on dark surfaces |
| Trail | `#D17D42` | Warm secondary accent and creation actions |
| Ink | `#293520` | Main text |
| Muted ink | `#56614F` | Supporting text |

Use Cormorant Garamond for display headings and Source Sans 3 for body text,
labels, and controls. Both font families are already bundled in the iOS app.
The designer did not provide font files or a separate font license; keep the
current bundled families unless the designer supplies different approved
fonts.

The screen artboards also use a clear reading hierarchy: put dates and publish
state in compact, bold white text on a dark orange tag; use the display face for
titles placed over photos; keep location and photo counts in a quieter but
legible sans-serif; and use bold sans-serif for species names and important
counts. On Hikes, the bottom navigation is a floating capsule with a separate
circular orange add action. Keep that shape and hierarchy as design cues while
building native SwiftUI controls.

## iOS implementation notes

- Update the shared values in
  [`ios/HikeJournal/DesignSystem/DesignTokens.swift`](../ios/HikeJournal/DesignSystem/DesignTokens.swift)
  when implementing the redesign. Keep semantic/adaptive light and dark
  variants rather than copying Android's fixed colors verbatim.
- Reuse the supplied vector assets in the iOS asset catalog where practical;
  prefer SVG/PDF vector assets for logos and tab icons and use the JPG pattern
  only as a cropped, low-contrast surface texture.
- Preserve the five primary destinations: Hikes, Species, Review, Publish, and
  Map. Publish remains a first-class navigation destination even though one
  Hikes artboard shows only four tabs.
- Treat every artboard as a visual reference. Keep existing data, navigation,
  accessibility, editing, tracking, offline, sync, photo, species review, and
  iNaturalist publishing behavior intact; the mockups do not specify every
  state or screen.
- Keep Android and iOS navigation layouts platform-native. Share the palette,
  fonts, marks, icon artwork, and spacing intent without forcing Compose layout
  or Android system-bar treatment onto SwiftUI.
- Keep the GPS-safe original-photo browser connected to journal uploads. Do
  not replace it with a cloud-provider-only picker because providers can strip
  EXIF coordinates used by photo maps and coordinate-backed publishing.

## Release boundary

The current work is Android + Web. iOS source, version, build number, archive,
and App Store artifact are unchanged. Implement and validate the iOS redesign in
its own release after reviewing the native iOS screens against the supplied
artboards.
