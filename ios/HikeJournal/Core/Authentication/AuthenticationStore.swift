import Combine
import Foundation

enum AuthenticationPhase: Equatable {
    case restoring
    case signedOut
    case signedIn(AuthAccount)
}

@MainActor
final class AuthenticationStore: ObservableObject {
    @Published private(set) var phase: AuthenticationPhase = .restoring
    @Published private(set) var entitlement: EntitlementSnapshot?
    @Published private(set) var isPerformingAction = false
    @Published private(set) var errorMessage: String?

    private let api: any AuthenticationAPI
    private let appleSignIn: any AppleSignInAuthorizing
    private let googleSignIn: any GoogleSignInAuthorizing
    private var hasRestored = false

    init(
        api: any AuthenticationAPI,
        appleSignIn: any AppleSignInAuthorizing,
        googleSignIn: (any GoogleSignInAuthorizing)? = nil
    ) {
        self.api = api
        self.appleSignIn = appleSignIn
        self.googleSignIn = googleSignIn ?? UnavailableGoogleSignInAuthorizer()
    }

    var isGoogleSignInConfigured: Bool {
        googleSignIn.isConfigured
    }

    func signInWithGoogle() async {
        guard !isPerformingAction else { return }
        isPerformingAction = true
        errorMessage = nil
        defer { isPerformingAction = false }

        do {
            let authorization = try await googleSignIn.authorize()
            let session = try await api.signInWithGoogle(
                credential: authorization.identityToken,
                nonce: nil
            )
            phase = .signedIn(session.account)
            await loadEntitlement(showErrors: false)
        } catch GoogleSignInAuthorizationError.cancelled {
            if case .restoring = phase {
                phase = .signedOut
            }
        } catch is CancellationError {
            return
        } catch {
            if case .restoring = phase {
                phase = .signedOut
            }
            errorMessage = readableMessage(error)
        }
    }

    func handleGoogleRedirect(_ url: URL) -> Bool {
        googleSignIn.handle(url)
    }

    func restore() async {
        guard !hasRestored else { return }
        hasRestored = true
        do {
            if let session = try await api.persistedSession() {
                phase = .signedIn(session.account)
                await loadEntitlement(showErrors: false)
            } else {
                phase = .signedOut
            }
        } catch {
            phase = .signedOut
            errorMessage = readableMessage(error)
        }
    }

    func signInWithApple() async {
        guard !isPerformingAction else { return }
        isPerformingAction = true
        errorMessage = nil
        defer { isPerformingAction = false }

        do {
            let authorization = try await appleSignIn.authorize()
            let session = try await api.signInWithApple(authorization)
            phase = .signedIn(session.account)
            await loadEntitlement(showErrors: false)
        } catch AppleSignInError.cancelled {
            if case .restoring = phase {
                phase = .signedOut
            }
        } catch is CancellationError {
            return
        } catch {
            if case .restoring = phase {
                phase = .signedOut
            }
            errorMessage = readableMessage(error)
        }
    }

    func loadEntitlement(showErrors: Bool = true) async {
        guard case .signedIn = phase else {
            entitlement = nil
            return
        }
        do {
            entitlement = try await api.entitlement()
        } catch is CancellationError {
            return
        } catch let error as APIClientError {
            if case .authenticationExpired = error {
                phase = .signedOut
                entitlement = nil
            }
            if showErrors {
                errorMessage = readableMessage(error)
            }
        } catch {
            if showErrors {
                errorMessage = readableMessage(error)
            }
        }
    }

    func signOut() async {
        guard !isPerformingAction else { return }
        isPerformingAction = true
        await api.signOut()
        googleSignIn.signOut()
        phase = .signedOut
        entitlement = nil
        errorMessage = nil
        isPerformingAction = false
    }

    func deleteAccount() async {
        guard !isPerformingAction else { return }
        isPerformingAction = true
        errorMessage = nil
        defer { isPerformingAction = false }
        do {
            try await api.deleteAccount()
            googleSignIn.signOut()
            phase = .signedOut
            entitlement = nil
        } catch is CancellationError {
            return
        } catch {
            errorMessage = readableMessage(error)
        }
    }

    func clearError() {
        errorMessage = nil
    }

    private func readableMessage(_ error: Error) -> String {
        if let localized = error as? LocalizedError,
           let description = localized.errorDescription,
           !description.isEmpty {
            return description
        }
        return "HikeJournal couldn't complete that request. Please try again."
    }
}

actor UnavailableAuthenticationAPI: AuthenticationAPI {
    func persistedSession() -> AuthSession? {
        nil
    }

    func signInWithApple(_ authorization: AppleAuthorizationPayload) throws -> AuthSession {
        throw APIClientError.missingBaseURL
    }

    func entitlement() throws -> EntitlementSnapshot {
        throw APIClientError.missingBaseURL
    }

    func signOut() {}

    func deleteAccount() throws {
        throw APIClientError.missingBaseURL
    }
}
