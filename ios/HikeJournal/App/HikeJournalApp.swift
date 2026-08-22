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
                    await model.startMaps()
                    await model.authentication.restore()
                    await model.startSync()
                    await model.storefront.configureForCurrentAccount()
                    await model.startJournal()
                    await model.restoreRecording()
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
                RootShellView(model: model)
                    .transition(reduceMotion ? .opacity : .move(edge: .trailing).combined(with: .opacity))
            }
        }
        .animation(reduceMotion ? nil : .snappy(duration: 0.48), value: model.phase)
    }
}
