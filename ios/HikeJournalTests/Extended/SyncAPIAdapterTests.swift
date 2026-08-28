import Foundation
import HikeJournalPersistence
import HikeJournalSync
import XCTest
@testable import HikeJournal

final class SyncAPIAdapterTests: XCTestCase {
    private let timestamp = Date(timeIntervalSince1970: 1_800_000_000)
    private let hikeID = "11111111-2222-3333-4444-555555555555"
    private let entityID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    private let operationID = "operation-0001"

    func testMapsEveryNonFileOperationToExactMobileAPIRequest() throws {
        let fixture = try SyncTemporaryDirectory()
        let builder = SyncOperationRequestBuilder(
            fileStore: AccountSyncFileStore(allowedRoots: [fixture.url])
        )
        let hikePayload: [String: Any] = [
            "title": "Morning trail",
            "hike_date": "2026-08-22",
            "distance_miles": 4.25,
            "location_name": "Pine Ridge",
            "notes": "Clear and warm",
            "location_id": NSNull(),
            "client_platform": "ios",
        ]
        let cases: [(PendingOperation, String, String, [String: Any]?)] = [
            (
                operation(.createHike, payload: hikePayload),
                "POST", "/v1/hikes",
                [
                    "id": entityID,
                    "title": "Morning trail",
                    "hike_date": "2026-08-22",
                    "distance_miles": 4.25,
                    "location_name": "Pine Ridge",
                    "notes": "Clear and warm",
                    "location_id": NSNull(),
                ]
            ),
            (
                operation(.updateHike, payload: hikePayload),
                "PUT", "/v1/hikes/\(entityID)",
                [
                    "title": "Morning trail",
                    "hike_date": "2026-08-22",
                    "distance_miles": 4.25,
                    "location_name": "Pine Ridge",
                    "notes": "Clear and warm",
                    "location_id": NSNull(),
                ]
            ),
            (
                operation(.archiveHike, payload: ["is_archived": true]),
                "PUT", "/v1/hikes/\(entityID)/archive", ["is_archived": true]
            ),
            (
                operation(.deleteHike),
                "DELETE", "/v1/hikes/\(entityID)", nil
            ),
            (
                operation(
                    .setHikeCover,
                    payload: ["photo_id": entityID, "cover_url": "file:///private/local.jpg"]
                ),
                "PUT", "/v1/hikes/\(entityID)/cover", ["photo_id": entityID]
            ),
            (
                operation(.updateCaption, payload: ["caption": "Creek crossing"]),
                "PUT", "/v1/photos/\(entityID)/caption", ["caption": "Creek crossing"]
            ),
            (
                operation(.deletePhoto),
                "DELETE", "/v1/photos/\(entityID)", nil
            ),
            (
                operation(.queueSpeciesReview, payload: [:]),
                "PUT", "/v1/photos/\(entityID)/review", ["queued": true]
            ),
            (
                operation(
                    .assignKnownSpecies,
                    payload: [
                        "taxon_id": 42,
                        "common_name": "Green anole",
                        "scientific_name": "Anolis carolinensis",
                    ]
                ),
                "PUT", "/v1/photos/\(entityID)/species",
                [
                    "taxon_id": 42,
                    "common_name": "Green anole",
                    "scientific_name": "Anolis carolinensis",
                ]
            ),
            (
                operation(
                    .reviewDecision,
                    payload: [
                        "action": "confirm",
                        "observation_id": "observation-1",
                        "candidate": [
                            "taxon_id": 42,
                            "common_name": "Green anole",
                            "scientific_name": "Anolis carolinensis",
                            "confidence": 0.91,
                        ],
                    ]
                ),
                "POST", "/v1/species/review/\(entityID)/decision",
                [
                    "action": "confirm",
                    "observation_id": "observation-1",
                    "candidate": [
                        "taxon_id": 42,
                        "common_name": "Green anole",
                        "scientific_name": "Anolis carolinensis",
                        "confidence": 0.91,
                    ],
                ]
            ),
            (
                operation(
                    .updateSpeciesQuest,
                    payload: [
                        "focus_taxon_ids": [42, 84],
                        "platform": "ios",
                        "set_linked_hike": true,
                    ]
                ),
                "PATCH", "/v1/discovery/quests/\(entityID)",
                ["set_linked_hike": false, "focus_taxon_ids": [42, 84]]
            ),
            (
                operation(
                    .createFieldMark,
                    parentID: hikeID,
                    payload: [
                        "recording_session_id": NSNull(),
                        "marked_at": "2026-08-22T12:00:00Z",
                        "lat": 28.5,
                        "lng": -81.25,
                        "accuracy_meters": 4.0,
                        "mark_type": "water",
                        "note": "Spring",
                        "wait_for_hike_create": false,
                    ]
                ),
                "POST", "/v1/hikes/\(hikeID)/field-marks",
                [
                    "id": entityID,
                    "recording_session_id": NSNull(),
                    "marked_at": "2026-08-22T12:00:00Z",
                    "lat": 28.5,
                    "lng": -81.25,
                    "accuracy_meters": 4.0,
                    "mark_type": "water",
                    "note": "Spring",
                ]
            ),
            (
                operation(
                    .updateNaturalHistory,
                    payload: [
                        "confidence": "likely",
                        "provenance": "user",
                        "phenophases": ["flowering", "fruiting"],
                    ]
                ),
                "PUT", "/v1/observations/\(entityID)/natural-history",
                [
                    "confidence": "likely",
                    "provenance": "user",
                    "phenophases": [
                        ["code": "flowering"],
                        ["code": "fruiting"],
                    ],
                ]
            ),
        ]

        var coveredKinds = Set<PendingOperationKind>()
        for (operation, expectedMethod, expectedPath, expectedBody) in cases {
            let prepared = try builder.prepare(
                operation: operation,
                idempotencyKey: SyncIdempotencyKey(operationID: operationID)
            )
            coveredKinds.insert(operation.kind)
            XCTAssertEqual(prepared.method.rawValue, expectedMethod, operation.kind.rawValue)
            XCTAssertEqual(prepared.path, expectedPath, operation.kind.rawValue)
            XCTAssertEqual(
                prepared.headers,
                [SyncAPIAdapterConstants.idempotencyHeader: operationID],
                operation.kind.rawValue
            )
            XCTAssertFalse(prepared.headers.keys.contains { $0.lowercased().contains("platform") })
            if let expectedBody {
                assertJSON(prepared.body, equals: expectedBody, operation.kind.rawValue)
            } else {
                XCTAssertNil(prepared.body, operation.kind.rawValue)
            }
        }

        let fileKinds: Set<PendingOperationKind> = [.uploadPhoto, .uploadRoute]
        XCTAssertEqual(coveredKinds.union(fileKinds), Set(PendingOperationKind.allCases))
    }

