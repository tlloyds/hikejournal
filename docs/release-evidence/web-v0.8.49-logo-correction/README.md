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

## Live deployment

- Runtime source commit: `b65f0a4`.
- Deployed through the signed-in Bluehost portal and cPanel File Manager to
  `/home3/mftphilo/public_html/website_4d9d652d`.
- All four deployed files match the committed-source SHA-256 hashes;
  `live-verification.json` records bytes, hashes, and successful legal/support
  URL checks.
- Live desktop and 390 CSS px phone layouts inspected. Both logo instances and
  both updated app previews loaded. The phone document width equals its 390 px
  viewport. Browser warning/error log: no entries.
- `live-desktop.jpg`, `live-phone.jpg`, and `live-full-page.jpg` show the result.
- The uploaded ZIP was moved to cPanel Trash. Its public URL returns HTTP 404.
- Server backups, verified in cPanel, are outside the document root:
  `/home3/mftphilo/hikejournal-backups/assets-before-logo-2026-11-10.zip`
  (2.6 MB) and `index-before-logo-2026-11-10.html` (14.34 KB).
- No new access credentials were created. The existing portal session was
  renewed by the user; no permanent access was added.
- Web-only tag: `web-v0.8.49-logo-correction`.
