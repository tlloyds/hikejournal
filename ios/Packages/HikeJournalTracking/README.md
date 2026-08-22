# HikeJournalTracking

Pure Swift tracking domain package with no app target, Core Location, database,
speech, or UI dependency. It ports the Android recorder's accepted-fix rules,
state transitions, recovery semantics, route segmentation, field marks,
whole-mile milestones, and Garmin TCX v2 output.

## Integration surface

Create a persistable session with injected dependencies, then keep the mutable
`Sendable` value inside an app-owned actor:

```swift
let clock = TrackingClock.system
var session = TrackingSession.start(
    clock: clock,
    idGenerator: .random,
    calendar: .current
)
try session.beginRecording(at: clock.read())

let result = session.ingest(
    LocationSample(
        latitude: location.coordinate.latitude,
        longitude: location.coordinate.longitude,
        altitudeMeters: location.verticalAccuracy >= 0 ? location.altitude : nil,
        horizontalAccuracyMeters: location.horizontalAccuracy,
        timestamp: location.timestamp,
        monotonicTimestampNanoseconds: monotonicNanoseconds
    ),
    receivedAt: clock.read().wallTime
)
```

Persist `TrackingSession` with `Codable`. Call `checkpoint(at:)` on the app's
durable cadence, `pause(at:)` / `resume(at:)` for user transitions, and
`recoverAfterInterruption(at:)` after process restoration. Recovery always
returns an interrupted active/finalizing session paused and preserves only its
checkpointed active time.

Use `makeFieldMark(type:note:at:idGenerator:)` after the first accepted fix,
`WholeMileAnnouncementScheduler.update(...)` to drive speech, and
`TCXWriter.write(snapshot:notes:)` after paused finalization. `TCXDocument`
excludes singleton segments just like Android.

App integration still owns Core Location/background execution, permission and
notification policy, persistence transactions/checkpoint scheduling, speech,
upload/sync, and adding this local package dependency to the Xcode project.
Those platform concerns are intentionally outside this independent package.
