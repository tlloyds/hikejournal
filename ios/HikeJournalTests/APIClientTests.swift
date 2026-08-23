import Foundation
import HikeJournalDomain
import XCTest
@testable import HikeJournal

final class APIClientTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_777_777_777)

    func testInjectsAPIKeyAndBearerWithoutAllowingHeaderOverride() async throws {
        let session = makeSession(accessToken: "trusted-access", refreshToken: "refresh")
        let store = MemorySessionStore(session: session)
        let transport = QueueTransport(
            responses: [.json(status: 200, #"{"value":"trail"}"#)]
        )
        let client = makeClient(transport: transport, store: store, apiKey: "pairing-key")

        let response: TestResponse = try await client.send(
            APIRequest(
                path: "/v1/test",
                headers: [
                    "Authorization": "Bearer attacker",
                    "X-HikeJournal-Key": "attacker",
                    "X-Client-Trace": "test-trace"
                ]
            )
        )

        XCTAssertEqual(response.value, "trail")
        let requests = await transport.requests()
        let request = try XCTUnwrap(requests.first)
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer trusted-access")
        XCTAssertEqual(request.value(forHTTPHeaderField: "X-HikeJournal-Key"), "pairing-key")
        XCTAssertEqual(request.value(forHTTPHeaderField: "X-Client-Trace"), "test-trace")
    }

    func testRefreshesOnceAfterUnauthorizedAndRetriesWithRotatedCredential() async throws {
        let store = MemorySessionStore(session: makeSession(accessToken: "old-access", refreshToken: "old-refresh"))
        let transport = RefreshingTransport(alwaysRejectProtectedRequest: false)
        let client = makeClient(transport: transport, store: store)

        let response: TestResponse = try await client.send(APIRequest(path: "/v1/protected"))

        XCTAssertEqual(response.value, "after-refresh")
        let counts = await transport.counts()
        XCTAssertEqual(counts.refresh, 1)
        XCTAssertEqual(counts.protected, 2)
        let storedSession = try await store.loadSession()
        XCTAssertEqual(storedSession?.accessToken, "new-access")
    }

    func testConcurrentExplicitRefreshesCoalesceIntoOneNetworkCall() async throws {
        let store = MemorySessionStore(session: makeSession(accessToken: "old-access", refreshToken: "old-refresh"))
        let transport = DelayedRefreshTransport()
        let client = makeClient(transport: transport, store: store)

        async let first = client.refreshSession()
        async let second = client.refreshSession()
        let sessions = try await [first, second]

        XCTAssertEqual(sessions.map(\.accessToken), ["new-access", "new-access"])
        let refreshCount = await transport.refreshCount()
        XCTAssertEqual(refreshCount, 1)
    }

    func testSecondUnauthorizedClearsPersistedSession() async throws {
        let store = MemorySessionStore(session: makeSession(accessToken: "old-access", refreshToken: "old-refresh"))
        let transport = RefreshingTransport(alwaysRejectProtectedRequest: true)
        let client = makeClient(transport: transport, store: store)

        do {
            let _: TestResponse = try await client.send(APIRequest(path: "/v1/protected"))
            XCTFail("Expected authentication to expire")
        } catch let error as APIClientError {
            XCTAssertEqual(error, .authenticationExpired("Access token expired."))
        }

        let storedSession = try await store.loadSession()
        XCTAssertNil(storedSession)
    }

    func testProactivelyRefreshesNearExpiry() async throws {
        let expiring = AuthSession(
            accessToken: "old-access",
            refreshToken: "old-refresh",
            expiresIn: 60,
            account: makeAccount(),
            obtainedAt: now
        )
        let store = MemorySessionStore(session: expiring)
        let transport = RefreshingTransport(alwaysRejectProtectedRequest: false)
        let client = makeClient(transport: transport, store: store)

        let response: TestResponse = try await client.send(APIRequest(path: "/v1/protected"))

        XCTAssertEqual(response.value, "after-refresh")
        let counts = await transport.counts()
        XCTAssertEqual(counts.refresh, 1)
        XCTAssertEqual(counts.protected, 1)
    }

    func testTransientRefreshFailureKeepsSessionForOfflineRetry() async throws {
        let expiring = AuthSession(
            accessToken: "old-access",
            refreshToken: "old-refresh",
            expiresIn: 60,
            account: makeAccount(),
            obtainedAt: now
        )
        let store = MemorySessionStore(session: expiring)
        let client = makeClient(
            transport: QueueTransport(responses: []),
            store: store
        )

        do {
            let _: TestResponse = try await client.send(APIRequest(path: "/v1/protected"))
            XCTFail("Expected the refresh request to be unavailable")
        } catch let error as APIClientError {
            guard case .transport = error else {
                return XCTFail("Expected a transport error, got \(error)")
            }
        }

        let storedSession = await store.loadSession()
        XCTAssertEqual(storedSession, expiring)
    }

    func testCancellationIsNotCollapsedIntoTransportError() async throws {
        let client = makeClient(
            transport: CancellationTransport(),
            store: MemorySessionStore(session: makeSession())
        )

        do {
            let _: TestResponse = try await client.send(APIRequest(path: "/v1/test"))
            XCTFail("Expected cancellation")
        } catch is CancellationError {
            // Expected: callers can distinguish cooperative cancellation from failure.
        }
    }

    func testValidationErrorIsTypedAndDoesNotExposeRawResponse() async throws {
        let transport = QueueTransport(
            responses: [
                .json(
                    status: 422,
                    #"{"detail":[{"loc":["body","title"],"msg":"Title is required.","type":"missing"}]}"#,
                    headers: ["X-Request-ID": "request-123"]
                )
            ]
        )
        let client = makeClient(transport: transport, store: MemorySessionStore(session: makeSession()))

        do {
            let _: TestResponse = try await client.send(APIRequest(path: "/v1/test"))
            XCTFail("Expected a server error")
        } catch let error as APIClientError {
            XCTAssertEqual(
                error,
                .server(statusCode: 422, message: "Title is required.", requestID: "request-123")
            )
        }
    }

    func testRejectsAbsoluteAndTraversalPathsBeforeTransport() async throws {
        let transport = QueueTransport(responses: [])
        let client = makeClient(transport: transport, store: MemorySessionStore(session: makeSession()))

        for path in ["https://evil.example/v1", "/v1/../account", "/v1/test?secret=yes"] {
            do {
                let _: TestResponse = try await client.send(APIRequest(path: path))
                XCTFail("Expected \(path) to be rejected")
            } catch let error as APIClientError {
                XCTAssertEqual(error, .invalidRequestPath)
            }
        }
        let requests = await transport.requests()
        XCTAssertTrue(requests.isEmpty)
    }

    func testPreservesConfiguredBasePath() async throws {
        let transport = QueueTransport(responses: [.json(status: 200, #"{"value":"ok"}"#)])
        let fixedNow = now
        let client = APIClient(
            baseURL: URL(string: "https://api.example/mobile"),
            transport: transport,
            sessionStore: MemorySessionStore(session: makeSession()),
            now: { fixedNow }
        )

        let _: TestResponse = try await client.send(APIRequest(path: "/v1/test"))

        let requests = await transport.requests()
        XCTAssertEqual(requests.first?.url?.path, "/mobile/v1/test")
    }

    func testPlaceConditionsCarriesFollowedGaugeIDsAsRepeatedQueryItems() async throws {
        let transport = QueueTransport(
            responses: [.json(status: 200, #"{"river_gauges":[]}"#)]
        )
        let client = makeClient(transport: transport, store: MemorySessionStore(session: makeSession()))

        _ = try await client.placeConditions(
            id: "place with spaces",
            riverDays: 30,
            followedGaugeIDs: ["USGS-02233484", "USGS-02233500"]
        )

        let requests = await transport.requests()
        let request = try XCTUnwrap(requests.first)
        let components = try XCTUnwrap(URLComponents(url: try XCTUnwrap(request.url), resolvingAgainstBaseURL: false))
        XCTAssertTrue(request.url?.absoluteString.contains("/v1/places/place%20with%20spaces/conditions") == true)
        XCTAssertEqual(components.queryItems?.filter { $0.name == "river_days" }.map(\.value), ["30"])
        XCTAssertEqual(
            components.queryItems?.filter { $0.name == "followed_gauge_id" }.compactMap(\.value),
            ["USGS-02233484", "USGS-02233500"]
        )
    }

    func testStartsAndReadsSmartReviewBatchWithStableRequestShape() async throws {
        let transport = QueueTransport(
            responses: [
                .json(status: 200, #"{"job_id":"review-job","state":"queued"}"#),
                .json(status: 200, #"{"job_id":"review-job","state":"completed"}"#),
            ]
        )
        let client = makeClient(transport: transport, store: MemorySessionStore(session: makeSession()))

        _ = try await client.startReviewBatch(
            groups: [["photo-a", "photo-b"], ["photo-c"]],
            clientRequestID: "review-request-1"
        )
        _ = try await client.reviewBatchStatus(jobID: "review-job")

        let requests = await transport.requests()
        XCTAssertEqual(requests.count, 2)
        XCTAssertEqual(requests[0].httpMethod, "POST")
        XCTAssertEqual(requests[0].url?.path, "/v1/species/review/batch-recommendation/start")
        XCTAssertEqual(requests[1].httpMethod, "GET")
        XCTAssertEqual(requests[1].url?.path, "/v1/species/review/batch-recommendation/review-job")

        let body = try XCTUnwrap(requests[0].httpBody)
        let payload = try XCTUnwrap(
            JSONSerialization.jsonObject(with: body) as? [String: Any]
        )
        XCTAssertEqual(payload["client_request_id"] as? String, "review-request-1")
        let groups = try XCTUnwrap(payload["groups"] as? [[String: Any]])
        XCTAssertEqual(groups.compactMap { $0["photo_ids"] as? [String] }, [["photo-a", "photo-b"], ["photo-c"]])
    }

    func testStartsAndReadsAcknowledgedPublishBatchWithPrivacyOptions() async throws {
        let transport = QueueTransport(
            responses: [
                .json(status: 200, #"{"job_id":"publish-job","state":"queued"}"#),
                .json(status: 200, #"{"job_id":"publish-job","state":"completed"}"#),
            ]
        )
        let client = makeClient(transport: transport, store: MemorySessionStore(session: makeSession()))

        _ = try await client.startPublishBatch(
            groups: [["observation-a", "observation-b"]],
            options: PublishOptions(
                observationIds: [],
                description: "Wetland edge",
                tags: ["field-note", "summer"],
                geoprivacy: "obscured",
                captive: false
            ),
            clientRequestID: "publish-request-1"
        )
        _ = try await client.publishBatchStatus(jobID: "publish-job")

        let requests = await transport.requests()
        XCTAssertEqual(requests.count, 2)
        XCTAssertEqual(requests[0].httpMethod, "POST")
        XCTAssertEqual(requests[0].url?.path, "/v1/species/publish/batch/start")
        XCTAssertEqual(requests[1].httpMethod, "GET")
        XCTAssertEqual(requests[1].url?.path, "/v1/species/publish/batch/publish-job")

        let body = try XCTUnwrap(requests[0].httpBody)
        let payload = try XCTUnwrap(
            JSONSerialization.jsonObject(with: body) as? [String: Any]
        )
        XCTAssertEqual(payload["acknowledged_public"] as? Bool, true)
        XCTAssertEqual(payload["client_request_id"] as? String, "publish-request-1")
        XCTAssertEqual(payload["description"] as? String, "Wetland edge")
        XCTAssertEqual(payload["tags"] as? [String], ["field-note", "summer"])
        XCTAssertEqual(payload["geoprivacy"] as? String, "obscured")
        XCTAssertEqual(payload["captive"] as? Bool, false)
        let groups = try XCTUnwrap(payload["groups"] as? [[String: Any]])
        XCTAssertEqual(groups.compactMap { $0["observation_ids"] as? [String] }, [["observation-a", "observation-b"]])
    }

    private func makeClient(
        transport: any HTTPTransport,
        store: any SessionStoring,
        apiKey: String? = nil
    ) -> APIClient {
        let fixedNow = now
        return APIClient(
            baseURL: URL(string: "https://api.hikejournal.example"),
            apiKey: apiKey,
            transport: transport,
            sessionStore: store,
            now: { fixedNow }
        )
    }

    private func makeSession(
        accessToken: String = "access",
        refreshToken: String = "refresh"
    ) -> AuthSession {
        AuthSession(
            accessToken: accessToken,
            refreshToken: refreshToken,
            expiresIn: 1_200,
            account: makeAccount(),
            obtainedAt: now
        )
    }

    private func makeAccount() -> AuthAccount {
        AuthAccount(
            subject: "apple:subject",
            email: "hiker@example.com",
            displayName: "Hiker",
            pictureURL: nil,
            userID: "00000000-0000-0000-0000-000000000001",
            identityProvider: "apple"
        )
    }
}

private struct TestResponse: Codable, Equatable {
    let value: String
}

private struct TransportResponse: Sendable {
    let status: Int
    let data: Data
    let headers: [String: String]

    static func json(status: Int, _ body: String, headers: [String: String] = [:]) -> TransportResponse {
        TransportResponse(status: status, data: Data(body.utf8), headers: headers)
    }

    func response(for request: URLRequest) throws -> (Data, URLResponse) {
        guard let url = request.url,
              let response = HTTPURLResponse(
                url: url,
                statusCode: status,
                httpVersion: "HTTP/1.1",
                headerFields: headers
              ) else {
            throw URLError(.badServerResponse)
        }
        return (data, response)
    }
}

private actor QueueTransport: HTTPTransport {
    private var pending: [TransportResponse]
    private var captured: [URLRequest] = []

    init(responses: [TransportResponse]) {
        pending = responses
    }

    func data(for request: URLRequest) throws -> (Data, URLResponse) {
        captured.append(request)
        guard !pending.isEmpty else { throw URLError(.resourceUnavailable) }
        return try pending.removeFirst().response(for: request)
    }

    func requests() -> [URLRequest] {
        captured
    }
}

private actor RefreshingTransport: HTTPTransport {
    private let alwaysRejectProtectedRequest: Bool
    private var refreshRequests = 0
    private var protectedRequests = 0

    init(alwaysRejectProtectedRequest: Bool) {
        self.alwaysRejectProtectedRequest = alwaysRejectProtectedRequest
    }

    func data(for request: URLRequest) throws -> (Data, URLResponse) {
        switch request.url?.path {
        case "/v1/auth/refresh":
            refreshRequests += 1
            return try TransportResponse.json(status: 200, Self.refreshedSessionJSON).response(for: request)
        case "/v1/protected":
            protectedRequests += 1
            let isNew = request.value(forHTTPHeaderField: "Authorization") == "Bearer new-access"
            if isNew, !alwaysRejectProtectedRequest {
                return try TransportResponse.json(status: 200, #"{"value":"after-refresh"}"#).response(for: request)
            }
            return try TransportResponse.json(
                status: 401,
                #"{"detail":"Access token expired."}"#
            ).response(for: request)
        default:
            throw URLError(.badURL)
        }
    }

    func counts() -> (refresh: Int, protected: Int) {
        (refreshRequests, protectedRequests)
    }

    static let refreshedSessionJSON = #"{"access_token":"new-access","refresh_token":"new-refresh","expires_in":1200,"token_type":"Bearer","account":{"subject":"apple:subject","email":"hiker@example.com","display_name":"Hiker","picture_url":"","user_id":"00000000-0000-0000-0000-000000000001","identity_provider":"apple"}}"#
}

private actor DelayedRefreshTransport: HTTPTransport {
    private var count = 0

    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        guard request.url?.path == "/v1/auth/refresh" else { throw URLError(.badURL) }
        count += 1
        try await Task.sleep(for: .milliseconds(75))
        return try TransportResponse.json(
            status: 200,
            RefreshingTransport.refreshedSessionJSON
        ).response(for: request)
    }

    func refreshCount() -> Int {
        count
    }
}

private struct CancellationTransport: HTTPTransport {
    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        throw CancellationError()
    }
}