    func testPhotoAndTCXMultipartMatchServerFieldNamesAndLimits() throws {
        let fixture = try SyncTemporaryDirectory()
        let photoURL = fixture.url.appendingPathComponent("queued-photo.jpg")
        let routeURL = fixture.url.appendingPathComponent("recorded-route.tcx")
        try Data("jpeg-bytes".utf8).write(to: photoURL)
        try Data("<TrainingCenterDatabase/>".utf8).write(to: routeURL)
        let builder = SyncOperationRequestBuilder(
            fileStore: AccountSyncFileStore(allowedRoots: [fixture.url])
        )

        let photo = operation(
            .uploadPhoto,
            parentID: "everyday",
            payload: [
                "caption": "Trail bird",
                "queue_for_review": true,
                "taken_at": "2026-08-22T12:00:00Z",
                "lat": 28.5,
                "lng": -81.25,
                "width": 4_032,
                "height": 3_024,
                "platform": "ios",
            ],
            localFilePath: photoURL.path,
            contentType: "image/jpeg",
            fileName: "bird.jpg"
        )
        let photoRequest = try builder.prepare(
            operation: photo,
            idempotencyKey: SyncIdempotencyKey(operationID: operationID)
        )
        let photoBody = String(decoding: try XCTUnwrap(photoRequest.body), as: UTF8.self)
        XCTAssertEqual(photoRequest.path, "/v1/hikes/everyday/photos")
        XCTAssertEqual(photoRequest.timeoutInterval, SyncAPIAdapterConstants.uploadTimeout)
        XCTAssertEqual(
            photoRequest.maximumResponseBytes,
            SyncAPIAdapterConstants.maximumResponseBytes
        )
        XCTAssertTrue(photoBody.contains("name=\"caption\"\r\n\r\nTrail bird"))
        XCTAssertTrue(photoBody.contains("name=\"queue_for_review\"\r\n\r\ntrue"))
        XCTAssertTrue(photoBody.contains("name=\"photo_id\"\r\n\r\n\(entityID)"))
        XCTAssertTrue(photoBody.contains("name=\"taken_at\"\r\n\r\n2026-08-22T12:00:00Z"))
        XCTAssertTrue(photoBody.contains("name=\"lat\"\r\n\r\n28.5"))
        XCTAssertTrue(photoBody.contains("name=\"lng\"\r\n\r\n-81.25"))
        XCTAssertTrue(photoBody.contains("name=\"file\"; filename=\"bird.jpg\""))
        XCTAssertTrue(photoBody.contains("Content-Type: image/jpeg"))
        XCTAssertFalse(photoBody.contains("name=\"width\""))
        XCTAssertFalse(photoBody.contains("name=\"height\""))
        XCTAssertFalse(photoBody.contains("platform"))

        let route = operation(
            .uploadRoute,
            parentID: hikeID,
            payload: [
                "source_type": "hikejournal_ios_gps",
                "route_segments": [["local-only"]],
            ],
            localFilePath: routeURL.path,
            contentType: "text/plain",
            fileName: "outing.tcx"
        )
        let routeRequest = try builder.prepare(
            operation: route,
            idempotencyKey: SyncIdempotencyKey(operationID: operationID)
        )
        let routeBody = String(decoding: try XCTUnwrap(routeRequest.body), as: UTF8.self)
        XCTAssertEqual(routeRequest.path, "/v1/hikes/\(hikeID)/route")
        XCTAssertTrue(
            routeBody.contains("name=\"source_type\"\r\n\r\nhikejournal_ios_gps")
        )
        XCTAssertTrue(routeBody.contains("name=\"file\"; filename=\"outing.tcx\""))
        XCTAssertTrue(routeBody.contains("Content-Type: application/vnd.garmin.tcx+xml"))
        XCTAssertFalse(routeBody.contains("route_segments"))
    }

