import Foundation
import HikeJournalPersistence
import HikeJournalSync

enum SyncAPIAdapterConstants {
    static let idempotencyHeader = "Idempotency-Key"
    static let maximumUploadBytes = 30 * 1_024 * 1_024
    static let maximumResponseBytes = 2 * 1_024 * 1_024
    static let uploadTimeout: TimeInterval = 90
}

struct PreparedSyncRequest: Sendable {
    let method: HTTPMethod
    let path: String
    let body: Data?
    let headers: [String: String]
    let timeoutInterval: TimeInterval
    let maximumResponseBytes: Int
}

struct AccountSyncFileStore: Sendable {
    struct Upload: Sendable {
        let data: Data
        let fileName: String
        let contentType: String
    }

    private let allowedRoots: [URL]

    init(allowedRoots: [URL]) {
        self.allowedRoots = allowedRoots.map {
            $0.standardizedFileURL.resolvingSymlinksInPath()
        }
    }

    func upload(
        for operation: PendingOperation,
        defaultFileName: String,
        defaultContentType: String
    ) throws -> Upload {
        guard let rawPath = operation.localFilePath?.trimmingCharacters(
            in: .whitespacesAndNewlines
        ), !rawPath.isEmpty else {
            throw validation("The queued upload no longer has a staged file reference.")
        }
        let fileURL = try ownedFileURL(rawPath, mustExist: true)
        let values: URLResourceValues
        do {
            values = try fileURL.resourceValues(forKeys: [
                .isRegularFileKey,
                .isSymbolicLinkKey,
                .fileSizeKey,
            ])
        } catch {
            throw validation("The queued upload is no longer available in app storage.")
        }
        guard values.isRegularFile == true,
              values.isSymbolicLink != true,
              let size = values.fileSize,
              size > 0 else {
            throw validation("The queued upload is missing or is not a regular file.")
        }
        guard size <= SyncAPIAdapterConstants.maximumUploadBytes else {
            throw validation("Photos, videos, and TCX files must be 30 MB or smaller.")
        }

        let data: Data
        do {
            data = try Data(contentsOf: fileURL, options: [.mappedIfSafe])
        } catch {
            throw validation("The queued upload could not be reopened from app storage.")
        }
        guard data.count == size,
              !data.isEmpty,
              data.count <= SyncAPIAdapterConstants.maximumUploadBytes else {
            throw validation("The queued upload changed while HikeJournal was preparing it.")
        }
        return Upload(
            data: data,
            fileName: safeFileName(operation.fileName, fallback: defaultFileName),
            contentType: safeContentType(operation.contentType, fallback: defaultContentType)
        )
    }

    /// Called by `SyncCoordinator` only after remote acknowledgement and
    /// verified durable queue deletion. Paths are revalidated at deletion time.
    func removeAcknowledgedFile(for operation: PendingOperation) throws {
        guard let rawPath = operation.localFilePath?.trimmingCharacters(
            in: .whitespacesAndNewlines
        ), !rawPath.isEmpty else { return }
        let candidate = URL(fileURLWithPath: rawPath).standardizedFileURL
        guard FileManager.default.fileExists(atPath: candidate.path) else { return }
        let fileURL = try ownedFileURL(rawPath, mustExist: true)
        let values = try fileURL.resourceValues(forKeys: [
            .isRegularFileKey,
            .isSymbolicLinkKey,
        ])
        guard values.isRegularFile == true, values.isSymbolicLink != true else {
            throw validation("HikeJournal refused to remove a non-file staging path.")
        }
        try FileManager.default.removeItem(at: fileURL)
        try removeCompletedMediaManifestIfEmpty(fileURL.deletingLastPathComponent())
    }

    private func ownedFileURL(_ rawPath: String, mustExist: Bool) throws -> URL {
        let original = URL(fileURLWithPath: rawPath).standardizedFileURL
        if mustExist {
            let originalValues = try? original.resourceValues(forKeys: [.isSymbolicLinkKey])
            guard originalValues?.isSymbolicLink != true else {
                throw validation("HikeJournal refused an unsafe staged-file link.")
            }
        }
        let resolved = original.resolvingSymlinksInPath()
        guard allowedRoots.contains(where: { root in
            let rootPath = root.path.hasSuffix("/") ? root.path : root.path + "/"
            return resolved.path.hasPrefix(rootPath)
        }) else {
            throw validation("The queued upload is outside this account's app-owned storage.")
        }
        return resolved
    }

