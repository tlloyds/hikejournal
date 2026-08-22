import XCTest
@testable import HikeJournal

@MainActor
final class AuthenticationStoreTests: XCTestCase {
    func testRestoreUsesDurableAccountAndKeepsItAvailableWhenEntitlementIsOffline() async {
        let session = makeSession()
        let api = MockAuthenticationAPI(session: session, entitlementFailure: true)
        let store = AuthenticationStore(
            api: api,
            appleSignIn: MockAppleAuthorizer(result: .failure(AppleSignInError.cancelled))
        )

        await store.restore()

        XCTAssertEqual(store.phase, .signedIn(session.account))
        XCTAssertNil(store.entitlement)
        XCTAssertNil(store.errorMessage)
    }

    func testAppleSignInSendsRawNonceAndPublishesServerAccount() async {
        let authorization = AppleAuthorizationPayload(
            identityToken: "identity-token",
            rawNonce: "raw-nonce-1234567890",
            displayName: "Trail Name"
        )
        let session = makeSession()
        let entitlement = makeEntitlement(plan: .plus)
        let api = MockAuthenticationAPI(
            session: nil,
            signInSession: session,
            entitlement: entitlement
        )
        let store = AuthenticationStore(
            api: api,
            appleSignIn: MockAppleAuthorizer(result: .success(authorization))
        )

        await store.restore()
        await store.signInWithApple()

        let receivedAuthorization = await api.receivedAuthorization()
        XCTAssertEqual(receivedAuthorization, authorization)
        XCTAssertEqual(store.phase, .signedIn(session.account))
        XCTAssertEqual(store.entitlement?.plan, .plus)
        XCTAssertNil(store.errorMessage)
    }

    func testAppleCancellationLeavesSignedOutStateWithoutError() async {
        let api = MockAuthenticationAPI(session: nil)
        let store = AuthenticationStore(
            api: api,
            appleSignIn: MockAppleAuthorizer(result: .failure(AppleSignInError.cancelled))
        )

        await store.restore()
        await store.signInWithApple()

        XCTAssertEqual(store.phase, .signedOut)
        XCTAssertNil(store.errorMessage)
    }

    func testGoogleSignInSendsOfficialIDTokenWithoutAndroidNonce() async {
        let session = makeSession()
        let api = MockAuthenticationAPI(
            session: nil,
            signInSession: session,
            entitlement: makeEntitlement(plan: .plus)
        )
        let google = MockGoogleAuthorizer(
            configured: true,
            result: .success(GoogleAuthorizationPayload(identityToken: "verified-google-id-token"))
        )
        let store = AuthenticationStore(
            api: api,
            appleSignIn: MockAppleAuthorizer(result: .failure(AppleSignInError.cancelled)),
            googleSignIn: google
        )

        await store.restore()
        await store.signInWithGoogle()

        let request = await api.receivedGoogleRequest()
        XCTAssertEqual(request?.credential, "verified-google-id-token")
        XCTAssertNil(request?.nonce)
        XCTAssertEqual(store.phase, .signedIn(session.account))
        XCTAssertEqual(store.entitlement?.plan, .plus)
        XCTAssertNil(store.errorMessage)
    }

    func testGoogleCancellationRemainsSignedOutAndShowsNoError() async {
        let api = MockAuthenticationAPI(session: nil)
        let google = MockGoogleAuthorizer(
            configured: true,
            result: .failure(GoogleSignInAuthorizationError.cancelled)
        )
        let store = AuthenticationStore(
            api: api,
            appleSignIn: MockAppleAuthorizer(result: .failure(AppleSignInError.cancelled)),
            googleSignIn: google
        )

        await store.restore()
        await store.signInWithGoogle()

        XCTAssertEqual(store.phase, .signedOut)
        XCTAssertNil(store.errorMessage)
        let request = await api.receivedGoogleRequest()
        XCTAssertNil(request)
    }

    func testProviderSessionIsClearedAfterAccountDeletion() async {
        let api = MockAuthenticationAPI(session: makeSession())
        let google = MockGoogleAuthorizer(
            configured: true,
            result: .failure(GoogleSignInAuthorizationError.cancelled)
        )
        let store = AuthenticationStore(
            api: api,
            appleSignIn: MockAppleAuthorizer(result: .failure(AppleSignInError.cancelled)),
            googleSignIn: google
        )
        await store.restore()

        await store.deleteAccount()

        XCTAssertEqual(google.signOutCount, 1)
    }

