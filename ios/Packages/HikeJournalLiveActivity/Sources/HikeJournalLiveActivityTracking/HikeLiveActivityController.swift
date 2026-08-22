import Foundation
import HikeJournalLiveActivity
import HikeJournalTracking

public enum HikeLiveActivityStateFactory {
    public static func make(
        snapshot: TrackingSnapshot,
        now: Date = Date(),
        overridingPhase: HikeLiveActivityPhase? = nil
    ) -> HikeLiveActivityState {
        let mappedPhase: HikeLiveActivityPhase = switch snapshot.status {
        case .starting, .recording: HikeLiveActivityPhase.recording
        case .paused: HikeLiveActivityPhase.paused
        case .finalizing, .finished: HikeLiveActivityPhase.finished
        }
        let phase = overridingPhase ?? mappedPhase
        return HikeLiveActivityState(
            phase: phase,
            distanceMeters: snapshot.distanceMeters,
            activeElapsedMilliseconds: snapshot.activeElapsedMilliseconds,
            updatedAt: now,
            pointCount: snapshot.pointCount
        )
    }
}

@MainActor
public protocol HikeLiveActivityControlling: AnyObject {
    func start(for snapshot: TrackingSnapshot) async
    func update(for snapshot: TrackingSnapshot) async
    func end(for snapshot: TrackingSnapshot?, discarded: Bool) async
}

@MainActor
public final class NoopHikeLiveActivityController: HikeLiveActivityControlling {
    public init() {}
    public func start(for snapshot: TrackingSnapshot) async {}
    public func update(for snapshot: TrackingSnapshot) async {}
    public func end(for snapshot: TrackingSnapshot?, discarded: Bool) async {}
}

#if os(iOS) && canImport(ActivityKit)
import ActivityKit

@available(iOS 16.1, *)
@MainActor
public final class SystemHikeLiveActivityController: HikeLiveActivityControlling {
    private var activity: Activity<HikeActivityAttributes>?

    public init() {}

    public func start(for snapshot: TrackingSnapshot) async {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }
        if let current = matchingActivity(recordingID: snapshot.sessionID) {
            activity = current
            await update(for: snapshot)
            return
        }
        await endUnrelatedActivities()
        do {
            let attributes = HikeActivityAttributes(
                recordingID: snapshot.sessionID,
                hikeID: snapshot.hikeID,
                startedAt: snapshot.startedAt
            )
            let state = HikeLiveActivityStateFactory.make(snapshot: snapshot)
            activity = try Activity.request(
                attributes: attributes,
                content: ActivityContent(state: state, staleDate: nil),
                pushType: nil
            )
        } catch {
            // A Live Activity is supplementary. Recording must continue even
            // when the user disabled activities or the system rejects a request.
            activity = nil
        }
    }

    public func update(for snapshot: TrackingSnapshot) async {
        if activity == nil {
            activity = matchingActivity(recordingID: snapshot.sessionID)
        }
        guard let activity else {
            await start(for: snapshot)
            return
        }
        let state = HikeLiveActivityStateFactory.make(snapshot: snapshot)
        await activity.update(ActivityContent(state: state, staleDate: nil))
    }

    public func end(for snapshot: TrackingSnapshot?, discarded: Bool) async {
        let activities: [Activity<HikeActivityAttributes>]
        if let activity {
            activities = [activity]
        } else if let snapshot {
            activities = Activity<HikeActivityAttributes>.activities.filter {
                $0.attributes.recordingID == snapshot.sessionID
            }
        } else {
            activities = Activity<HikeActivityAttributes>.activities
        }
        for activity in activities {
            let finalState = snapshot.map {
                HikeLiveActivityStateFactory.make(
                    snapshot: $0,
                    overridingPhase: .finished
                )
            } ?? activity.content.state
            let policy: ActivityUIDismissalPolicy = discarded
                ? .immediate
                : .after(Date().addingTimeInterval(60))
            await activity.end(
                ActivityContent(state: finalState, staleDate: Date()),
                dismissalPolicy: policy
            )
        }
        activity = nil
    }

    private func matchingActivity(recordingID: String) -> Activity<HikeActivityAttributes>? {
        Activity<HikeActivityAttributes>.activities.first {
            $0.attributes.recordingID == recordingID
        }
    }

    private func endUnrelatedActivities() async {
        for existing in Activity<HikeActivityAttributes>.activities {
            await existing.end(nil, dismissalPolicy: .immediate)
        }
    }
}
#endif

@MainActor
public func makeSystemHikeLiveActivityController() -> any HikeLiveActivityControlling {
    #if os(iOS) && canImport(ActivityKit)
    if #available(iOS 16.1, *) {
        return SystemHikeLiveActivityController()
    }
    #endif
    return NoopHikeLiveActivityController()
}
