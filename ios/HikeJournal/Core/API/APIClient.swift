import Foundation

enum HTTPMethod: String, Sendable {
    case get = "GET"
    case post = "POST"
    case put = "PUT"
    case patch = "PATCH"
    case delete = "DELETE"
}

enum RequestAuthentication: Sendable {
    case none
    case optional
    case required
}

struct APIRequest<Response: Decodable>: Sendable {
    let method: HTTPMethod
    let path: String
    let queryItems: [URLQueryItem]
    let body: Data?
    let authentication: RequestAuthentication
    let headers: [String: String]
    let timeoutInterval: TimeInterval
    let maximumResponseBytes: Int

    init(
        method: HTTPMethod = .get,
        path: String,
        queryItems: [URLQueryItem] = [],
        body: Data? = nil,
        authentication: RequestAuthentication = .required,
        headers: [String: String] = [:],
        timeoutInterval: TimeInterval = 30,
        maximumResponseBytes: Int = 5 * 1_024 * 1_024
    ) {
        self.method = method
        self.path = path
        self.queryItems = queryItems
        self.body = body
        self.authentication = authentication
        self.headers = headers
        self.timeoutInterval = max(1, timeoutInterval)
        self.maximumResponseBytes = max(1, maximumResponseBytes)
    }
}

protocol HTTPTransport: Sendable {
    func data(for request: URLRequest) async throws -> (Data, URLResponse)
}

final class URLSessionTransport: HTTPTransport, @unchecked Sendable {
    private let session: URLSession

    init(session: URLSession? = nil) {
        if let session {
            self.session = session
        } else {
            let configuration = URLSessionConfiguration.default
            configuration.waitsForConnectivity = true
            configuration.timeoutIntervalForRequest = 30
            configuration.timeoutIntervalForResource = 90
            configuration.requestCachePolicy = .reloadRevalidatingCacheData
            self.session = URLSession(configuration: configuration)
        }
    }

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        try await session.data(for: request)
    }
}

enum APIClientError: Error, Equatable, LocalizedError {
    case missingBaseURL
    case invalidRequestPath
    case requestEncodingFailed
    case responseDecodingFailed
    case responseTooLarge(maximumBytes: Int)
    case nonHTTPResponse
    case sessionRequired
    case authenticationExpired(String)
    case server(statusCode: Int, message: String, requestID: String?)
    case transport(String)

    var errorDescription: String? {
        switch self {
        case .missingBaseURL:
            return "HikeJournal's server address is not configured."
        case .invalidRequestPath:
            return "HikeJournal could not create a safe server request."
        case .requestEncodingFailed:
            return "HikeJournal could not prepare this request."
        case .responseDecodingFailed:
            return "HikeJournal received a response it could not read."
        case let .responseTooLarge(maximumBytes):
            return "HikeJournal's server response exceeded the \(maximumBytes)-byte safety limit."
        case .nonHTTPResponse:
            return "HikeJournal received an invalid server response."
        case .sessionRequired:
            return "Sign in to continue."
        case let .authenticationExpired(message):
            return message
        case let .server(_, message, _):
            return message
        case let .transport(message):
            return message
        }
    }
}

extension Notification.Name {
    static let hikeJournalAuthenticationExpired = Notification.Name(
        "HikeJournalAuthenticationExpired"
    )
}

protocol AuthenticationAPI: Sendable {
    func persistedSession() async throws -> AuthSession?
    func signInWithApple(_ authorization: AppleAuthorizationPayload) async throws -> AuthSession
    func signInWithGoogle(credential: String, nonce: String?) async throws -> AuthSession
    func entitlement() async throws -> EntitlementSnapshot
    func signOut() async
    func deleteAccount() async throws
}

extension AuthenticationAPI {
    func signInWithGoogle(credential: String, nonce: String?) async throws -> AuthSession {
        throw APIClientError.missingBaseURL
    }
}

