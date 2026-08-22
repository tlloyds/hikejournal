import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public enum EntitlementServerClientError: Error, Equatable, LocalizedError, Sendable {
    case insecureBaseURL
    case invalidBaseURL
    case invalidAccessToken
    case invalidResponse
    case responseTooLarge
    case httpStatus(Int)
    case decodingFailed

    public var errorDescription: String? {
        switch self {
        case .insecureBaseURL:
            "The entitlement server must use HTTPS."
        case .invalidBaseURL:
            "The entitlement server URL is invalid."
        case .invalidAccessToken:
            "A signed-in HikeJournal session is required."
        case .invalidResponse:
            "The entitlement server returned an invalid response."
        case .responseTooLarge:
            "The entitlement server response was unexpectedly large."
        case let .httpStatus(status):
            "The entitlement server returned HTTP \(status)."
        case .decodingFailed:
            "The entitlement server response could not be decoded."
        }
    }
}

public final class URLSessionEntitlementServerClient: HikeJournalEntitlementServer,
    @unchecked Sendable
{
    public typealias AccessTokenProvider = @Sendable () async throws -> String

    public static let maximumResponseBytes = 1_000_000

    private let baseURL: URL
    private let session: URLSession
    private let accessToken: AccessTokenProvider

    public init(
        baseURL: URL,
        session: URLSession = .shared,
        accessToken: @escaping AccessTokenProvider
    ) throws {
        guard baseURL.scheme?.lowercased() == "https" else {
            throw EntitlementServerClientError.insecureBaseURL
        }
        guard baseURL.host != nil,
              baseURL.user == nil,
              baseURL.password == nil,
              baseURL.query == nil,
              baseURL.fragment == nil
        else {
            throw EntitlementServerClientError.invalidBaseURL
        }
        self.baseURL = baseURL
        self.session = session
        self.accessToken = accessToken
    }

    public func sync(
        _ payload: StoreKitTransactionSyncRequest
    ) async throws -> AuthoritativeEntitlementSnapshot {
        let token = try await authorizationToken()
        var request = try makeRequest(
            path: StoreKitServerEndpoint.transactionSyncPath,
            method: "POST",
            token: token
        )
        request.httpBody = try JSONEncoder().encode(payload)
        return try await execute(request)
    }

    public func fetchEntitlement() async throws -> AuthoritativeEntitlementSnapshot {
        let token = try await authorizationToken()
        let request = try makeRequest(
            path: StoreKitServerEndpoint.entitlementPath,
            method: "GET",
            token: token
        )
        return try await execute(request)
    }

    public func makeTransactionSyncURLRequest(
        _ payload: StoreKitTransactionSyncRequest,
        accessToken: String
    ) throws -> URLRequest {
        let token = try Self.normalizedAccessToken(accessToken)
        var request = try makeRequest(
            path: StoreKitServerEndpoint.transactionSyncPath,
            method: "POST",
            token: token
        )
        request.httpBody = try JSONEncoder().encode(payload)
        return request
    }

    private func authorizationToken() async throws -> String {
        do {
            return try Self.normalizedAccessToken(try await accessToken())
        } catch let error as EntitlementServerClientError {
            throw error
        } catch {
            throw EntitlementServerClientError.invalidAccessToken
        }
    }

    private static func normalizedAccessToken(_ value: String) throws -> String {
        let token = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !token.isEmpty,
              token.count <= 8_192,
              !token.contains(where: { $0.isWhitespace || $0.isNewline })
        else {
            throw EntitlementServerClientError.invalidAccessToken
        }
        return token
    }

    private func makeRequest(
        path: String,
        method: String,
        token: String
    ) throws -> URLRequest {
        guard var components = URLComponents(
            url: baseURL,
            resolvingAgainstBaseURL: false
        ) else {
            throw EntitlementServerClientError.invalidResponse
        }
        let basePath = components.path.hasSuffix("/")
            ? String(components.path.dropLast())
            : components.path
        components.path = basePath + path
        guard let url = components.url else {
            throw EntitlementServerClientError.invalidResponse
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if method == "POST" {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        request.timeoutInterval = 30
        return request
    }

    private func execute(
        _ request: URLRequest
    ) async throws -> AuthoritativeEntitlementSnapshot {
        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else {
            throw EntitlementServerClientError.invalidResponse
        }
        guard (200 ... 299).contains(response.statusCode) else {
            throw EntitlementServerClientError.httpStatus(response.statusCode)
        }
        guard data.count <= Self.maximumResponseBytes else {
            throw EntitlementServerClientError.responseTooLarge
        }
        do {
            return try Self.decoder().decode(
                AuthoritativeEntitlementSnapshot.self,
                from: data
            )
        } catch {
            throw EntitlementServerClientError.decodingFailed
        }
    }

    private static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let value = try container.decode(String.self)
            let fractionalFormatter = ISO8601DateFormatter()
            fractionalFormatter.formatOptions = [
                .withInternetDateTime,
                .withFractionalSeconds,
            ]
            let standardFormatter = ISO8601DateFormatter()
            standardFormatter.formatOptions = [.withInternetDateTime]
            if let date = fractionalFormatter.date(from: value)
                ?? standardFormatter.date(from: value)
            {
                return date
            }
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Expected an ISO 8601 date."
            )
        }
        return decoder
    }
}
