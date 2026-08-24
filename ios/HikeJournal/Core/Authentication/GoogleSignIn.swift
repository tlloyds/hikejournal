import AuthenticationServices
import CryptoKit
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
    case providerFailure(code: Int, message: String)

    var errorDescription: String? {
        switch self {
        case .unconfigured:
            return "Google Sign-In needs its public iOS and server client IDs configured."
        case .noPresentingViewController:
            return "HikeJournal couldn't open Google Sign-In right now."
        case .cancelled:
            return nil
        case .missingIdentityToken:
            return "Google did not return the identity proof HikeJournal needs."
        case let .providerFailure(code, message):
            let detail = message.trimmingCharacters(in: .whitespacesAndNewlines)
            if detail.isEmpty {
                return "Google Sign-In couldn't complete (error \(code)). Please try again."
            }
            return "Google Sign-In couldn't complete (error \(code)): \(detail)"
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
final class GoogleSignInCoordinator: NSObject, GoogleSignInAuthorizing, ASWebAuthenticationPresentationContextProviding {
    private let clientID: String?
    private let serverClientID: String?
    private var didConfigureProvider = false
    private var simulatorWebSession: ASWebAuthenticationSession?

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
#if targetEnvironment(simulator)
        return try await authorizeInSimulator(clientID: clientID, serverClientID: serverClientID)
#else
        guard let presenter = UIApplication.shared.hikeJournalPresentingViewController else {
            throw GoogleSignInAuthorizationError.noPresentingViewController
        }

        let provider = GIDSignIn.sharedInstance
        provider.configuration = GIDConfiguration(
            clientID: clientID,
            serverClientID: serverClientID
        )
        if !didConfigureProvider {
            didConfigureProvider = true
            await prewarmAppCheck(provider)
        }

        return try await withCheckedThrowingContinuation { continuation in
            provider.signIn(withPresenting: presenter) { result, error in
                if let error {
                    let providerError = error as NSError
                    if providerError.domain == kGIDSignInErrorDomain,
                       providerError.code == GIDSignInError.canceled.rawValue {
                        continuation.resume(throwing: GoogleSignInAuthorizationError.cancelled)
                    } else {
                        let message = [
                            providerError.localizedDescription,
                            (providerError.userInfo[NSUnderlyingErrorKey] as? NSError)?.localizedDescription
                        ]
                        .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
                        .reduce(into: [String]()) { details, value in
                            if !details.contains(value) { details.append(value) }
                        }
                        .joined(separator: " ")
                        continuation.resume(
                            throwing: GoogleSignInAuthorizationError.providerFailure(
                                code: providerError.code,
                                message: message
                            )
                        )
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
#endif
    }

    func handle(_ url: URL) -> Bool {
#if targetEnvironment(simulator)
        false
#else
        GIDSignIn.sharedInstance.handle(url)
#endif
    }

    func signOut() {
#if targetEnvironment(simulator)
        simulatorWebSession?.cancel()
        simulatorWebSession = nil
#else
        GIDSignIn.sharedInstance.signOut()
#endif
    }

#if targetEnvironment(simulator)
    private func authorizeInSimulator(
        clientID: String,
        serverClientID: String
    ) async throws -> GoogleAuthorizationPayload {
        guard UIApplication.shared.hikeJournalPresentationAnchor != nil else {
            throw GoogleSignInAuthorizationError.noPresentingViewController
        }

        let state = try AppleSignInSecurity.randomURLSafeValue(byteCount: 24)
        let nonce = try AppleSignInSecurity.randomURLSafeValue(byteCount: 24)
        let verifier = try AppleSignInSecurity.randomURLSafeValue(byteCount: 48)
        let callbackScheme = try Self.reversedClientIDScheme(for: clientID)
        let redirectURI = "\(callbackScheme):/oauth2callback"
        let challenge = Self.codeChallenge(for: verifier)

        var components = URLComponents(string: "https://accounts.google.com/o/oauth2/v2/auth")
        components?.queryItems = [
            URLQueryItem(name: "client_id", value: clientID),
            URLQueryItem(name: "redirect_uri", value: redirectURI),
            URLQueryItem(name: "response_type", value: "code"),
            URLQueryItem(name: "scope", value: "openid email profile"),
            URLQueryItem(name: "state", value: state),
            URLQueryItem(name: "nonce", value: nonce),
            URLQueryItem(name: "code_challenge", value: challenge),
            URLQueryItem(name: "code_challenge_method", value: "S256"),
            // This is the same server-audience parameter used by the official
            // GoogleSignIn SDK when GIDConfiguration has serverClientID set.
            URLQueryItem(name: "audience", value: serverClientID),
            URLQueryItem(name: "prompt", value: "select_account")
        ]
        guard let authorizationURL = components?.url else {
            throw GoogleSignInAuthorizationError.providerFailure(
                code: -1,
                message: "Google Sign-In could not create its authorization request."
            )
        }

        return try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                let session = ASWebAuthenticationSession(
                    url: authorizationURL,
                    callbackURLScheme: callbackScheme
                ) { [weak self] callbackURL, error in
                    Task { @MainActor [weak self] in
                        guard let self else { return }
                        self.simulatorWebSession = nil

                        if let webError = error as? ASWebAuthenticationSessionError,
                           webError.code == .canceledLogin {
                            continuation.resume(throwing: GoogleSignInAuthorizationError.cancelled)
                            return
                        }
                        if let error {
                            continuation.resume(
                                throwing: GoogleSignInAuthorizationError.providerFailure(
                                    code: (error as NSError).code,
                                    message: error.localizedDescription
                                )
                            )
                            return
                        }
                        guard let callbackURL,
                              let callbackQuery = URLComponents(
                                  url: callbackURL,
                                  resolvingAgainstBaseURL: false
                              )?.queryItems else {
                            continuation.resume(
                                throwing: GoogleSignInAuthorizationError.providerFailure(
                                    code: -1,
                                    message: "Google Sign-In returned an invalid callback."
                                )
                            )
                            return
                        }

                        let values = callbackQuery.reduce(into: [String: String]()) { result, item in
                            result[item.name] = item.value
                        }
                        guard values["state"] == state else {
                            continuation.resume(
                                throwing: GoogleSignInAuthorizationError.providerFailure(
                                    code: -1,
                                    message: "Google Sign-In could not verify its callback."
                                )
                            )
                            return
                        }
                        if let callbackError = values["error"] {
                            if callbackError == "access_denied" {
                                continuation.resume(throwing: GoogleSignInAuthorizationError.cancelled)
                            } else {
                                continuation.resume(
                                    throwing: GoogleSignInAuthorizationError.providerFailure(
                                        code: -1,
                                        message: values["error_description"] ?? callbackError
                                    )
                                )
                            }
                            return
                        }
                        guard let code = values["code"], !code.isEmpty else {
                            continuation.resume(
                                throwing: GoogleSignInAuthorizationError.providerFailure(
                                    code: -1,
                                    message: "Google Sign-In did not return an authorization code."
                                )
                            )
                            return
                        }

                        do {
                            let token = try await self.exchangeSimulatorCode(
                                code: code,
                                clientID: clientID,
                                redirectURI: redirectURI,
                                verifier: verifier
                            )
                            continuation.resume(
                                returning: GoogleAuthorizationPayload(identityToken: token)
                            )
                        } catch {
                            continuation.resume(throwing: error)
                        }
                    }
                }
                session.presentationContextProvider = self
                session.prefersEphemeralWebBrowserSession = false
                self.simulatorWebSession = session
                if !session.start() {
                    self.simulatorWebSession = nil
                    continuation.resume(
                        throwing: GoogleSignInAuthorizationError.noPresentingViewController
                    )
                }
            }
        } onCancel: { [weak self] in
            Task { @MainActor [weak self] in
                self?.simulatorWebSession?.cancel()
            }
        }
    }

    private func exchangeSimulatorCode(
        code: String,
        clientID: String,
        redirectURI: String,
        verifier: String
    ) async throws -> String {
        guard let tokenURL = URL(string: "https://oauth2.googleapis.com/token") else {
            throw GoogleSignInAuthorizationError.providerFailure(
                code: -1,
                message: "Google Sign-In token exchange is unavailable."
            )
        }
        var request = URLRequest(url: tokenURL)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        var body = URLComponents()
        body.queryItems = [
            URLQueryItem(name: "code", value: code),
            URLQueryItem(name: "client_id", value: clientID),
            URLQueryItem(name: "redirect_uri", value: redirectURI),
            URLQueryItem(name: "grant_type", value: "authorization_code"),
            URLQueryItem(name: "code_verifier", value: verifier)
        ]
        request.httpBody = body.percentEncodedQuery?.data(using: .utf8)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              (200..<300).contains(httpResponse.statusCode) else {
            let detail = String(data: data, encoding: .utf8) ?? "Google token exchange failed."
            throw GoogleSignInAuthorizationError.providerFailure(code: -1, message: detail)
        }
        do {
            let payload = try JSONDecoder().decode(GoogleTokenResponse.self, from: data)
            guard let token = payload.idToken?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !token.isEmpty else {
                throw GoogleSignInAuthorizationError.missingIdentityToken
            }
            return token
        } catch let error as GoogleSignInAuthorizationError {
            throw error
        } catch {
            throw GoogleSignInAuthorizationError.providerFailure(
                code: -1,
                message: "Google token exchange returned an invalid response."
            )
        }
    }

    private static func reversedClientIDScheme(for clientID: String) throws -> String {
        let parts = clientID.split(separator: ".")
        guard parts.count >= 3 else {
            throw GoogleSignInAuthorizationError.unconfigured
        }
        return parts.reversed().joined(separator: ".").lowercased()
    }

    private static func codeChallenge(for verifier: String) -> String {
        Data(SHA256.hash(data: Data(verifier.utf8)))
            .base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        UIApplication.shared.hikeJournalPresentationAnchor ?? ASPresentationAnchor()
    }

    private struct GoogleTokenResponse: Decodable {
        let idToken: String?

        enum CodingKeys: String, CodingKey {
            case idToken = "id_token"
        }
    }
#else
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        UIApplication.shared.hikeJournalPresentationAnchor ?? ASPresentationAnchor()
    }
#endif

    private func prewarmAppCheck(_ provider: GIDSignIn) async {
        await withCheckedContinuation { continuation in
            provider.configure { _ in
                // App Check preparation is an optimization, not an authentication
                // prerequisite. App Attest is unavailable in Simulator and can also
                // fail transiently on a device; GoogleSignIn still performs the
                // interactive authorization flow and handles token fallback itself.
                continuation.resume()
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

    var hikeJournalPresentationAnchor: ASPresentationAnchor? {
        connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .filter { $0.activationState == .foregroundActive }
            .flatMap(\.windows)
            .first(where: \.isKeyWindow)
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
