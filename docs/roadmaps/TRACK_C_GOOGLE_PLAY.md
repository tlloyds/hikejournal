# Track C: Google Play publication

**Track status:** planned; publisher and policy discovery may proceed in parallel

**Outcome:** a policy-compliant, production-signed HikeJournal Android App Bundle,
complete Play listing and declarations, controlled testing, staged rollout,
monitoring, support, and rollback capability.

Google Play requirements change. At the beginning of each release cycle, verify
the current rules in the official Play Console and Android documentation. A date
or target mentioned in this roadmap is a planning input, not a substitute for
that release-time check.

## Release lanes

Track C has two distinct lanes:

1. **Internal/closed personal testing.** A Track A single-owner build may be used
   with controlled testers and an appropriate pairing/reviewer process. It is not
   presented as a general consumer service.
2. **Public consumer release.** Requires all applicable Track A and Track B exit
   gates, including real accounts, tenant isolation, privacy controls, deletion,
   and production operations.

No public-production listing may rely on the legacy global pairing key.

## Scope

Track C includes:

- publisher identity, organization/personal account decision, package registration,
  Play App Signing, key custody, and console access controls;
- current target SDK, AAB, native-library compatibility, release-toolchain, and
  artifact validation;
- privacy policy, support and deletion web presence, data inventory, retention,
  third-party notices, and Play declarations;
- foreground-service, photo/video permission, location, health/activity, target
  audience, advertising, content rating, and reviewer-access submissions;
- store name, descriptions, icons, feature graphic, screenshots, localization
  decisions, and device compatibility;
- internal/closed testing, pre-launch reports, accessibility, performance,
  security, and policy validation; and
- staged rollout, Android vitals, backend monitoring, support, rollback, and
  post-launch review.

## Non-goals

Track C does not:

- substitute store review for Track A reliability verification;
- substitute a privacy policy for Track B's technical tenant isolation;
- remove Android features merely to make declarations shorter without an explicit
  product decision;
- create iOS/App Store artifacts;
- add monetization unless separately specified; or
- authorize public launch before required multi-user gates are complete.

## Dependencies and compatibility

- Track A must supply the permanent package/signing decision, release variants,
  signed AAB, current SDK/toolchain, no-secret artifact scan, contract compatibility,
  production API, monitoring, backups, and release evidence.
- Track B is required for public consumer launch. It supplies verified accounts,
  authorization, media privacy, per-user integrations, export/deletion, retention,
  abuse controls, and the final data map.
- Play App Signing and the personal release signing approach must be designed
  together. If the same package is used, the upload/app-signing key transition
  must preserve future update ownership.
- `VERSION` remains canonical for versionName/API/artifact naming; versionCode is
  monotonically increased for every build uploaded to Play, including internal
  and closed tracks.
- The mobile API supports the currently available Play build and the declared
  previous-client window. Store review and staged rollout can leave older clients
  active for days or weeks.
- API, database, privacy page, support contact, and deletion path must remain live
  throughout review and rollout.

## Current official policy checkpoints

Revalidate these sources immediately before implementation and submission:

- [Target API level requirements](https://developer.android.com/google/play/requirements/target-sdk)
- [Android Gradle Plugin and API compatibility](https://developer.android.com/build/releases/about-agp)
- [Play App Signing](https://support.google.com/googleplay/android-developer/answer/9842756)
- [16 KB page-size support](https://developer.android.com/guide/practices/page-sizes)
- [Photo and video permissions policy](https://support.google.com/googleplay/android-developer/answer/14115180)
- [Foreground service requirements](https://support.google.com/googleplay/android-developer/answer/13392821)
- [Data Safety](https://support.google.com/googleplay/android-developer/answer/10787469)
- [Account deletion](https://support.google.com/googleplay/android-developer/answer/13327111)
- [Health apps declaration](https://support.google.com/googleplay/android-developer/answer/14738291)
- [Testing requirements for new personal accounts](https://support.google.com/googleplay/android-developer/answer/14151465)

The August 2026 working-tree baseline is compile/target API 36. Configuration at
API 36 is not proof that behavior has been verified across the supported device
and permission matrix, nor that the eventual upload meets every current Console
rule. Track A therefore retains API 36 behavior and toolchain verification as
productionization work. The official Console requirement at upload time wins.

## C0 — Publisher, ownership, and package decisions

### Work

- **C0.1** Decide organization versus personal developer account using the current
  Google Play identity and health-app rules. If an organization account is needed,
  obtain/verify the legal entity, D-U-N-S record, address, phone, website, and
  authorized contact early.
- **C0.2** Establish least-privileged Play Console roles, mandatory MFA, recovery
  owners, and audited access. Avoid a single-person unrecoverable account.
- **C0.3** Confirm permanent application ID, public app name, publisher name, support
  domain/email, default language, countries, pricing, ads, target ages, and whether
  the route/distance/activity features trigger health-app declarations.
- **C0.4** Enroll/configure Play App Signing and document upload-key generation,
  custody, backup, rotation, compromise response, and CI access.
- **C0.5** Reconcile the Track A personal signing path with Play ownership. Rehearse
  the exact update/migration behavior before enrolling the production package.
- **C0.6** Register the package and complete current developer verification before
  applicable deadlines.

### Exit gates

- Publisher and package ownership are recoverable and documented.
- The correct account type and health/activity classification are recorded with
  supporting Console/official guidance.
- App-signing and upload-key fingerprints are securely recorded; secrets are not
  in source or ordinary build logs.
- A signed test bundle uploaded to the intended non-production track installs and
  can be updated by a subsequent higher versionCode build.

## C1 — Data, privacy, legal, and policy inventory

### Work

- **C1.1** Build a field-level data inventory covering account identity, journal
  text, routes/precise location, EXIF, photos/videos, species/identification,
  iNaturalist credentials/publications, device/session data, operations/jobs,
  logs, analytics/crash data, backups, maps, and every third party.
- **C1.2** For each field, record collection source, purpose, required/optional
  status, transmission, encryption, retention, deletion, sharing, processor,
  region, and user control. Use runtime/build inspection, not assumptions.
- **C1.3** Publish an accessible privacy policy at a stable public HTTPS URL and
  ensure app, listing, Data Safety, retention, and actual behavior agree.
- **C1.4** Publish support contact/process and, for accounts, a public deletion
  request URL backed by Track B's verified deletion workflow.
- **C1.5** Document terms where appropriate, copyright/trademark ownership, open
  source and map/data attribution, provider terms, offline-map rights, and
  iNaturalist integration disclosures.
- **C1.6** Complete Data Safety from the verified inventory, including transmitted
  location/media and any telemetry. Revisit it whenever code, SDKs, or providers change.
- **C1.7** Complete account deletion, foreground-service, photo/video permission,
  location, health/activity, target audience, ads, content rating, and news/other
  applicable declarations.
- **C1.8** Prepare accurate prominent disclosures and permission rationale where
  Play policy requires them. Permission prompts must follow contextual in-app
  explanation and preserve a useful denied-permission path.
- **C1.9** Establish a policy-change checklist in CI/release review for new Android
  permissions, SDKs, endpoints, data fields, and external processors.

### Exit gates

- Data inventory traces every declared datum to code/config/provider evidence.
- Privacy policy, Data Safety, in-app disclosures, retention, export/deletion, and
  observed network behavior are consistent.
- Account deletion works from both in-app and public web entry points.
- All permission and service declarations match the final manifest and runtime.
- Counsel or an accountable owner has reviewed applicable terms and declarations;
  no roadmap checkbox is treated as legal advice.

## C2 — Store-grade Android artifact

### Work

- **C2.1** Build from the Track A production variant with the current required
  compile/target SDK and compatible Gradle/Kotlin/Compose toolchain.
- **C2.2** Generate a release AAB signed with the protected upload key. Ensure Play
  App Signing configuration and local/internal APK signing expectations are clear.
- **C2.3** Verify minification/resource shrinking, R8 mapping retention, native
  debug-symbol handling, dependency/SBOM scanning, reproducible inputs, and build
  provenance appropriate to the project.
- **C2.4** Inspect the manifest and final Play-generated split APKs for permissions,
  SDK levels, exported components, foreground-service types, debuggability,
  cleartext policy, backup behavior, deep/app links, adaptive icon, and package version.
- **C2.5** Verify 16 KB native-page support and exercise Play-generated artifacts on
  applicable devices, not only the locally built universal APK.
- **C2.6** Prove the artifact contains no secret, pairing credential, service key,
  signed test URL, LAN endpoint, private host, test account, private route/media,
  debug component, or unexpected analytics endpoint.
- **C2.7** Decide and implement the policy-compliant media access strategy while
  maintaining the existing user capability according to Track A. Submit the
  broad-access declaration only if full-library access is demonstrably core and
  the runtime behavior matches it.
- **C2.8** Verify location and foreground service behavior, user initiation,
  notification, stop action, declared types, and review demonstration materials.
- **C2.9** Validate Android vitals instrumentation, crash symbolication, privacy
  redaction, feature flags, minimum-version handling, rollback, and kill switches.

### Exit gates

- Play accepts the AAB in an internal track with no target SDK, signing, native
  compatibility, manifest, or artifact-policy blocker.
- A Play-delivered build installs, starts, pairs/logs in as appropriate, records
  offline, synchronizes, uploads, identifies, publishes, maps, and upgrades.
- The final artifact passes Track A no-regression, security, secret, performance,
  and compatibility gates.
- R8 mapping/native symbols and exact source revision can be retrieved for the build.

## C3 — Store listing and reviewer package

### Work

- **C3.1** Create the public name, short description, full description, category,
  tags, contact details, website, and localization plan without claiming behavior
  the app does not provide.
- **C3.2** Produce a valid high-resolution icon, feature graphic, phone screenshots,
  and required tablet/foldable assets where listed. Screenshots show real final UI
  and contain no personal journal data or misleading device frames/results.
- **C3.3** Prepare reviewer access with a stable test account/environment and
  instructions for offline recording, media permission, location foreground
  service, Species Review, iNaturalist connection/publishing boundaries, maps,
  and account deletion. Never give reviewers the owner's personal pairing key.
- **C3.4** Record permission and foreground-service demonstration videos showing
  the feature, user initiation, notification/stop behavior, and why access is core.
- **C3.5** Verify public support, privacy, deletion, and attribution URLs from an
  unsigned/incognito browser and throughout the expected review period.
- **C3.6** Complete device catalog exclusions only for measured incompatibility,
  not as a substitute for fixing supported devices.

### Exit gates

- Listing assets meet current Console dimensions/content rules and show the
  submitted build accurately.
- A person unfamiliar with the project can follow reviewer instructions without
  access to production personal data.
- Every public URL is stable, HTTPS, responsive on mobile, and owned by the publisher.
- Descriptions, screenshots, declarations, and actual behavior are consistent.

## C4 — Internal, closed, and pre-launch verification

### Work

- **C4.1** Use internal testing for build/install/update/signing smoke tests and
  rapid Track A release verification.
- **C4.2** Run a closed beta covering the intended device/API matrix, OEM background
  restrictions, poor networks, long GPS sessions, large media, low storage,
  permission denial/revocation, account lifecycle, and upgrades.
- **C4.3** If a new personal publisher account is subject to a tester-duration rule,
  satisfy the current Console requirement with real opted-in testers and retain
  evidence. Do not assume an old numeric rule remains current.
- **C4.4** Review Play pre-launch reports for crashes, ANRs, security, accessibility,
  rendering, deep links, and policy findings. Reproduce and resolve applicable issues.
- **C4.5** Perform TalkBack, switch access, keyboard where applicable, large text,
  contrast, touch target, landscape, tablet/foldable, multi-window, and reduced
  motion/sensory review.
- **C4.6** Run backend load/failure exercises using beta traffic assumptions and
  prove dashboards, paging, support, backup/restore, rollback, and feature disables.
- **C4.7** Collect tester feedback without ingesting sensitive journal content into
  an unapproved support/analytics system.

### Exit gates

- Required testing duration/participation and production-access application are
  accepted where applicable.
- No unresolved release-blocking pre-launch, policy, crash/ANR, accessibility,
  security, data-loss, or cross-account issue remains.
- Track A performance/reliability gates pass on Play-delivered artifacts, and
  Track B isolation gates pass for the public lane.
- Support and on-call owners have exercised incident, rollback, and restoration runbooks.

## C5 — Review, staged rollout, and post-launch operations

### Work

- **C5.1** Freeze the release candidate by source revision/versionCode, deploy a
  backward-compatible API/schema first, and run final evidence review.
- **C5.2** Submit with complete app-access instructions and monitor Console messages.
  Changes requested during review return through the same build/test gates.
- **C5.3** Begin with a small staged percentage, then advance through predetermined
  cohorts such as 5, 25, 50, and 100 percent only when gates remain healthy.
- **C5.4** Monitor crash-free users/sessions, ANRs, startup/render performance,
  authentication, sync failure/age, queue depth, API latency/errors, upload and
  deletion failures, storage/egress, iNaturalist failures, account deletion, and
  support volume.
- **C5.5** Define quantitative pause and rollback thresholds before rollout. Use
  server feature flags/compatibility and a previous supported client rather than
  relying on instant store rollback.
- **C5.6** Reconcile listing/data declarations after every material feature, SDK,
  permission, endpoint, processor, or retention change.
- **C5.7** Establish the recurring target-SDK, dependency, certificate/key, policy,
  backup/restore, map/provider terms, privacy, and incident-review calendar.

### Minimum rollout gates

Before expanding a cohort:

- no confirmed data loss, duplicate publication, cross-account exposure, broken
  recording, signing/update failure, or account deletion failure exists;
- crash/ANR and performance metrics are within the stricter of the Track A budget
  or the release's recorded thresholds;
- API readiness, p95 latency, queue age, cleanup backlog, upload failure, and
  external-service error rates remain within their recorded service objectives;
- support volume and issue severity are understood; and
- rollback remains compatible with the live schema and clients.

### Track C definition of done

- Publisher identity, package, signing, and access are verified and recoverable.
- A Play-delivered AAB passes current SDK, 16 KB, manifest, artifact-security,
  permission, foreground-service, and no-regression gates.
- Policy declarations, privacy, retention, account deletion, support, reviewer
  access, listing assets, and actual runtime behavior agree.
- Required internal/closed/pre-launch testing has passed.
- Public release, when pursued, uses Track B identities and tenant isolation rather
  than a global pairing key.
- Staged rollout reaches its approved audience without crossing defined halt
  thresholds, and recurring post-launch operations are assigned.

## Webapp changes required by Track C

Track C does not require a Streamlit product redesign. It does require a stable
public web presence for privacy, support, and—when accounts exist—account deletion.
Those pages may be hosted separately from Streamlit.

The webapp itself requires changes only when it is used for:

- the Track B identity/account lifecycle underlying the public application;
- an authenticated account export or deletion flow;
- reviewer access or documented web handoff behavior; or
- correcting behavior disclosed by the store's verified data inventory.

Any such change remains subject to the shared no-regression invariant.