    private func removeCompletedMediaManifestIfEmpty(_ directory: URL) throws {
        guard directory.path.contains("/HikeJournalMediaStaging/") else { return }
        let children = try FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: nil,
            options: []
        )
        guard children.count == 1,
              children[0].lastPathComponent == "manifest.json" else { return }
        try FileManager.default.removeItem(at: directory)
    }

    private func safeFileName(_ proposed: String?, fallback: String) -> String {
        let raw = proposed?.trimmingCharacters(in: .whitespacesAndNewlines)
        let candidate = raw?.isEmpty == false ? raw! : fallback
        let leaf = (candidate as NSString).lastPathComponent
        let cleaned = leaf
            .replacingOccurrences(of: "\\", with: "_")
            .replacingOccurrences(of: "\"", with: "_")
            .replacingOccurrences(of: "\r", with: "_")
            .replacingOccurrences(of: "\n", with: "_")
        return cleaned.isEmpty ? fallback : String(cleaned.prefix(180))
    }

    private func safeContentType(_ proposed: String?, fallback: String) -> String {
        let value = proposed?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard value.count <= 160,
              value.contains("/"),
              !value.contains("\r"),
              !value.contains("\n") else { return fallback }
        return value
    }

    private func validation(_ message: String) -> SyncExecutionFailure {
        .validation(message: message)
    }
}

struct SyncOperationRequestBuilder: Sendable {
    private let fileStore: AccountSyncFileStore

    init(fileStore: AccountSyncFileStore) {
        self.fileStore = fileStore
    }