    func testRemovingPhotoFromSpeciesReviewUsesTheExistingUnqueueOperation() throws {
        let fixture = try SyncTemporaryDirectory()
        let builder = SyncOperationRequestBuilder(
            fileStore: AccountSyncFileStore(allowedRoots: [fixture.url])
        )
        let prepared = try builder.prepare(
            operation: operation(.queueSpeciesReview, payload: ["queued": false]),
            idempotencyKey: SyncIdempotencyKey(operationID: operationID)
        )

        XCTAssertEqual(prepared.method.rawValue, "PUT")
        XCTAssertEqual(prepared.path, "/v1/photos/\(entityID)/review")
        assertJSON(prepared.body, equals: ["queued": false], "remove from species review")
    }

    func testRejectsForeignFilesUnsafeHeaderIDsAndAndroidRouteSource() throws {
        let fixture = try SyncTemporaryDirectory()
        let foreign = try SyncTemporaryDirectory()
        let foreignFile = foreign.url.appendingPathComponent("private.jpg")
        try Data("not-owned".utf8).write(to: foreignFile)
        let localRoute = fixture.url.appendingPathComponent("route.tcx")
        try Data("<tcx/>".utf8).write(to: localRoute)
        let builder = SyncOperationRequestBuilder(
            fileStore: AccountSyncFileStore(allowedRoots: [fixture.url])
        )

        XCTAssertThrowsError(
            try builder.prepare(
                operation: operation(
                    .uploadPhoto,
                    parentID: hikeID,
                    localFilePath: foreignFile.path
                ),
                idempotencyKey: SyncIdempotencyKey(operationID: operationID)
            )
        ) { error in
            guard case .validation = error as? SyncExecutionFailure else {
                return XCTFail("Expected account-scope validation, got \(error)")
            }
        }

        XCTAssertThrowsError(
            try builder.prepare(
                operation: operation(.deletePhoto),
                idempotencyKey: SyncIdempotencyKey(rawValue: "bad\r\nX-Evil: yes")
            )
        )

        XCTAssertThrowsError(
            try builder.prepare(
                operation: operation(
                    .uploadRoute,
                    parentID: hikeID,
                    payload: ["source_type": "hikejournal_android_gps"],
                    localFilePath: localRoute.path,
                    fileName: "route.tcx"
                ),
                idempotencyKey: SyncIdempotencyKey(operationID: operationID)
            )
        )
    }