    func testAuthenticationFailureIsReadableAndDoesNotInventAccount() async {
        let api = MockAuthenticationAPI(session: nil, signInFailure: true)
        let store = AuthenticationStore(
            api: api,
            appleSignIn: MockAppleAuthorizer(
                result: .success(
                    AppleAuthorizationPayload(
                        identityToken: "identity-token",
                        rawNonce: "raw-nonce-1234567890",
                        displayName: nil
                    )
                )
            )
        )

        await store.restore()
        await store.signInWithApple()

        XCTAssertEqual(store.phase, .signedOut)
        XCTAssertEqual(store.errorMessage, "Apple sign-in was rejected.")
    }

    func testSignOutClearsPublishedAccountAndEntitlement() async {
        let api = MockAuthenticationAPI(
            session: makeSession(),
            entitlement: makeEntitlement(plan: .lifetime)
        )
        let store = AuthenticationStore(
            api: api,
            appleSignIn: MockAppleAuthorizer(result: .failure(AppleSignInError.cancelled))
        )
        await store.restore()

        await store.signOut()

        XCTAssertEqual(store.phase, .signedOut)
        XCTAssertNil(store.entitlement)
        let signOutCount = await api.signOutCount()
        XCTAssertEqual(signOutCount, 1)
    }

    func testFailedDeletionKeepsAccountAvailable() async {
        let session = makeSession()
        let api = MockAuthenticationAPI(session: session, deleteFailure: true)
        let store = AuthenticationStore(
            api: api,
            appleSignIn: MockAppleAuthorizer(result: .failure(AppleSignInError.cancelled))
        )
        await store.restore()

        await store.deleteAccount()

        XCTAssertEqual(store.phase, .signedIn(session.account))
        XCTAssertEqual(store.errorMessage, "Account deletion paused safely.")
    }

    func testSuccessfulDeletionClearsAccount() async {
        let api = MockAuthenticationAPI(session: makeSession())
        let store = AuthenticationStore(
            api: api,
            appleSignIn: MockAppleAuthorizer(result: .failure(AppleSignInError.cancelled))
        )
        await store.restore()

        await store.deleteAccount()

        XCTAssertEqual(store.phase, .signedOut)
        XCTAssertNil(store.entitlement)
    }