    func prepare(
        operation: PendingOperation,
        idempotencyKey: SyncIdempotencyKey
    ) throws -> PreparedSyncRequest {
        let headers = [
            SyncAPIAdapterConstants.idempotencyHeader:
                try safeIdempotencyValue(idempotencyKey.rawValue)
        ]
        switch operation.kind {
        case .createHike:
            var body = try hikeBody(operation.payload)
            body["id"] = operation.entityID
            return try jsonRequest(.post, "/v1/hikes", body, headers: headers)

        case .updateHike:
            return try jsonRequest(
                .put,
                "/v1/hikes/\(try pathSegment(operation.entityID))",
                try hikeBody(operation.payload),
                headers: headers
            )

        case .archiveHike:
            let payload = try object(operation.payload)
            return try jsonRequest(
                .put,
                "/v1/hikes/\(try pathSegment(operation.entityID))/archive",
                ["is_archived": boolean(payload["is_archived"], default: false)],
                headers: headers
            )

        case .deleteHike:
            return request(
                .delete,
                "/v1/hikes/\(try pathSegment(operation.entityID))",
                headers: headers
            )

        case .uploadPhoto:
            return try photoUpload(operation, headers: headers, idempotencyKey: idempotencyKey)

        case .uploadRoute:
            return try routeUpload(operation, headers: headers, idempotencyKey: idempotencyKey)

        case .setHikeCover:
            let payload = try object(operation.payload)
            return try jsonRequest(
                .put,
                "/v1/hikes/\(try pathSegment(operation.entityID))/cover",
                ["photo_id": stringOrNull(payload["photo_id"])],
                headers: headers
            )

        case .updateCaption:
            let payload = try object(operation.payload)
            return try jsonRequest(
                .put,
                "/v1/photos/\(try pathSegment(operation.entityID))/caption",
                ["caption": string(payload["caption"], default: "")],
                headers: headers
            )

        case .deletePhoto:
            return request(
                .delete,
                "/v1/photos/\(try pathSegment(operation.entityID))",
                headers: headers
            )

        case .queueSpeciesReview:
            let payload = try object(operation.payload)
            return try jsonRequest(
                .put,
                "/v1/photos/\(try pathSegment(operation.entityID))/review",
                ["queued": boolean(payload["queued"], default: true)],
                headers: headers
            )

        case .assignKnownSpecies:
            let payload = try object(operation.payload)
            return try jsonRequest(
                .put,
                "/v1/photos/\(try pathSegment(operation.entityID))/species",
                [
                    "taxon_id": numberOrNull(payload["taxon_id"]),
                    "common_name": string(payload["common_name"], default: ""),
                    "scientific_name": string(payload["scientific_name"], default: ""),
                ],
                headers: headers
            )

        case .reviewDecision:
            let payload = try object(operation.payload)
            let action = try requiredString(payload["action"], name: "review action")
            var body: [String: Any] = [
                "action": action,
                "observation_id": stringOrNull(payload["observation_id"]),
                "candidate": NSNull(),
            ]
            if let candidate = payload["candidate"] as? [String: Any] {
                body["candidate"] = [
                    "taxon_id": numberOrNull(candidate["taxon_id"]),
                    "common_name": string(candidate["common_name"], default: ""),
                    "scientific_name": string(candidate["scientific_name"], default: ""),
                    "confidence": numberOrNull(candidate["confidence"]),
                ]
            }
            return try jsonRequest(
                .post,
                "/v1/species/review/\(try pathSegment(operation.entityID))/decision",
                body,
                headers: headers
            )

        case .updateSpeciesQuest:
            let payload = try object(operation.payload)
            return try jsonRequest(
                .patch,
                "/v1/discovery/quests/\(try pathSegment(operation.entityID))",
                [
                    "set_linked_hike": false,
                    "focus_taxon_ids": payload["focus_taxon_ids"] as? [Any] ?? [],
                ],
                headers: headers
            )

        case .createFieldMark:
            let payload = try object(operation.payload)
            let hikeID = try requiredParentID(operation)
            return try jsonRequest(
                .post,
                "/v1/hikes/\(try pathSegment(hikeID))/field-marks",
                [
                    "id": operation.entityID,
                    "recording_session_id": stringOrNull(payload["recording_session_id"]),
                    "marked_at": try requiredString(payload["marked_at"], name: "field-mark time"),
                    "lat": try requiredNumber(payload["lat"], name: "field-mark latitude"),
                    "lng": try requiredNumber(payload["lng"], name: "field-mark longitude"),
                    "accuracy_meters": numberOrNull(payload["accuracy_meters"]),
                    "mark_type": string(payload["mark_type"], default: "note"),
                    "note": string(payload["note"], default: ""),
                ],
                headers: headers
            )

        case .updateNaturalHistory:
            let payload = try object(operation.payload)
            let rawPhenophases = payload["phenophases"] as? [Any] ?? []
            let phenophases: [[String: Any]] = try rawPhenophases.map { raw in
                if let code = raw as? String {
                    return ["code": code]
                }
                if let item = raw as? [String: Any] {
                    return [
                        "code": try requiredString(item["code"], name: "phenophase code"),
                        "metadata": item["metadata"] as? [String: Any] ?? [:],
                    ]
                }
                throw validation("A queued phenophase has an invalid format.")
            }
            return try jsonRequest(
                .put,
                "/v1/observations/\(try pathSegment(operation.entityID))/natural-history",
                [
                    "confidence": string(payload["confidence"], default: "tentative"),
                    "provenance": string(payload["provenance"], default: "user"),
                    "phenophases": phenophases,
                ],
                headers: headers
            )
        }
    }

    private func hikeBody(_ data: Data) throws -> [String: Any] {
        let payload = try object(data)
        return [
            "title": try requiredString(payload["title"], name: "hike title"),
            "hike_date": try requiredString(payload["hike_date"], name: "hike date"),
            "distance_miles": numberOrNull(payload["distance_miles"]),
            "location_name": string(payload["location_name"], default: ""),
            "notes": string(payload["notes"], default: ""),
            "location_id": stringOrNull(payload["location_id"]),
        ]
    }