    func testExecutorUsesAPIClientRefreshAndStableOperationIDHeader() async throws {
        let sessionStore = MemorySessionStore(session: session(accessToken: "old-access"))
        let transport = SyncRefreshTransport()
        let fixedTimestamp = timestamp
        let client = APIClient(
            baseURL: URL(string: "https://api.hikejournal.example"),
            apiKey: "pairing-key",
            transport: transport,
            sessionStore: sessionStore,
            now: { fixedTimestamp }
        )
        let adapter = SyncOperationAPIAdapter(
            apiClient: client,
            fileStore: AccountSyncFileStore(allowedRoots: []),
            connectivity: .alwaysAvailable
        )
        let operation = operation(
            .createHike,
            payload: [
                "title": "Synced hike",
                "hike_date": "2026-08-22",
            ]
        )

        _ = try await adapter.executor().execute(
            operation,
            idempotencyKey: SyncIdempotencyKey(operationID: operation.id)
        )

        let requests = await transport.requests()
        let mutations = requests.filter { $0.url?.path == "/v1/hikes" }
        XCTAssertEqual(mutations.count, 2)
        XCTAssertEqual(
            mutations.map { $0.value(forHTTPHeaderField: "Authorization") },
            ["Bearer old-access", "Bearer new-access"]
        )
        XCTAssertEqual(
            mutations.map { $0.value(forHTTPHeaderField: SyncAPIAdapterConstants.idempotencyHeader) },
            [operation.id, operation.id]
        )
        XCTAssertTrue(mutations.allSatisfy {
            $0.value(forHTTPHeaderField: "X-HikeJournal-Key") == "pairing-key"
        })
        XCTAssertTrue(mutations.allSatisfy { request in
            request.allHTTPHeaderFields?.keys.allSatisfy {
                !$0.lowercased().contains("platform")
            } == true
        })
    }

    func testClassifiesQuotaValidationRetryAndOfflineFailures() async throws {
        let operation = operation(
            .createHike,
            payload: ["title": "Queued", "hike_date": "2026-08-22"]
        )
        let cases: [(Int, String, SyncExecutionFailure)] = [
            (
                402,
                "Your cloud media quota has been reached.",
                .quotaExceeded(
                    resource: "media",
                    message: "Your cloud media quota has been reached."
                )
            ),
            (422, "Title is invalid.", .validation(message: "Title is invalid.")),
            (
                503,
                "Service unavailable.",
                .retryableServer(statusCode: 503, message: "Service unavailable.")
            ),
        ]
        for (status, message, expected) in cases {
            let adapter = makeAdapter(
                transport: SingleSyncResponseTransport(status: status, message: message),
                connectivity: .alwaysAvailable
            )
            do {
                _ = try await adapter.executor().execute(
                    operation,
                    idempotencyKey: SyncIdempotencyKey(operationID: operation.id)
                )
                XCTFail("Expected HTTP \(status) to fail")
            } catch let failure as SyncExecutionFailure {
                XCTAssertEqual(failure, expected)
            }
        }

        let offlineAdapter = makeAdapter(
            transport: OfflineSyncTransport(),
            connectivity: .alwaysUnavailable
        )
        do {
            _ = try await offlineAdapter.executor().execute(
                operation,
                idempotencyKey: SyncIdempotencyKey(operationID: operation.id)
            )
            XCTFail("Expected offline failure")
        } catch let failure as SyncExecutionFailure {
            guard case .offline = failure else {
                return XCTFail("Expected offline classification, got \(failure)")
            }
        }
    }

