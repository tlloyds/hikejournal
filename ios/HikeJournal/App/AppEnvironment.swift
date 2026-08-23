import Combine
import CoreLocation
import Foundation
import HikeJournalStoreKit

@MainActor
struct AppEnvironment {
    let configuration: AppConfiguration
    let version: AppVersion
    let onboardingStore: OnboardingStoring
    let locationPermission: LocationPermissionClient
    let authenticationAPI: (any AuthenticationAPI)?
    let syncAPIClient: APIClient?
    let featureAPI: (any HikeJournalFeatureAPI)?
    let appleSignIn: (any AppleSignInAuthorizing)?
    let googleSignIn: (any GoogleSignInAuthorizing)?
    let offlineStores: OfflineStoreCoordinator?
    let storeKitCoordinator: StoreKitCoordinator?
    let preferencesDefaults: UserDefaults
    let now: () -> Date

    init(
        configuration: AppConfiguration,
        version: AppVersion,
        onboardingStore: OnboardingStoring,
        locationPermission: LocationPermissionClient,
        authenticationAPI: (any AuthenticationAPI)? = nil,
        syncAPIClient: APIClient? = nil,
        featureAPI: (any HikeJournalFeatureAPI)? = nil,
        appleSignIn: (any AppleSignInAuthorizing)? = nil,
        googleSignIn: (any GoogleSignInAuthorizing)? = nil,
        offlineStores: OfflineStoreCoordinator? = nil,
        storeKitCoordinator: StoreKitCoordinator? = nil,
        preferencesDefaults: UserDefaults = .standard,
        now: @escaping () -> Date
    ) {
        self.configuration = configuration
        self.version = version
        self.onboardingStore = onboardingStore
        self.locationPermission = locationPermission
        self.authenticationAPI = authenticationAPI
        self.syncAPIClient = syncAPIClient
        self.featureAPI = featureAPI
        self.appleSignIn = appleSignIn
        self.googleSignIn = googleSignIn
        self.offlineStores = offlineStores
        self.storeKitCoordinator = storeKitCoordinator
        self.preferencesDefaults = preferencesDefaults
        self.now = now
    }

    static func live(
        bundle: Bundle = .main,
        defaults: UserDefaults = .standard
    ) -> AppEnvironment {
        let configuration = AppConfiguration(infoDictionary: bundle.infoDictionary ?? [:])
        let sessionStore = KeychainSessionStore()
        let apiClient = APIClient(
            baseURL: configuration.apiBaseURL,
            apiKey: configuration.apiKey,
            sessionStore: sessionStore
        )
        return AppEnvironment(
            configuration: configuration,
            version: AppVersion(bundle: bundle),
            onboardingStore: DefaultsOnboardingStore(defaults: defaults),
            locationPermission: SystemLocationPermissionClient(),
            authenticationAPI: apiClient,
            syncAPIClient: apiClient,
            featureAPI: apiClient,
            appleSignIn: AppleSignInCoordinator(),
            googleSignIn: GoogleSignInCoordinator(
                clientID: configuration.googleIOSClientID,
                serverClientID: configuration.googleServerClientID
            ),
            offlineStores: try? OfflineStoreCoordinator(),
            storeKitCoordinator: StoreKitCoordinator(
                store: StoreKit2Client(),
                server: apiClient
            ),
            preferencesDefaults: defaults,
            now: Date.init
        )
    }
}

enum AppPhase: Equatable {
    case onboarding
    case journal
}

enum AppTab: Hashable {
    case journal
    case fieldGuide
    case record
    case map
    case settings
}

@MainActor
final class AppModel: ObservableObject {
    @Published var phase: AppPhase
    @Published var selectedTab: AppTab = .journal
    @Published private(set) var isBootstrapped = false
    @Published private(set) var isSettingsPresented = false
    @Published private(set) var locationAuthorization: CLAuthorizationStatus
    @Published private(set) var pendingDeepLink: DeepLink?

