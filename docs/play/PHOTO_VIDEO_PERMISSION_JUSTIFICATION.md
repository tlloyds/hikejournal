# Google Play photo and video permission justification

## Core functionality

HikeJournal is a visual field-journal application. Attaching original photos
and videos to a hike is a core part of creating the journal entry, and users
perform this workflow for effectively every hike they record. This is not a
profile-image, avatar, or occasional attachment feature.

When a user opens the photo attachment flow, HikeJournal lets them browse the
phone's local media library, browse albums, select multiple items, and attach
them to the current hike. Media access is user initiated and limited to the
attachment workflow; the app does not scan or upload the library in the
background.

## Why Android Photo Picker is technically insufficient

HikeJournal's core photo feature depends on the GPS-bearing original bytes and
their EXIF metadata. The coordinates are used to place photos on the hike's
photo map and to support coordinate-backed iNaturalist publishing. If a picker
returns a cloud-backed, transcoded, or privacy-redacted representation, the
GPS EXIF can be absent even though the original photo in the user's local
library contains it. Once the provider has omitted or redacted the GPS data,
HikeJournal cannot reconstruct it from the selected URI.

The Android Photo Picker is an appropriate privacy-preserving choice for apps
that need occasional access to display or upload selected media. It is not
sufficient for HikeJournal's required workflow because it does not guarantee
that a selected provider item is the phone-local, original file with the EXIF
metadata needed by the app. In testing, the picker path surfaced Google
Photos/cloud-backed media whose selected representation did not provide the
GPS-bearing original required for photo maps. A generic document/system picker
has the same provider-origin and original-bytes uncertainty and does not
provide a reliable replacement for HikeJournal's local-library browser.

## Why the requested permissions are necessary

- `READ_MEDIA_IMAGES` and `READ_MEDIA_VIDEO` allow the in-app browser to read
  the user's local photo and video library for the user-selected attachment
  workflow, including album browsing and multi-selection.
- `READ_MEDIA_VISUAL_USER_SELECTED` supports Android 14 selected-media access
  behavior while the app manages the attachment session.
- `ACCESS_MEDIA_LOCATION` is required to read unredacted GPS EXIF from the
  original media when the user has granted access.
- `READ_EXTERNAL_STORAGE` is retained only for Android 12 and earlier, where
  it is the legacy equivalent needed by the same workflow.

HikeJournal reads media only after the user chooses to attach photos or videos
to a hike. It copies the selected originals into the app's upload queue,
extracts the metadata needed for the journal, and does not use these
permissions for advertising, analytics, or unrelated features.

## Reviewer access steps

1. Sign in with the supplied review account.
2. On first launch, choose a state and load the place library.
3. Complete or skip the four-screen welcome walkthrough.
4. Open Journal, open a hike, and choose **Upload photos**.
5. Grant full photo and video access when Android requests it. Full access is
   necessary to exercise album browsing and select original GPS-tagged media.
6. Select several local photos, including a GPS-tagged original, and attach
   them to the hike. The app uses the retained EXIF location for the photo map.

## Short declaration text

HikeJournal is a visual field journal; attaching original photos/videos is its
core function on every hike. We need local-library access to browse albums and
select multiple originals because Android Photo Picker/system providers can
return cloud, transcoded, or EXIF-redacted copies, omitting GPS required for
photo maps and coordinate-backed iNaturalist publishing. ACCESS_MEDIA_LOCATION
reads unredacted GPS from selected originals. Media is read only during
user-initiated attachment.
