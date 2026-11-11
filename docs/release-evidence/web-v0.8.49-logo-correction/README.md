# Website logo correction evidence

Scope: Web only. Shared VERSION 0.8.49 is unchanged. Android build 195 and iOS
version/build metadata are unchanged.

The corrected asset is copied without modification from
`design/hikejournal-brand/logos/svg/Hiking_Journal-Color_and_white-Horizonal_Logo.svg`.
Its source filename retains “Hiking_Journal”, but the outlined lettering in
the file reads “Hike Journal”.

`SHA256SUMS` records the four deployment files. The local upload package is
`/tmp/hikejournal-bluehost-logo-correction.zip`; it contains `index.html`, the corrected SVG, and updated Hikes/Field Guide PNG
previews. The PNGs are unmodified build-195 instrumentation captures from the
Android release validation; they show synthetic observations with the supplied
public-reference photograph, and no private account data.

Local verification: SVG XML parsing and exact source-asset equality passed.
Both image references resolve and load in the browser. Desktop preview and
390 CSS px phone-width header inspected; document scroll width equals viewport
width. Desktop and full-page preview images are included. Legal/support URLs
were fetched successfully before deployment and contain no logo images.

Bluehost upload/live verification: pending sign-in. The previous temporary SSH
key was removed during the earlier release, and the browser session has expired.
No new access credentials have been created.