    func testMediaCleanupOccursOnlyAfterAcknowledgementAndDurableQueueDeletion() async throws {
        let failureFixture = try SyncTemporaryDirectory()
        let failedFile = failureFixture.url.appendingPathComponent("failed.jpg")
        try Data("failed-media".utf8).write(to: failedFile)
        let failedDatabase = try OfflineDatabase(
            path: failureFixture.url.appendingPathComponent("failed.sqlite").path
        )
        let failedOperation = operation(
            .uploadPhoto,
            parentID: hikeID,
            localFilePath: failedFile.path,
            contentType: "image/jpeg",
            fileName: "failed.jpg"
        )
        try await failedDatabase.upsertOperation(failedOperation)
        let failedFileStore = AccountSyncFileStore(allowedRoots: [failureFixture.url])
        let failedAdapter = makeAdapter(
            transport: SingleSyncResponseTransport(status: 503, message: "Try again."),
            connectivity: .alwaysAvailable,
            fileStore: failedFileStore
        )
        let failedCoordinator = SyncCoordinator(
            store: .offlineDatabase(failedDatabase),
            executor: failedAdapter.executor(),
            connectivity: .alwaysAvailable,
            clock: .fixed(timestamp),
            jitter: .none,
            mediaCleanup: SyncMediaCleanup { operation in
                try failedFileStore.removeAcknowledgedFile(for: operation)
            }
        )
        _ = try await failedCoordinator.drain()
        XCTAssertTrue(FileManager.default.fileExists(atPath: failedFile.path))
        let retainedFailure = try await failedDatabase.operation(id: failedOperation.id)
        XCTAssertNotNil(retainedFailure)

        let successFixture = try SyncTemporaryDirectory()
        let uploadedFile = successFixture.url.appendingPathComponent("uploaded.jpg")
        try Data("uploaded-media".utf8).write(to: uploadedFile)
        let successDatabase = try OfflineDatabase(
            path: successFixture.url.appendingPathComponent("success.sqlite").path
        )
        let successfulOperation = operation(
            .uploadPhoto,
            parentID: hikeID,
            localFilePath: uploadedFile.path,
            contentType: "image/jpeg",
            fileName: "uploaded.jpg"
        )
        try await successDatabase.upsertOperation(successfulOperation)
        let successFileStore = AccountSyncFileStore(allowedRoots: [successFixture.url])
        let successAdapter = makeAdapter(
            transport: SingleSyncResponseTransport(status: 201, message: ""),
            connectivity: .alwaysAvailable,
            fileStore: successFileStore
        )
        let successCoordinator = SyncCoordinator(
            store: .offlineDatabase(successDatabase),
            executor: successAdapter.executor(),
            connectivity: .alwaysAvailable,
            clock: .fixed(timestamp),
            mediaCleanup: SyncMediaCleanup { operation in
                try successFileStore.removeAcknowledgedFile(for: operation)
            }
        )
        _ = try await successCoordinator.drain()
        let removedSuccess = try await successDatabase.operation(id: successfulOperation.id)
        XCTAssertNil(removedSuccess)
        XCTAssertFalse(FileManager.default.fileExists(atPath: uploadedFile.path))
    }

    private func makeAdapter(
        transport: any HTTPTransport,
        connectivity: SyncConnectivityProvider,
        fileStore: AccountSyncFileStore = AccountSyncFileStore(allowedRoots: [])
    ) -> SyncOperationAPIAdapter {
        let fixedTimestamp = timestamp
        let client = APIClient(
            baseURL: URL(string: "https://api.hikejournal.example"),
            transport: transport,
            sessionStore: MemorySessionStore(session: session()),
            now: { fixedTimestamp }
        )
        return SyncOperationAPIAdapter(
            apiClient: client,
            fileStore: fileStore,
            connectivity: connectivity
        )
    }

