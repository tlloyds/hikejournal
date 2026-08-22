import Foundation
import HikeJournalLiveActivity
import HikeJournalLiveActivityTracking
import HikeJournalTracking
import Testing

struct HikeLiveActivityStateTests {
    @Test func mapsRecordingSnapshotAndBuildsTimerAnchor() {
        let now = Date(timeIntervalSince1970: 10_000)
        let state = HikeLiveActivityStateFactory.make(
            snapshot: snapshot(status: .recording, elapsed: 125_000, distance: 3_218.688),
            now: now
        )

        #expect(state.phase == .recording)
        #expect(abs(state.distanceMiles - 2) < 0.000_001)
        #expect(state.elapsedText == "02:05")
        #expect(state.runningTimerAnchor == now.addingTimeInterval(-125))
    }

    @Test func mapsPauseAndFinishedStates() {
        #expect(HikeLiveActivityStateFactory.make(snapshot: snapshot(status: .paused)).phase == .paused)
        #expect(HikeLiveActivityStateFactory.make(snapshot: snapshot(status: .finalizing)).phase == .finished)
        #expect(HikeLiveActivityStateFactory.make(snapshot: snapshot(status: .finished)).phase == .finished)
    }

    @Test func sanitizesUnsafeMetrics() {
        let state = HikeLiveActivityState(
            phase: .recording,
            distanceMeters: .nan,
            activeElapsedMilliseconds: -4,
            updatedAt: .distantPast,
            pointCount: -3
        )
        #expect(state.distanceMeters == 0)
        #expect(state.activeElapsedMilliseconds == 0)
        #expect(state.pointCount == 0)
    }

    private func snapshot(
        status: TrackingStatus,
        elapsed: Int64 = 0,
        distance: Double = 0
    ) -> TrackingSnapshot {
        TrackingSnapshot(
            sessionID: "recording-1",
            hikeID: "hike-1",
            status: status,
            startedAt: Date(timeIntervalSince1970: 9_000),
            hikeDate: "2026-08-22",
            distanceMeters: distance,
            activeElapsedMilliseconds: elapsed,
            currentSegment: 0,
            routeSegments: [],
            lastAccuracyMeters: nil,
            lastFixTimestamp: nil,
            pointCount: 7,
            generatedTCXPath: nil,
            recoveryReason: nil,
            errorMessage: nil
        )
    }
}
