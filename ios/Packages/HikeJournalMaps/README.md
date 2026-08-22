# HikeJournalMaps

An iOS 17 Swift package for HikeJournal's MapLibre map surface, pure map
domain, National Scenic Trail overlays, and bounded offline packs. MapLibre is
the official `maplibre-gl-native-distribution` Swift package, pinned exactly to
the audited `6.28.0` release and product `MapLibre`.

The domain and context code also build on macOS so geometry, validation,
attribution, accessibility, and persistence behavior can be tested without an
iOS runtime. MapLibre and SwiftUI adapters are conditionally compiled for iOS.

## App integration

Add this local package to the app target, then build a validated style at the
app's configuration boundary. There is deliberately no bundled demo style,
provider token, or fallback that silently changes map licensing.

```swift
let attribution = try MapAttribution(
  id: "production-map-provider",
  title: "Map provider and data contributors",
  url: URL(string: "https://maps.your-provider.example/attribution")!
)
let style = try MapStyleConfiguration(
  id: "production-outdoors",
  styleURL: URL(string: "https://maps.your-provider.example/styles/outdoors.json")!,
  attribution: attribution,
  tokenQueryItemName: "key" // nil when the provider does not require one
)
let credential = try MapStyleCredential(valueLoadedFromAppConfiguration)

let map = try HikeJournalMapSurface(
  scene: scene,
  style: style,
  styleCredential: credential
)
```

Load the style URL and token through an app-owned build setting, managed
configuration, or secret provider. Do not commit a production token or include
it in `MapScene` or offline context. URL and credential validation fail closed:
styles and attribution must use HTTPS, credentials cannot be embedded in URL
userinfo, and a configured token query item requires a runtime credential.

The MapLibre logo and built-in attribution control stay enabled. The SwiftUI
surface additionally renders required links for the configured style and each
selected trail source. The app must not hide either attribution surface or
remove notices required by its style/tile provider.

`MapScene` accepts recorded multi-segment routes, a supplied current location,
and typed map points for geotagged photos/videos, field marks, sightings,
discoveries, and places. The package does not request location permission or
start location tracking. `MapAccessibility.snapshot(for:)` provides a concise
map summary and ordered text alternatives suitable for an app-owned details
sheet or VoiceOver fallback. Camera fitting uses the minimum longitude arc, so
routes and regions around the international date line do not zoom out to the
whole world.

## National Scenic Trail overlays

`NationalScenicTrailCatalog.all` is a source-for-source port of Android's 11
currently supported overlays: Appalachian, Pacific Crest, Continental Divide,
Florida, Arizona, Ice Age, Natchez Trace, New England, North Country, Pacific
Northwest, and Potomac Heritage. The three featured flags, FID overrides, both
North Country layers, and every production ArcGIS FeatureServer URL are
preserved. The iOS surface uses the same 2,000-feature pagination, 20-page cap,
WGS84 output, and geometry simplification request as Android, then renders
selected trails in orange. It does not substitute sample or demo geometry.

Trail FeatureServer responses are held in the surface loader's memory cache.
They are dynamic GeoJSON overlays and are not automatically incorporated into
an `MLNTilePyramidOfflineRegion`; if trail overlays must remain available after
process termination with no network, the app should add an explicitly reviewed
durable GeoJSON cache policy later.

## Offline maps and entitlement ownership

Offline-map entitlement gating is app-owned. Before calling `create`, the app
must obtain its fresh server-authoritative entitlement and verify the relevant
feature flag. This package intentionally has no plan enum, paid Boolean,
receipt interpretation, Android compatibility bypass, or local mechanism that
can grant access. Existing packs may still be listed or deleted according to
app policy even after access changes.

MapLibre's network policy is global and its URL sessions copy the configuration
when first created. Construct `MapLibreOfflinePackStore` before any
`HikeJournalMapSurface` or other MapLibre object:

```swift
let offlineStore = await MapLibreOfflinePackStore(
  networkPolicy: .wifiOnly,
  maximumAllowedTiles: 50_000
)

// App-owned authoritative entitlement check happens here.
guard entitlement.features.offlineMaps else { return }

let request = try OfflinePackRequest(
  name: "Weekend route",
  style: style,
  styleCredential: credential,
  bounds: try MapCoordinateBounds(
    south: 28.45,
    west: -81.75,
    north: 28.85,
    east: -81.25
  ),
  minimumZoomLevel: 9,
  maximumZoomLevel: 14,
  networkPolicy: .wifiOnly
)
let initial = try await offlineStore.create(request)

for await update in try await offlineStore.updates(id: initial.id) {
  // update.state: unknown, inactive, downloading, complete, failed, invalid
  // update.progress and update.failure are safe UI payloads.
}
```

The production actor exposes these operations:

```swift
create(_:automaticallyResume:) async throws -> OfflinePackSnapshot
list() async throws -> [OfflinePackSnapshot]
status(id:) async throws -> OfflinePackSnapshot
resume(id:) async throws -> OfflinePackSnapshot
suspend(id:) async throws -> OfflinePackSnapshot
delete(id:) async throws
updates(id:) async throws -> AsyncStream<OfflinePackSnapshot>
totalStorageBytes() async -> UInt64
```

Requests validate Web Mercator latitude, nonzero bounds, antimeridian-safe
longitude span, zoom range, maximum geographic span, and an estimated 50,000
tile ceiling before calling MapLibre. `OfflineStorageEstimate` is a conservative
planning range, while snapshots report MapLibre's actual resource, tile, and
byte progress plus total MapLibre database bytes (offline packs and ambient
cache). The JSON context is deterministic,
bounded to 16 KiB, versioned, tamper-checked, and never stores the runtime style
credential. Equivalent region keys and in-flight reservations prevent duplicate
packs. Deleting a pack makes unshared resources eligible for cleanup; MapLibre's
ambient cache may retain useful shared resources, so disk bytes need not fall
immediately.

`.wifiOnly` sets MapLibre's supported `URLSessionConfiguration` controls to
disallow cellular, expensive, and constrained access. `.anyNetwork` enables
them. Because this is SDK-global setup, all requests submitted to one actor must
match the actor's policy.

## Verification

From this directory:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  swift test -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors

DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  swift build \
  --triple arm64-apple-ios17.0-simulator \
  --sdk /Applications/Xcode.app/Contents/Developer/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator26.5.sdk \
  -Xswiftc -strict-concurrency=complete -Xswiftc -warnings-as-errors
```