    private func session(accessToken: String = "access") -> AuthSession {
        AuthSession(
            accessToken: accessToken,
            refreshToken: "refresh-token",
            expiresIn: 3_600,
            account: AuthAccount(
                subject: "apple:subject",
                email: "hiker@example.com",
                displayName: "Hiker",
                pictureURL: nil,
                userID: "00000000-0000-0000-0000-000000000001",
                identityProvider: "apple"
            ),
            obtainedAt: timestamp
        )
    }

    private func operation(
        _ kind: PendingOperationKind,
        parentID: String? = nil,
        payload: [String: Any] = [:],
        localFilePath: String? = nil,
        contentType: String? = nil,
        fileName: String? = nil
    ) -> PendingOperation {
        PendingOperation(
            id: operationID,
            kind: kind,
            entityID: entityID,
            parentID: parentID,
            payload: try! JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]),
            localFilePath: localFilePath,
            contentType: contentType,
            fileName: fileName,
            createdAt: timestamp,
            updatedAt: timestamp
        )
    }

    private func assertJSON(
        _ data: Data?,
        equals expected: [String: Any],
        _ context: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        guard let data,
              let actual = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return XCTFail("Missing JSON body for \(context)", file: file, line: line)
        }
        XCTAssertTrue(
            (actual as NSDictionary).isEqual(to: expected),
            "\(context): actual=\(actual) expected=\(expected)",
            file: file,
            line: line
        )
    }
}

private final class SyncTemporaryDirectory {
    let url: URL

    init() throws {
        url = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(
            at: url,
            withIntermediateDirectories: true
        )
    }

    deinit {
        try? FileManager.default.removeItem(at: url)
    }
}

private actor SyncRefreshTransport: HTTPTransport {
    private var captured: [URLRequest] = []
    private var mutationCount = 0

    func data(for request: URLRequest) throws -> (Data, URLResponse) {
        captured.append(request)
        switch request.url?.path {
        case "/v1/hikes":
            mutationCount += 1
            if mutationCount == 1 {
                return try response(
                    request,
                    status: 401,
                    body: #"{"detail":"Access token expired."}"#
                )
            }
            return try response(request, status: 201, body: "{}")

        case "/v1/auth/refresh":
            return try response(
                request,
                status: 200,
                body: #"{"access_token":"new-access","refresh_token":"new-refresh","expires_in":3600,"token_type":"Bearer","account":{"subject":"apple:subject","email":"hiker@example.com","display_name":"Hiker","picture_url":"","user_id":"00000000-0000-0000-0000-000000000001","identity_provider":"apple"}}"#
            )

        default:
            throw URLError(.badURL)
        }
    }

    func requests() -> [URLRequest] {
        captured
    }
}

private struct SingleSyncResponseTransport: HTTPTransport {
    let status: Int
    let message: String

    func data(for request: URLRequest) throws -> (Data, URLResponse) {
        let body = (200..<300).contains(status)
            ? "{}"
            : String(data: try JSONSerialization.data(
                withJSONObject: ["detail": message],
                options: [.sortedKeys]
            ), encoding: .utf8) ?? "{}"
        return try response(request, status: status, body: body)
    }
}

private struct OfflineSyncTransport: HTTPTransport {
    func data(for request: URLRequest) throws -> (Data, URLResponse) {
        throw URLError(.notConnectedToInternet)
    }
}

private func response(
    _ request: URLRequest,
    status: Int,
    body: String
) throws -> (Data, URLResponse) {
    guard let url = request.url,
          let response = HTTPURLResponse(
            url: url,
            statusCode: status,
            httpVersion: "HTTP/1.1",
            headerFields: nil
          ) else {
        throw URLError(.badServerResponse)
    }
    return (Data(body.utf8), response)
}
