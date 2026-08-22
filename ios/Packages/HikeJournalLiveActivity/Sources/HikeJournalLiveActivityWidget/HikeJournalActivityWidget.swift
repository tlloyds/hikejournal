#if os(iOS) && canImport(ActivityKit) && canImport(WidgetKit) && canImport(SwiftUI)
import ActivityKit
import HikeJournalLiveActivity
import SwiftUI
import WidgetKit

@available(iOSApplicationExtension 16.1, *)
public struct HikeJournalActivityWidget: Widget {
    public init() {}

    public var body: some WidgetConfiguration {
        ActivityConfiguration(for: HikeActivityAttributes.self) { context in
            HikeJournalLockScreenActivity(context: context)
                .activityBackgroundTint(Color(red: 0.08, green: 0.17, blue: 0.13))
                .activitySystemActionForegroundColor(.white)
                .widgetURL(trackingURL("open"))
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    activityMark
                }
                DynamicIslandExpandedRegion(.trailing) {
                    distance(context.state)
                }
                DynamicIslandExpandedRegion(.center) {
                    Text(context.state.phase == .paused ? "ROUTE PAUSED" : "FOLLOWING YOUR LINE")
                        .font(.system(size: 11, weight: .bold, design: .rounded))
                        .tracking(0.7)
                        .foregroundStyle(trail)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    HStack {
                        elapsed(context.state)
                        Spacer()
                        activityLinks(context.state)
                    }
                    .padding(.horizontal, 4)
                }
            } compactLeading: {
                Image(systemName: context.state.phase == .paused ? "pause.fill" : "figure.hiking")
                    .foregroundStyle(trail)
            } compactTrailing: {
                Text(String(format: "%.1f", context.state.distanceMiles))
                    .font(.system(size: 13, weight: .bold, design: .rounded))
                    .foregroundStyle(.white)
            } minimal: {
                Image(systemName: "figure.hiking")
                    .foregroundStyle(trail)
            }
            .widgetURL(trackingURL("open"))
            .keylineTint(trail)
        }
    }

    private var activityMark: some View {
        VStack(alignment: .leading, spacing: 1) {
            Text("HIKE")
                .font(.system(size: 10, weight: .bold, design: .rounded))
                .tracking(1)
                .foregroundStyle(trail)
            Text("JOURNAL")
                .font(.system(size: 14, weight: .semibold, design: .serif))
                .foregroundStyle(.white)
        }
    }

    private func distance(_ state: HikeLiveActivityState) -> some View {
        VStack(alignment: .trailing, spacing: 0) {
            Text(String(format: "%.2f", state.distanceMiles))
                .font(.system(size: 18, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
            Text("MILES")
                .font(.system(size: 9, weight: .bold, design: .rounded))
                .tracking(0.8)
                .foregroundStyle(Color.white.opacity(0.68))
        }
    }

    @ViewBuilder
    private func elapsed(_ state: HikeLiveActivityState) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            if state.phase == .recording {
                Text(state.runningTimerAnchor, style: .timer)
                    .monospacedDigit()
            } else {
                Text(state.elapsedText)
                    .monospacedDigit()
            }
            Text("ACTIVE")
                .font(.system(size: 9, weight: .bold, design: .rounded))
                .tracking(0.8)
                .foregroundStyle(Color.white.opacity(0.64))
        }
        .font(.system(size: 17, weight: .bold, design: .rounded))
        .foregroundStyle(.white)
    }

    private func activityLinks(_ state: HikeLiveActivityState) -> some View {
        HStack(spacing: 8) {
            Link(destination: trackingURL(state.phase == .paused ? "resume" : "pause")!) {
                Image(systemName: state.phase == .paused ? "play.fill" : "pause.fill")
                    .frame(width: 34, height: 28)
                    .background(Color.white.opacity(0.14), in: Capsule())
            }
            Link(destination: trackingURL("stop")!) {
                Image(systemName: "flag.checkered")
                    .frame(width: 34, height: 28)
                    .background(trail.opacity(0.28), in: Capsule())
            }
        }
        .foregroundStyle(.white)
    }

    private var trail: Color { Color(red: 0.89, green: 0.52, blue: 0.28) }
}

@available(iOSApplicationExtension 16.1, *)
private struct HikeJournalLockScreenActivity: View {
    let context: ActivityViewContext<HikeActivityAttributes>

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 0) {
                    Text("HIKEJOURNAL")
                        .font(.system(size: 12, weight: .bold, design: .rounded))
                        .tracking(1.2)
                        .foregroundStyle(trail)
                    Text(context.state.phase == .paused ? "The route is safe." : "Following your line.")
                        .font(.system(size: 24, weight: .semibold, design: .serif))
                        .foregroundStyle(.white)
                }
                Spacer()
                Image(systemName: context.state.phase == .paused ? "pause.circle.fill" : "location.circle.fill")
                    .font(.system(size: 28, weight: .medium))
                    .foregroundStyle(trail)
            }

            HStack(spacing: 24) {
                metric(value: context.state.distanceText, label: "DISTANCE")
                VStack(alignment: .leading, spacing: 0) {
                    if context.state.phase == .recording {
                        Text(context.state.runningTimerAnchor, style: .timer)
                            .monospacedDigit()
                    } else {
                        Text(context.state.elapsedText)
                            .monospacedDigit()
                    }
                    Text("ACTIVE")
                        .font(.system(size: 9, weight: .bold, design: .rounded))
                        .tracking(0.8)
                        .foregroundStyle(Color.white.opacity(0.62))
                }
                .font(.system(size: 18, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
                metric(value: String(context.state.pointCount), label: "POINTS")
                Spacer(minLength: 0)
                HStack(spacing: 8) {
                    Link(destination: trackingURL(context.state.phase == .paused ? "resume" : "pause")!) {
                        Image(systemName: context.state.phase == .paused ? "play.fill" : "pause.fill")
                            .frame(width: 42, height: 34)
                            .background(Color.white.opacity(0.13), in: Capsule())
                    }
                    Link(destination: trackingURL("stop")!) {
                        Image(systemName: "flag.checkered")
                            .frame(width: 42, height: 34)
                            .background(trail.opacity(0.28), in: Capsule())
                    }
                }
                .foregroundStyle(.white)
            }
        }
        .padding(16)
    }

    private func metric(value: String, label: String) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(value)
                .font(.system(size: 18, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
            Text(label)
                .font(.system(size: 9, weight: .bold, design: .rounded))
                .tracking(0.8)
                .foregroundStyle(Color.white.opacity(0.62))
        }
    }

    private var trail: Color { Color(red: 0.89, green: 0.52, blue: 0.28) }
}

private func trackingURL(_ action: String) -> URL? {
    URL(string: "hikejournal://tracking/\(action)")
}
#endif