    func testAppleSecurityUsesDocumentedSHA256NonceContract() throws {
        XCTAssertEqual(
            AppleSignInSecurity.sha256("raw-nonce"),
            "2c5d107938053a2275f022c153c9a71f65ee07754b8bca543ee97a0c3cc66990"
        )

        let first = try AppleSignInSecurity.randomURLSafeValue()
        let second = try AppleSignInSecurity.randomURLSafeValue()
        XCTAssertGreaterThanOrEqual(first.count, 40)
        XCTAssertNotEqual(first, second)
        XCTAssertNil(first.range(of: #"[^A-Za-z0-9_-]"#, options: .regularExpression))
    }

    func testMemorySessionStoreKeepsStableDeviceAndClearsOnlySession() async throws {
        let session = makeSession()
        let storage = MemorySessionStore(session: session, deviceID: "stable-device-123")

        let firstDeviceID = try await storage.deviceID()
        let loadedSession = try await storage.loadSession()
        XCTAssertEqual(firstDeviceID, "stable-device-123")
        XCTAssertEqual(loadedSession, session)
        try await storage.clearSession()
        let clearedSession = try await storage.loadSession()
        let secondDeviceID = try await storage.deviceID()
        XCTAssertNil(clearedSession)
        XCTAssertEqual(secondDeviceID, "stable-device-123")
    }

    private func makeSession() -> AuthSession {
        AuthSession(
            accessToken: "access",
            refreshToken: "refresh",
            expiresIn: 1_200,
            account: AuthAccount(
                subject: "apple:subject",
                email: "relay@privaterelay.appleid.com",
                displayName: "Avery",
                pictureURL: nil,
                userID: "00000000-0000-0000-0000-000000000001",
                identityProvider: "apple"
            ),
            obtainedAt: Date(timeIntervalSince1970: 1_000)
        )
    }

    private func makeEntitlement(plan: EntitlementPlan) -> EntitlementSnapshot {
        EntitlementSnapshot(
            plan: plan,
            source: plan == .lifetime ? .googlePlayLegacy : .appleSubscription,
            billingPeriod: plan == .lifetime ? .lifetime : .monthly,
            status: .active,
            productID: plan == .lifetime ? nil : "com.hikejournal.app.plus.monthly",
            expiresAt: plan == .lifetime ? nil : Date(timeIntervalSince1970: 2_000),
            graceExpiresAt: nil,
            limits: EntitlementLimits(cloudHikes: nil, cloudMedia: 10_000),
            usage: EntitlementUsage(cloudHikes: 4, cloudMedia: 12),
            features: ["offline_maps": true],
            policy: EntitlementPolicySummary(
                version: "2026-08-21",
                androidPaidCompatibility: "observe_only"
            )
        )
    }
}

private enum MockAuthenticationError: Error, LocalizedError {
    case signIn
    case deletion

    var errorDescription: String? {
        switch self {
        case .signIn: "Apple sign-in was rejected."
        case .deletion: "Account deletion paused safely."
        }
    }
}

@MainActor
private final class MockAppleAuthorizer: AppleSignInAuthorizing {
    let result: Result<AppleAuthorizationPayload, Error>

    init(result: Result<AppleAuthorizationPayload, Error>) {
        self.result = result
    }

    func authorize() async throws -> AppleAuthorizationPayload {
        try result.get()
    }
}

@MainActor
private final class MockGoogleAuthorizer: GoogleSignInAuthorizing {
    let isConfigured: Bool
    let result: Result<GoogleAuthorizationPayload, Error>
    private(set) var signOutCount = 0

    init(configured: Bool, result: Result<GoogleAuthorizationPayload, Error>) {
        isConfigured = configured
        self.result = result
    }

    func authorize() async throws -> GoogleAuthorizationPayload {
        try result.get()
    }

    func handle(_ url: URL) -> Bool { false }

    func signOut() {
        signOutCount += 1
    }
}

private actor MockAuthenticationAPI: AuthenticationAPI {
    private let storedSession: AuthSession?
    private let signInSession: AuthSession?
    private let entitlementValue: EntitlementSnapshot?
    private let entitlementFailure: Bool
    private let signInFailure: Bool
    private let deleteFailure: Bool
    private var authorization: AppleAuthorizationPayload?
    private var googleRequest: (credential: String, nonce: String?)?
    private var signOutCalls = 0

    init(
        session: AuthSession?,
        signInSession: AuthSession? = nil,
        entitlement: EntitlementSnapshot? = nil,
        entitlementFailure: Bool = false,
        signInFailure: Bool = false,
        deleteFailure: Bool = false
    ) {
        storedSession = session
        self.signInSession = signInSession
        entitlementValue = entitlement
        self.entitlementFailure = entitlementFailure
        self.signInFailure = signInFailure
        self.deleteFailure = deleteFailure
    }

    func persistedSession() -> AuthSession? {
        storedSession
    }

    func signInWithApple(_ authorization: AppleAuthorizationPayload) throws -> AuthSession {
        self.authorization = authorization
        if signInFailure { throw MockAuthenticationError.signIn }
        guard let signInSession else { throw MockAuthenticationError.signIn }
        return signInSession
    }

    func signInWithGoogle(credential: String, nonce: String?) throws -> AuthSession {
        googleRequest = (credential, nonce)
        if signInFailure { throw MockAuthenticationError.signIn }
        guard let signInSession else { throw MockAuthenticationError.signIn }
        return signInSession
    }

    func entitlement() throws -> EntitlementSnapshot {
        if entitlementFailure { throw APIClientError.transport("Offline") }
        guard let entitlementValue else { throw APIClientError.server(statusCode: 404, message: "Not ready.", requestID: nil) }
        return entitlementValue
    }

    func signOut() {
        signOutCalls += 1
    }

    func deleteAccount() throws {
        if deleteFailure { throw MockAuthenticationError.deletion }
    }

    func receivedAuthorization() -> AppleAuthorizationPayload? {
        authorization
    }

    func signOutCount() -> Int {
        signOutCalls
    }

    func receivedGoogleRequest() -> (credential: String, nonce: String?)? {
        googleRequest
    }
}
