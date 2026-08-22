import Foundation

public enum HikeLiveActivityPhase: String, Codable, CaseIterable, Hashable, Sendable {
    case recording
    case paused
    case finished
}

public struct HikeLiveActivityState: Codable, Hashable, Sendable {
    public let phase: HikeLiveActivityPhase
    public let distanceMeters: Double
    public let activeElapsedMilliseconds: Int64
    public let updatedAt: Date
    public let pointCount: Int

    public init(
        phase: HikeLiveActivityPhase,
        distanceMeters: Double,
        activeElapsedMilliseconds: Int64,
        updatedAt: Date,
        pointCount: Int
    ) {
        self.phase = phase
        self.distanceMeters = max(0, distanceMeters.isFinite ? distanceMeters : 0)
        self.activeElapsedMilliseconds = max(0, activeElapsedMilliseconds)
        self.updatedAt = updatedAt
        self.pointCount = max(0, pointCount)
    }

    public var distanceMiles: Double { distanceMeters / 1_609.344 }

    /// The anchor lets WidgetKit render a live timer without waking the app.
    /// Paused/finished activities display the stored elapsed duration instead.
    public var runningTimerAnchor: Date {
        updatedAt.addingTimeInterval(-Double(activeElapsedMilliseconds) / 1_000)
    }

    public var elapsedText: String {
        let totalSeconds = max(0, activeElapsedMilliseconds / 1_000)
        let hours = totalSeconds / 3_600
        let minutes = (totalSeconds % 3_600) / 60
        let seconds = totalSeconds % 60
        return hours > 0
            ? String(format: "%lld:%02lld:%02lld", hours, minutes, seconds)
            : String(format: "%02lld:%02lld", minutes, seconds)
    }

    public var distanceText: String {
        String(format: "%.2f mi", distanceMiles)
    }
}

#if os(iOS) && canImport(ActivityKit)
import ActivityKit

@available(iOS 16.1, *)
public struct HikeActivityAttributes: ActivityAttributes {
    public typealias ContentState = HikeLiveActivityState

    public let recordingID: String
    public let hikeID: String
    public let startedAt: Date

    public init(recordingID: String, hikeID: String, startedAt: Date) {
        self.recordingID = recordingID
        self.hikeID = hikeID
        self.startedAt = startedAt
    }
}
#endif