actor APIClient: AuthenticationAPI {
    private let baseURL: URL?
    private let apiKey: String?
    private let transport: any HTTPTransport
    private let sessionStore: any SessionStoring
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder
    private let now: @Sendable () -> Date
    private var refreshTask: Task<AuthSession, Error>?

    init(
        baseURL: URL?,
        apiKey: String? = nil,
        transport: any HTTPTransport = URLSessionTransport(),
        sessionStore: any SessionStoring = KeychainSessionStore(),
        now: @escaping @Sendable () -> Date = { Date() }
    ) {
        self.baseURL = baseURL
        self.apiKey = apiKey?.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty
        self.transport = transport
        self.sessionStore = sessionStore
        self.now = now
        encoder = JSONEncoder()
        decoder = JSONDecoder.hikeJournal
    }

    func persistedSession() async throws -> AuthSession? {
        try await sessionStore.loadSession()
    }

    func configuration() async throws -> MobileConfiguration {
        try await send(
            APIRequest(
                path: "/v1/config",
                authentication: .optional
            )
        )
    }

    func signInWithApple(_ authorization: AppleAuthorizationPayload) async throws -> AuthSession {
        let payload = AppleAuthenticationRequest(
            identityToken: authorization.identityToken,
            deviceID: try await sessionStore.deviceID(),
            nonce: authorization.rawNonce,
            displayName: authorization.displayName
        )
        return try await authenticate(payload, path: "/v1/auth/apple")
    }

    func signInWithGoogle(credential: String, nonce: String?) async throws -> AuthSession {
        let payload = GoogleAuthenticationRequest(
            credential: credential,
            deviceID: try await sessionStore.deviceID(),
            nonce: nonce
        )
        return try await authenticate(payload, path: "/v1/auth/google")
    }

    func refreshSession() async throws -> AuthSession {
        if let refreshTask {
            return try await refreshTask.value
        }

        let task = Task { try await self.performRefresh() }
        refreshTask = task
        do {
            let session = try await task.value
            refreshTask = nil
            return session
        } catch {
            refreshTask = nil
            if Self.isAuthenticationFailure(error) {
                await invalidateSession()
            }
            throw error
        }
    }

    func entitlement() async throws -> EntitlementSnapshot {
        try await send(APIRequest(path: "/v1/me/entitlement"))
    }

    func signOut() async {
        if var session = try? await sessionStore.loadSession() {
            if session.needsRefresh(at: now()),
               let refreshed = try? await refreshSession() {
                session = refreshed
            }
            let payload = LogoutRequest(refreshToken: session.refreshToken)
            let body = try? encoder.encode(payload)
            let request = APIRequest<SignedOutResponse>(
                method: .post,
                path: "/v1/auth/logout",
                body: body,
                authentication: .required
            )
            _ = try? await execute(
                request,
                session: session,
                mayRecoverAuthentication: false
            )
        }
        try? await sessionStore.clearSession()
    }

    func deleteAccount() async throws {
        let response: AccountDeletionResponse = try await send(
            APIRequest(method: .delete, path: "/v1/account")
        )
        guard response.deleted else {
            throw APIClientError.responseDecodingFailed
        }
        try? await sessionStore.clearSession()
    }

    func send<Response: Decodable>(_ request: APIRequest<Response>) async throws -> Response {
        try Task.checkCancellation()
        let session = try await sessionForRequest(request.authentication)
        return try await execute(request, session: session, mayRecoverAuthentication: true)
    }

    private func authenticate<Request: Encodable>(
        _ payload: Request,
        path: String
    ) async throws -> AuthSession {
        let body: Data
        do {
            body = try encoder.encode(payload)
        } catch {
            throw APIClientError.requestEncodingFailed
        }
        let response: MobileSessionPayload = try await send(
            APIRequest(
                method: .post,
                path: path,
                body: body,
                authentication: .none
            )
        )
        let session = AuthSession(payload: response, obtainedAt: now())
        try await sessionStore.saveSession(session)
        return session
    }

    private func performRefresh() async throws -> AuthSession {
        guard let existing = try await sessionStore.loadSession() else {
            throw APIClientError.sessionRequired
        }
        let payload = RefreshSessionRequest(
            refreshToken: existing.refreshToken,
            deviceID: try await sessionStore.deviceID()
        )
        let body: Data
        do {
            body = try encoder.encode(payload)
        } catch {
            throw APIClientError.requestEncodingFailed
        }
        let response: MobileSessionPayload = try await execute(
            APIRequest(
                method: .post,
                path: "/v1/auth/refresh",
                body: body,
                authentication: .none
            ),
            session: nil,
            mayRecoverAuthentication: false
        )
        let refreshed = AuthSession(payload: response, obtainedAt: now())
        try await sessionStore.saveSession(refreshed)
        return refreshed
    }

    private func sessionForRequest(_ authentication: RequestAuthentication) async throws -> AuthSession? {
        guard authentication != .none else { return nil }
        let session = try await sessionStore.loadSession()
        if authentication == .required, session == nil {
            throw APIClientError.sessionRequired
        }
        guard let session else { return nil }
        if session.needsRefresh(at: now()) {
            return try await refreshSession()
        }
        return session
    }

    private func execute<Response: Decodable>(
        _ request: APIRequest<Response>,
        session: AuthSession?,
        mayRecoverAuthentication: Bool
    ) async throws -> Response {
        let urlRequest = try makeURLRequest(request, accessToken: session?.accessToken)
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await transport.data(for: urlRequest)
        } catch is CancellationError {
            throw CancellationError()
        } catch let error as URLError where error.code == .cancelled {
            throw CancellationError()
        } catch let error as URLError {
            throw APIClientError.transport(error.localizedDescription)
        } catch {
            throw APIClientError.transport(error.localizedDescription)
        }
        try Task.checkCancellation()

        guard let http = response as? HTTPURLResponse else {
            throw APIClientError.nonHTTPResponse
        }
        guard data.count <= request.maximumResponseBytes else {
            throw APIClientError.responseTooLarge(maximumBytes: request.maximumResponseBytes)
        }
        if (200..<300).contains(http.statusCode) {
            do {
                return try decoder.decode(Response.self, from: data)
            } catch {
                throw APIClientError.responseDecodingFailed
            }
        }

        let message = serverMessage(from: data, statusCode: http.statusCode)
        if http.statusCode == 401, mayRecoverAuthentication, session != nil {
            let latest = try await sessionStore.loadSession()
            let recovered: AuthSession
            if let latest, latest.accessToken != session?.accessToken {
                recovered = latest
            } else {
                do {
                    recovered = try await refreshSession()
                } catch {
                    throw APIClientError.authenticationExpired(message)
                }
            }

            do {
                return try await execute(
                    request,
                    session: recovered,
                    mayRecoverAuthentication: false
                )
            } catch let error as APIClientError {
                if case let .server(statusCode, retryMessage, _) = error, statusCode == 401 {
                    await invalidateSession()
                    throw APIClientError.authenticationExpired(retryMessage)
                }
                throw error
            }
        }

        throw APIClientError.server(
            statusCode: http.statusCode,
            message: message,
            requestID: http.value(forHTTPHeaderField: "X-Request-ID")
        )
    }

    private func invalidateSession() async {
        try? await sessionStore.clearSession()
        NotificationCenter.default.post(
            name: .hikeJournalAuthenticationExpired,
            object: nil
        )
    }

    private static func isAuthenticationFailure(_ error: Error) -> Bool {
        guard let error = error as? APIClientError else { return false }
        switch error {
        case .sessionRequired, .authenticationExpired:
            return true
        case let .server(statusCode, _, _):
            return statusCode == 401 || statusCode == 403
        case .missingBaseURL,
             .invalidRequestPath,
             .requestEncodingFailed,
             .responseDecodingFailed,
             .responseTooLarge,
             .nonHTTPResponse,
             .transport:
            return false
        }
    }

    private func makeURLRequest<Response>(
        _ request: APIRequest<Response>,
        accessToken: String?
    ) throws -> URLRequest {
        guard let baseURL else { throw APIClientError.missingBaseURL }
        let decodedPath = request.path.removingPercentEncoding ?? request.path
        guard request.path.hasPrefix("/"),
              !request.path.contains("://"),
              !request.path.contains("?"),
              !request.path.contains("#"),
              !decodedPath.split(separator: "/").contains(".."),
              var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else {
            throw APIClientError.invalidRequestPath
        }

        let basePath = components.percentEncodedPath.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let endpointPath = request.path.drop(while: { $0 == "/" })
        components.percentEncodedPath = "/" + [basePath, String(endpointPath)]
            .filter { !$0.isEmpty }
            .joined(separator: "/")
        components.queryItems = request.queryItems.isEmpty ? nil : request.queryItems
        guard let url = components.url else {
            throw APIClientError.invalidRequestPath
        }

        var urlRequest = URLRequest(url: url)
        // API state is already cached explicitly per account by the offline
        // store. Do not let URLSession reuse a response from another account
        // or an earlier entitlement/media state.
        urlRequest.cachePolicy = .reloadIgnoringLocalCacheData
        urlRequest.httpMethod = request.method.rawValue
        urlRequest.httpBody = request.body
        urlRequest.timeoutInterval = request.timeoutInterval
        urlRequest.setValue("application/json", forHTTPHeaderField: "Accept")
        if request.body != nil {
            urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if let apiKey {
            urlRequest.setValue(apiKey, forHTTPHeaderField: "X-HikeJournal-Key")
        }
        if let accessToken, !accessToken.isEmpty {
            urlRequest.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }
        for (name, value) in request.headers
        where !name.caseInsensitiveCompare("Authorization").isOrderedSame
            && !name.caseInsensitiveCompare("X-HikeJournal-Key").isOrderedSame {
            urlRequest.setValue(value, forHTTPHeaderField: name)
        }
        return urlRequest
    }

    private func serverMessage(from data: Data, statusCode: Int) -> String {
        if let payload = try? decoder.decode(ServerErrorPayload.self, from: data),
           !payload.message.isEmpty {
            return payload.message
        }
        return HTTPURLResponse.localizedString(forStatusCode: statusCode).capitalized + "."
    }
}