    private func photoUpload(
        _ operation: PendingOperation,
        headers: [String: String],
        idempotencyKey: SyncIdempotencyKey
    ) throws -> PreparedSyncRequest {
        let hikeID = try requiredParentID(operation)
        let payload = try object(operation.payload)
        let upload = try fileStore.upload(
            for: operation,
            defaultFileName: "hike-photo.jpg",
            defaultContentType: inferredMediaType(fileName: operation.fileName)
        )
        var fields = [
            MultipartField(name: "caption", value: string(payload["caption"], default: "")),
            MultipartField(
                name: "queue_for_review",
                value: boolean(payload["queue_for_review"], default: false) ? "true" : "false"
            ),
            MultipartField(name: "photo_id", value: operation.entityID),
        ]
        if let takenAt = nonemptyString(payload["taken_at"]) {
            fields.append(MultipartField(name: "taken_at", value: takenAt))
        }
        if let latitude = formNumber(payload["lat"]) {
            fields.append(MultipartField(name: "lat", value: latitude))
        }
        if let longitude = formNumber(payload["lng"]) {
            fields.append(MultipartField(name: "lng", value: longitude))
        }
        return multipartRequest(
            path: "/v1/hikes/\(try pathSegment(hikeID))/photos",
            fields: fields,
            upload: upload,
            fileFieldName: "file",
            headers: headers,
            boundary: multipartBoundary(idempotencyKey)
        )
    }

    private func routeUpload(
        _ operation: PendingOperation,
        headers: [String: String],
        idempotencyKey: SyncIdempotencyKey
    ) throws -> PreparedSyncRequest {
        let hikeID = try requiredParentID(operation)
        let payload = try object(operation.payload)
        let upload = try fileStore.upload(
            for: operation,
            defaultFileName: "route.tcx",
            defaultContentType: "application/vnd.garmin.tcx+xml"
        )
        var fields: [MultipartField] = []
        let sourceType = nonemptyString(payload["source_type"]) ?? "hikejournal_ios_gps"
        guard sourceType == "hikejournal_ios_gps" else {
            throw validation("An iPhone route must use the hikejournal_ios_gps source type.")
        }
        fields.append(MultipartField(name: "source_type", value: sourceType))
        let tcxUpload = AccountSyncFileStore.Upload(
            data: upload.data,
            fileName: upload.fileName,
            contentType: "application/vnd.garmin.tcx+xml"
        )
        return multipartRequest(
            path: "/v1/hikes/\(try pathSegment(hikeID))/route",
            fields: fields,
            upload: tcxUpload,
            fileFieldName: "file",
            headers: headers,
            boundary: multipartBoundary(idempotencyKey)
        )
    }

    private func multipartRequest(
        path: String,
        fields: [MultipartField],
        upload: AccountSyncFileStore.Upload,
        fileFieldName: String,
        headers: [String: String],
        boundary: String
    ) -> PreparedSyncRequest {
        let body = MultipartFormDataEncoder(boundary: boundary).encode(
            fields: fields,
            fileFieldName: fileFieldName,
            upload: upload
        )
        return request(
            .post,
            path,
            body: body,
            headers: headers.merging([
                "Content-Type": "multipart/form-data; boundary=\(boundary)"
            ]) { current, _ in current },
            timeoutInterval: SyncAPIAdapterConstants.uploadTimeout
        )
    }

    private func jsonRequest(
        _ method: HTTPMethod,
        _ path: String,
        _ object: [String: Any],
        headers: [String: String]
    ) throws -> PreparedSyncRequest {
        let data: Data
        do {
            data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        } catch {
            throw validation("A queued sync payload contains unsupported JSON values.")
        }
        return request(method, path, body: data, headers: headers)
    }

    private func request(
        _ method: HTTPMethod,
        _ path: String,
        body: Data? = nil,
        headers: [String: String],
        timeoutInterval: TimeInterval = 30
    ) -> PreparedSyncRequest {
        PreparedSyncRequest(
            method: method,
            path: path,
            body: body,
            headers: headers,
            timeoutInterval: timeoutInterval,
            maximumResponseBytes: SyncAPIAdapterConstants.maximumResponseBytes
        )
    }

