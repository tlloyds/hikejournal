import SwiftUI

@main
@MainActor
struct HikeJournalApp: App {
    @StateObject private var model: AppModel
    @Environment(\.scenePhase) private var scenePhase

    init() {
        let environment = AppEnvironment.live()
        let model = AppModel(environment: environment)
        model.sync.registerBackgroundTasks()
        _model = StateObject(wrappedValue: model)
    }

    var body: some Scene {
        WindowGroup {
            AppRootView(model: model)
                .tint(HikeJournalTheme.trail)
                .task {
                    await model.bootstrap()
                }
                .onOpenURL { url in
                    if !model.authentication.handleGoogleRedirect(url) {
                        model.handleDeepLink(url)
                    }
                }
                .onChange(of: scenePhase) { _, nextPhase in
                    switch nextPhase {
                    case .active:
                        Task { await model.applicationBecameActive() }
                    case .background:
                        model.applicationEnteredBackground()
                    case .inactive:
                        break
                    @unknown default:
                        break
                    }
                }
        }
    }
}

private struct AppRootView: View {
    @ObservedObject var model: AppModel
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            switch model.phase {
            case .onboarding:
                OnboardingView(model: model)
                    .transition(reduceMotion ? .opacity : .move(edge: .leading).combined(with: .opacity))
            case .journal:
                Group {
                    if model.isBootstrapped {
                        RootShellView(model: model)
                    } else {
                        JournalBootstrapView()
                    }
                }
                    .transition(reduceMotion ? .opacity : .move(edge: .trailing).combined(with: .opacity))
            }
        }
        .animation(reduceMotion ? nil : .snappy(duration: 0.48), value: model.phase)
    }
}

struct JournalBootstrapView: View {
    var body: some View {
        ZStack {
            ParchmentBackground()
            ProgressView("Opening your field journal…")
                .font(HikeJournalTheme.body())
                .tint(HikeJournalTheme.trail)
        }
    }
}
