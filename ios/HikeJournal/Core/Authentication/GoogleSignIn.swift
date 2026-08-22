import Foundation
@preconcurrency import GoogleSignIn
import UIKit

struct GoogleAuthorizationPayload: Equatable, Sendable {
    let identityToken: String
}

enum GoogleSignInAuthorizationError: Error, Equatable, LocalizedError {
    case unconfigured
    case noPresentingViewController
    case cancelled
    case missingIdentityToken
    case providerFailure

    var errorDescription: String? {
        switch self {
        case .unconfigured:
            "Google Sign-In needs its public iOS and server client IDs configured."
        case .noPresentingViewController:
            "HikeJournal couldn't open Google Sign-In right now."
        case .cancelled:
            nil
        case .missingIdentityToken:
            "Google did not return the identity proof HikeJournal needs."
        case .providerFailure:
            "Google Sign-In couldn't complete. Please try again."
        }
    }
}

@MainActor
protocol GoogleSignInAuthorizing: AnyObject {
    var isConfigured: Bool { get }
    func authorize() async throws -> GoogleAuthorizationPayload
    func handle(_ url: URL) -> Bool
    func signOut()
}

@MainActor
final class GoogleSignInCoordinator: GoogleSignInAuthorizing {
    private let clientID: String?
    private let serverClientID: String?
    private var didConfigureProvider = false

    init(clientID: String?, serverClientID: String?) {
        self.clientID = clientID
        self.serverClientID = serverClientID
    }

    var isConfigured: Bool {
        clientID?.hasSuffix(".apps.googleusercontent.com") == true
            && serverClientID?.hasSuffix(".apps.googleusercontent.com") == true
    }

    func authorize() async throws -> GoogleAuthorizationPayload {
        guard isConfigured, let clientID, let serverClientID else {
            throw GoogleSignInAuthorizationError.unconfigured
        }
        guard let presenter = UIApplication.shared.hikeJournalPresentingViewController else {
            throw GoogleSignInAuthorizationError.noPresentingViewController
        }

        let provider = GIDSignIn.sharedInstance
        provider.configuration = GIDConfiguration(
            clientID: clientID,
            serverClientID: serverClientID
        )
        if !didConfigureProvider {
            try await configure(provider)
            didConfigureProvider = true
        }

        return try await withCheckedThrowingContinuation { continuation in
            provider.signIn(withPresenting: presenter) { result, error in
                if let error {
                    let providerError = error as NSError
                    if providerError.domain == kGIDSignInErrorDomain,
                       providerError.code == GIDSignInError.canceled.rawValue {
                        continuation.resume(throwing: GoogleSignInAuthorizationError.cancelled)
                    } else {
                        continuation.resume(throwing: GoogleSignInAuthorizationError.providerFailure)
                    }
                    return
                }
                guard let token = result?.user.idToken?.tokenString
                    .trimmingCharacters(in: .whitespacesAndNewlines),
                    !token.isEmpty else {
                    continuation.resume(throwing: GoogleSignInAuthorizationError.missingIdentityToken)
                    return
                }
                continuation.resume(returning: GoogleAuthorizationPayload(identityToken: token))
            }
        }
    }

    func handle(_ url: URL) -> Bool {
        GIDSignIn.sharedInstance.handle(url)
    }

    func signOut() {
        GIDSignIn.sharedInstance.signOut()
    }

    private func configure(_ provider: GIDSignIn) async throws {
        try await withCheckedThrowingContinuation { continuation in
            provider.configure { error in
                if error == nil {
                    continuation.resume(returning: ())
                } else {
                    continuation.resume(throwing: GoogleSignInAuthorizationError.providerFailure)
                }
            }
        }
    }
}

@MainActor
final class UnavailableGoogleSignInAuthorizer: GoogleSignInAuthorizing {
    let isConfigured = false

    func authorize() async throws -> GoogleAuthorizationPayload {
        throw GoogleSignInAuthorizationError.unconfigured
    }

    func handle(_ url: URL) -> Bool {
        false
    }

    func signOut() {}
}

private extension UIApplication {
    var hikeJournalPresentingViewController: UIViewController? {
        connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .filter { $0.activationState == .foregroundActive }
            .flatMap(\.windows)
            .first(where: \.isKeyWindow)?
            .rootViewController?
            .topmostPresentedController
    }
}

private extension UIViewController {
    var topmostPresentedController: UIViewController {
        if let presentedViewController {
            return presentedViewController.topmostPresentedController
        }
        if let navigation = self as? UINavigationController,
           let visible = navigation.visibleViewController {
            return visible.topmostPresentedController
        }
        if let tabs = self as? UITabBarController,
           let selected = tabs.selectedViewController {
            return selected.topmostPresentedController
        }
        return self
    }
}