    private func object(_ data: Data) throws -> [String: Any] {
        do {
            guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw validation("A queued sync payload is not a JSON object.")
            }
            return object
        } catch let failure as SyncExecutionFailure {
            throw failure
        } catch {
            throw validation("A queued sync payload could not be read.")
        }
    }

    private func requiredParentID(_ operation: PendingOperation) throws -> String {
        guard let parentID = operation.parentID?.trimmingCharacters(
            in: .whitespacesAndNewlines
        ), !parentID.isEmpty else {
            throw validation("This queued operation is missing its parent hike.")
        }
        return parentID
    }

    private func requiredString(_ value: Any?, name: String) throws -> String {
        guard let value = value as? String, !value.isEmpty else {
            throw validation("The queued \(name) is missing.")
        }
        return value
    }

    private func requiredNumber(_ value: Any?, name: String) throws -> NSNumber {
        guard let number = value as? NSNumber,
              number.doubleValue.isFinite else {
            throw validation("The queued \(name) is invalid.")
        }
        return number
    }

    private func string(_ value: Any?, default fallback: String) -> String {
        value as? String ?? fallback
    }

    private func nonemptyString(_ value: Any?) -> String? {
        guard let string = value as? String else { return nil }
        let clean = string.trimmingCharacters(in: .whitespacesAndNewlines)
        return clean.isEmpty || clean.caseInsensitiveCompare("null") == .orderedSame
            ? nil
            : clean
    }

    private func stringOrNull(_ value: Any?) -> Any {
        nonemptyString(value) ?? NSNull()
    }

    private func numberOrNull(_ value: Any?) -> Any {
        guard let number = value as? NSNumber,
              number.doubleValue.isFinite else { return NSNull() }
        return number
    }

    private func boolean(_ value: Any?, default fallback: Bool) -> Bool {
        value as? Bool ?? fallback
    }

    private func formNumber(_ value: Any?) -> String? {
        guard let number = value as? NSNumber,
              number.doubleValue.isFinite else { return nil }
        return number.stringValue
    }

    private func pathSegment(_ value: String) throws -> String {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, trimmed.utf8.count <= 256 else {
            throw validation("A queued server identifier is invalid.")
        }
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-._~"))
        guard let encoded = trimmed.addingPercentEncoding(withAllowedCharacters: allowed) else {
            throw validation("A queued server identifier could not be encoded safely.")
        }
        return encoded
    }

    private func multipartBoundary(_ key: SyncIdempotencyKey) -> String {
        let safe = key.rawValue.unicodeScalars.map { scalar -> Character in
            CharacterSet.alphanumerics.contains(scalar) ? Character(String(scalar)) : "-"
        }
        return "HikeJournal-" + String(safe.prefix(48))
    }

    private func safeIdempotencyValue(_ value: String) throws -> String {
        guard !value.isEmpty,
              value.utf8.count <= 160,
              value.unicodeScalars.allSatisfy({ scalar in
                  CharacterSet.alphanumerics
                      .union(CharacterSet(charactersIn: "-._:"))
                      .contains(scalar)
              }) else {
            throw validation("A queued operation has an invalid idempotency identifier.")
        }
        return value
    }

    private func inferredMediaType(fileName: String?) -> String {
        switch (fileName ?? "").lowercased().split(separator: ".").last {
        case "jpg", "jpeg": return "image/jpeg"
        case "png": return "image/png"
        case "heic": return "image/heic"
        case "heif": return "image/heif"
        case "webp": return "image/webp"
        case "gif": return "image/gif"
        case "mp4": return "video/mp4"
        case "mov": return "video/quicktime"
        case "m4v": return "video/x-m4v"
        case "3gp": return "video/3gpp"
        case "webm": return "video/webm"
        default: return "image/jpeg"
        }
    }

    private func validation(_ message: String) -> SyncExecutionFailure {
        .validation(message: message)
    }
}