    let configuration: AppConfiguration
    let version: AppVersion
    let authentication: AuthenticationStore
    let recording: RecordingStore
    let storefront: StorefrontStore
    let sync: SyncStore
    let journal: JournalStore
    let media: MediaAttachmentStore
    let maps: MapStore
    let riverGauges: RiverGaugePreferencesStore

    private let onboardingStore: OnboardingStoring
    private let locationPermission: LocationPermissionClient
    private let deepLinkRouter: DeepLinkRouter
    private var recordingPhaseObservation: AnyCancellable?

    init(environment: AppEnvironment) {
        configuration = environment.configuration
        version = environment.version
        onboardingStore = environment.onboardingStore
        locationPermission = environment.locationPermission
        deepLinkRouter = DeepLinkRouter(callbackScheme: environment.configuration.callbackScheme)
        let authentication = AuthenticationStore(
            api: environment.authenticationAPI ?? UnavailableAuthenticationAPI(),
            appleSignIn: environment.appleSignIn ?? UnavailableAppleSignInAuthorizer(),
            googleSignIn: environment.googleSignIn
        )
        self.authentication = authentication
        riverGauges = RiverGaugePreferencesStore(defaults: environment.preferencesDefaults)
        maps = MapStore(
            configuration: environment.configuration,
            authentication: authentication
        )
        let recording = RecordingStore(
            authentication: authentication,
            offlineStores: environment.offlineStores
        )
        self.recording = recording
        storefront = StorefrontStore(
            authentication: authentication,
            coordinator: environment.storeKitCoordinator
        )
        let sync = SyncStore(
            authentication: authentication,
            offlineStores: environment.offlineStores,
            apiClient: environment.syncAPIClient
        )
        self.sync = sync
        journal = JournalStore(
            authentication: authentication,
            api: environment.featureAPI ?? UnavailableHikeJournalFeatureAPI(),
            offlineStores: environment.offlineStores,
            sync: sync
        )
        media = MediaAttachmentStore(
            authentication: authentication,
            offlineStores: environment.offlineStores,
            onQueued: { [weak sync] in
                await sync?.workWasQueued()
            }
        )
        locationAuthorization = environment.locationPermission.authorizationStatus
        phase = environment.onboardingStore.hasCompleted ? .journal : .onboarding

        locationPermission.authorizationDidChange = { [weak self] status in
            self?.locationAuthorization = status
        }
        recordingPhaseObservation = recording.$phase
            .removeDuplicates()
            .sink { [weak self] phase in
                guard phase == .finished else { return }
                Task { await self?.sync.workWasQueued() }
            }
    }

    func completeOnboarding(openRecording: Bool = false) {
        onboardingStore.markCompleted()
        selectedTab = openRecording ? .record : .journal
        phase = .journal
    }

    func replayOnboarding() {
        phase = .onboarding
    }

    func openRecording() {
        selectedTab = .record
    }

    func openSettings() {
        isSettingsPresented = true
    }

    func closeSettings() {
        isSettingsPresented = false
    }

    func requestWhenInUseLocation() {
        locationPermission.requestWhenInUse()
    }

    func restoreRecording() async {
        await recording.restoreIfNeeded()
    }

    func startSync() async {
        await sync.start()
    }

    func startJournal() async {
        await journal.start()
    }

    func startMaps() async {
        await maps.start()
    }

    func bootstrap() async {
        isBootstrapped = false
        await startMaps()
        await authentication.restore()
        await startSync()
        await storefront.configureForCurrentAccount()
        await startJournal()
        await restoreRecording()
        isBootstrapped = true
    }

    func applicationBecameActive() async {
        await sync.applicationBecameActive()
    }

    func applicationEnteredBackground() {
        sync.applicationEnteredBackground()
    }

    @discardableResult
    func handleDeepLink(_ url: URL) -> Bool {
        guard let destination = deepLinkRouter.destination(for: url) else { return false }
        pendingDeepLink = destination
        phase = .journal
        switch destination {
        case .hike:
            selectedTab = .journal
        case .inaturalist:
            openSettings()
        case .tracking:
            selectedTab = .record
        }
        return true
    }

    func consumeDeepLink() {
        pendingDeepLink = nil
    }
}