private struct ServerErrorPayload: Decodable {
    let message: String

    private enum CodingKeys: String, CodingKey {
        case detail
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        if let detail = try? container.decode(String.self, forKey: .detail) {
            message = detail
            return
        }
        if let validation = try? container.decode([ValidationDetail].self, forKey: .detail),
           let first = validation.first {
            message = first.message
            return
        }
        message = ""
    }
}

private struct ValidationDetail: Decodable {
    let message: String

    enum CodingKeys: String, CodingKey {
        case message = "msg"
    }
}

extension JSONDecoder {
    static var hikeJournal: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let value = try decoder.singleValueContainer().decode(String.self)
            let fractional = ISO8601DateFormatter()
            fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = fractional.date(from: value) {
                return date
            }
            let standard = ISO8601DateFormatter()
            standard.formatOptions = [.withInternetDateTime]
            if let date = standard.date(from: value) {
                return date
            }
            throw DecodingError.dataCorruptedError(
                in: try decoder.singleValueContainer(),
                debugDescription: "Expected an ISO-8601 timestamp."
            )
        }
        return decoder
    }
}

private extension String {
    var nilIfEmpty: String? {
        isEmpty ? nil : self
    }
}

private extension ComparisonResult {
    var isOrderedSame: Bool {
        self == .orderedSame
    }
}