actor SyncOperationAPIAdapter {
    private let apiClient: APIClient
    private let builder: SyncOperationRequestBuilder
    private let connectivity: SyncConnectivityProvider

    init(
        apiClient: APIClient,
        fileStore: AccountSyncFileStore,
        connectivity: SyncConnectivityProvider
    ) {
        self.apiClient = apiClient
        builder = SyncOperationRequestBuilder(fileStore: fileStore)
        self.connectivity = connectivity
    }

    nonisolated func executor() -> SyncOperationExecutor {
        SyncOperationExecutor { [weak self] operation, key in
            guard let self else {
                throw SyncExecutionFailure.retryableServer(
                    message: "The sync transport is no longer available."
                )
            }
            return try await self.execute(operation, idempotencyKey: key)
        }
    }

    private func execute(
        _ operation: PendingOperation,
        idempotencyKey: SyncIdempotencyKey
    ) async throws -> SyncOperationAcknowledgement {
        do {
            let prepared = try builder.prepare(
                operation: operation,
                idempotencyKey: idempotencyKey
            )
            let _: DiscardedSyncResponse = try await apiClient.send(
                APIRequest(
                    method: prepared.method,
                    path: prepared.path,
                    body: prepared.body,
                    authentication: .required,
                    headers: prepared.headers,
                    timeoutInterval: prepared.timeoutInterval,
                    maximumResponseBytes: prepared.maximumResponseBytes
                )
            )
            return .acknowledged
        } catch is CancellationError {
            throw CancellationError()
        } catch let failure as SyncExecutionFailure {
            throw failure
        } catch let error as APIClientError {
            throw await classify(error)
        } catch {
            throw SyncExecutionFailure.classify(error)
        }
    }

    private func classify(_ error: APIClientError) async -> SyncExecutionFailure {
        switch error {
        case .sessionRequired, .authenticationExpired:
            return .authenticationRequired(message: error.localizedDescription)

        case let .server(statusCode, message, _):
            if statusCode == 401 {
                return .authenticationRequired(message: message)
            }
            if isQuotaFailure(statusCode: statusCode, message: message) {
                return .quotaExceeded(resource: quotaResource(message), message: message)
            }
            if statusCode == 408 || statusCode == 425 || statusCode == 429
                || (500...599).contains(statusCode) {
                return .retryableServer(statusCode: statusCode, message: message)
            }
            if [400, 409, 413, 422].contains(statusCode) {
                return .validation(message: message)
            }
            return .permanentServer(statusCode: statusCode, message: message)

        case .transport:
            if await connectivity.status() == .unavailable {
                return .offline(message: error.localizedDescription)
            }
            return .retryableServer(message: error.localizedDescription)

        case .requestEncodingFailed, .invalidRequestPath:
            return .validation(message: error.localizedDescription)

        case .missingBaseURL:
            return .permanentServer(message: error.localizedDescription)

        case .responseDecodingFailed, .responseTooLarge, .nonHTTPResponse:
            return .retryableServer(message: error.localizedDescription)
        }
    }

    private func isQuotaFailure(statusCode: Int, message: String) -> Bool {
        if statusCode == 402 { return true }
        let lower = message.lowercased()
        return lower.contains("quota")
            || lower.contains("cloud limit")
            || lower.contains("storage limit")
            || lower.contains("plan limit")
    }

    private func quotaResource(_ message: String) -> String? {
        let lower = message.lowercased()
        if lower.contains("photo") || lower.contains("video") || lower.contains("media") {
            return "media"
        }
        if lower.contains("hike") || lower.contains("journal") {
            return "hikes"
        }
        return nil
    }
}

private struct MultipartField: Sendable {
    let name: String
    let value: String
}

private struct MultipartFormDataEncoder: Sendable {
    let boundary: String

    func encode(
        fields: [MultipartField],
        fileFieldName: String,
        upload: AccountSyncFileStore.Upload
    ) -> Data {
        var data = Data()
        for field in fields {
            append("--\(boundary)\r\n", to: &data)
            append(
                "Content-Disposition: form-data; name=\"\(quoted(field.name))\"\r\n\r\n",
                to: &data
            )
            append(field.value, to: &data)
            append("\r\n", to: &data)
        }
        append("--\(boundary)\r\n", to: &data)
        append(
            "Content-Disposition: form-data; name=\"\(quoted(fileFieldName))\"; filename=\"\(quoted(upload.fileName))\"\r\n",
            to: &data
        )
        append("Content-Type: \(upload.contentType)\r\n\r\n", to: &data)
        data.append(upload.data)
        append("\r\n--\(boundary)--\r\n", to: &data)
        return data
    }

    private func append(_ value: String, to data: inout Data) {
        data.append(Data(value.utf8))
    }

    private func quoted(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\r", with: "_")
            .replacingOccurrences(of: "\n", with: "_")
    }
}

private struct DiscardedSyncResponse: Decodable, Sendable {
    init(from decoder: Decoder) throws {}
}
