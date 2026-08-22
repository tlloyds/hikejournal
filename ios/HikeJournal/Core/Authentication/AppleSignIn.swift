import AuthenticationServices
import CryptoKit
import Foundation
import Security
import SwiftUI
import UIKit

struct AppleAuthorizationPayload: Equatable, Sendable {
    let identityToken: String
    let rawNonce: String
    let displayName: String?
}

@MainActor
protocol AppleSignInAuthorizing: AnyObject {
    func authorize() async throws -> AppleAuthorizationPayload
}

enum AppleSignInError: Error, Equatable, LocalizedError {
    case cancelled
    case alreadyInProgress
    case presentationUnavailable
    case invalidCredential
    case stateMismatch
    case missingIdentityToken
    case randomGenerationFailed(OSStatus)

    var errorDescription: String? {
        switch self {
        case .cancelled:
            return nil
        case .alreadyInProgress:
            return "Apple sign-in is already in progress."
        case .presentationUnavailable:
            return "Apple sign-in is not available from this screen."
        case .invalidCredential:
            return "Apple did not return a valid sign-in credential."
        case .stateMismatch:
            return "Apple sign-in could not be matched to this request. Please try again."
        case .missingIdentityToken:
            return "Apple did not return the identity token HikeJournal needs."
        case let .randomGenerationFailed(status):
            return "HikeJournal could not securely begin Apple sign-in (\(status))."
        }
    }
}

enum AppleSignInSecurity {
    static func randomURLSafeValue(byteCount: Int = 32) throws -> String {
        precondition(byteCount > 0)
        var bytes = [UInt8](repeating: 0, count: byteCount)
        let status = bytes.withUnsafeMutableBytes { buffer in
            guard let address = buffer.baseAddress else { return errSecParam }
            return SecRandomCopyBytes(kSecRandomDefault, buffer.count, address)
        }
        guard status == errSecSuccess else {
            throw AppleSignInError.randomGenerationFailed(status)
        }
        return Data(bytes)
            .base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    static func sha256(_ value: String) -> String {
        SHA256.hash(data: Data(value.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
    }
}

@MainActor
final class AppleSignInCoordinator: NSObject, AppleSignInAuthorizing {
    typealias PresentationAnchorProvider = @MainActor () -> ASPresentationAnchor?

    private struct PendingAuthorization {
        let rawNonce: String
        let state: String
        let anchor: ASPresentationAnchor
        let continuation: CheckedContinuation<AppleAuthorizationPayload, Error>
    }

    private let presentationAnchorProvider: PresentationAnchorProvider
    private var pending: PendingAuthorization?
    private var authorizationController: ASAuthorizationController?

    init(
        presentationAnchorProvider: @escaping PresentationAnchorProvider = AppleSignInCoordinator.activePresentationAnchor
    ) {
        self.presentationAnchorProvider = presentationAnchorProvider
    }

    func authorize() async throws -> AppleAuthorizationPayload {
        guard pending == nil else {
            throw AppleSignInError.alreadyInProgress
        }
        guard let anchor = presentationAnchorProvider() else {
            throw AppleSignInError.presentationUnavailable
        }

        let rawNonce = try AppleSignInSecurity.randomURLSafeValue()
        let state = try AppleSignInSecurity.randomURLSafeValue(byteCount: 16)
        let provider = ASAuthorizationAppleIDProvider()
        let request = provider.createRequest()
        request.requestedScopes = [.fullName, .email]
        request.nonce = AppleSignInSecurity.sha256(rawNonce)
        request.state = state

        return try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                pending = PendingAuthorization(
                    rawNonce: rawNonce,
                    state: state,
                    anchor: anchor,
                    continuation: continuation
                )
                let controller = ASAuthorizationController(authorizationRequests: [request])
                authorizationController = controller
                controller.delegate = self
                controller.presentationContextProvider = self
                controller.performRequests()
            }
        } onCancel: {
            Task { @MainActor [weak self] in
                self?.cancelPendingAuthorization()
            }
        }
    }

    private func finish(_ result: Result<AppleAuthorizationPayload, Error>) {
        guard let pending else { return }
        self.pending = nil
        authorizationController = nil
        pending.continuation.resume(with: result)
    }

    private func cancelPendingAuthorization() {
        authorizationController?.cancel()
        finish(.failure(CancellationError()))
    }

    private static func activePresentationAnchor() -> ASPresentationAnchor? {
        let scenes = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .filter { $0.activationState == .foregroundActive }
        return scenes
            .flatMap(\.windows)
            .first(where: \.isKeyWindow)
            ?? scenes.flatMap(\.windows).first
    }
}

extension AppleSignInCoordinator: ASAuthorizationControllerDelegate {
    func authorizationController(
        controller: ASAuthorizationController,
        didCompleteWithAuthorization authorization: ASAuthorization
    ) {
        guard let pending else { return }
        guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential else {
            finish(.failure(AppleSignInError.invalidCredential))
            return
        }
        guard credential.state == pending.state else {
            finish(.failure(AppleSignInError.stateMismatch))
            return
        }
        guard let tokenData = credential.identityToken,
              let identityToken = String(data: tokenData, encoding: .utf8),
              !identityToken.isEmpty else {
            finish(.failure(AppleSignInError.missingIdentityToken))
            return
        }

        let formatter = PersonNameComponentsFormatter()
        let suppliedName = credential.fullName.map { formatter.string(from: $0) }?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        finish(
            .success(
                AppleAuthorizationPayload(
                    identityToken: identityToken,
                    rawNonce: pending.rawNonce,
                    displayName: suppliedName?.isEmpty == false ? suppliedName : nil
                )
            )
        )
    }

    func authorizationController(
        controller: ASAuthorizationController,
        didCompleteWithError error: Error
    ) {
        if let authorizationError = error as? ASAuthorizationError,
           authorizationError.code == .canceled {
            finish(.failure(AppleSignInError.cancelled))
        } else {
            finish(.failure(error))
        }
    }
}

extension AppleSignInCoordinator: ASAuthorizationControllerPresentationContextProviding {
    func presentationAnchor(for controller: ASAuthorizationController) -> ASPresentationAnchor {
        pending?.anchor ?? presentationAnchorProvider() ?? ASPresentationAnchor()
    }
}

struct NativeAppleSignInButton: UIViewRepresentable {
    let colorScheme: ColorScheme
    let action: @MainActor () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(action: action)
    }

    func makeUIView(context: Context) -> ASAuthorizationAppleIDButton {
        let style: ASAuthorizationAppleIDButton.Style = colorScheme == .dark ? .white : .black
        let button = ASAuthorizationAppleIDButton(type: .continue, style: style)
        button.cornerRadius = 8
        button.addTarget(
            context.coordinator,
            action: #selector(Coordinator.activate),
            for: .touchUpInside
        )
        return button
    }

    func updateUIView(_ uiView: ASAuthorizationAppleIDButton, context: Context) {
        context.coordinator.action = action
    }

    @MainActor
    final class Coordinator: NSObject {
        var action: @MainActor () -> Void

        init(action: @escaping @MainActor () -> Void) {
            self.action = action
        }

        @objc func activate() {
            action()
        }
    }
}

@MainActor
final class UnavailableAppleSignInAuthorizer: AppleSignInAuthorizing {
    func authorize() async throws -> AppleAuthorizationPayload {
        throw AppleSignInError.presentationUnavailable
    }
}
