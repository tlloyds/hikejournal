import Foundation

/// Mirrors the dependency semantics of Android's FieldSync without coupling
/// selection to a particular transport or background-execution mechanism.
public enum SyncQueuePlanner {
    public static func next(
        from operations: [PendingOperation],
        prioritizedPhotoID: String? = nil
    ) -> PendingOperation? {
        let ordered = operations.sorted(by: operationOrder)
        let context = Context(operations: ordered)

        if let prioritizedPhotoID,
           let prioritized = ordered.first(where: {
               $0.kind == .uploadPhoto &&
                   $0.entityID == prioritizedPhotoID &&
                   isEligible($0, context: context)
           }) {
            return prioritized
        }

        if let selectedCoverUpload = ordered.first(where: {
            $0.kind == .uploadPhoto &&
                context.selectedCoverPhotoIDs.contains($0.entityID) &&
                isEligible($0, context: context)
        }) {
            return selectedCoverUpload
        }

        if let cover = ordered.first(where: {
            $0.kind == .setHikeCover && isEligible($0, context: context)
        }) {
            return cover
        }

        return ordered.first(where: { isEligible($0, context: context) })
    }

    public static func nextBatch(
        from operations: [PendingOperation],
        prioritizedPhotoID: String? = nil,
        maximumParallelPhotoUploads: Int = 2
    ) -> [PendingOperation] {
        guard let first = next(from: operations, prioritizedPhotoID: prioritizedPhotoID) else {
            return []
        }
        guard first.kind == .uploadPhoto, maximumParallelPhotoUploads > 1 else {
            return [first]
        }

        let ordered = operations.sorted(by: operationOrder)
        let context = Context(operations: ordered)
        guard !context.selectedCoverPhotoIDs.contains(first.entityID) else {
            return [first]
        }

        let additional = ordered.lazy.filter { operation in
            operation.id != first.id &&
                operation.kind == .uploadPhoto &&
                !context.selectedCoverPhotoIDs.contains(operation.entityID) &&
                isEligible(operation, context: context)
        }.prefix(maximumParallelPhotoUploads - 1)
        return [first] + Array(additional)
    }

    private struct Context {
        let deletingHikeIDs: Set<String>
        let pendingCreateHikeIDs: Set<String>
        let pendingPhotoIDs: Set<String>
        let selectedCoverPhotoIDs: Set<String>

        init(operations: [PendingOperation]) {
            deletingHikeIDs = Set(
                operations.filter { $0.kind == .deleteHike }.map(\.entityID)
            )
            pendingCreateHikeIDs = Set(
                operations.filter { $0.kind == .createHike }.map(\.entityID)
            )
            pendingPhotoIDs = Set(
                operations.filter { $0.kind == .uploadPhoto }.map(\.entityID)
            )
            selectedCoverPhotoIDs = Set(
                operations.compactMap { operation in
                    guard operation.kind == .setHikeCover,
                          operation.state == .queued || operation.state == .syncing,
                          let object = try? JSONSerialization.jsonObject(with: operation.payload) as? [String: Any],
                          let photoID = object["photo_id"] as? String,
                          !photoID.isEmpty else {
                        return nil
                    }
                    return photoID
                }
            )
        }
    }

    private static func isEligible(
        _ operation: PendingOperation,
        context: Context
    ) -> Bool {
        guard operation.state == .queued || operation.state == .syncing else {
            return false
        }

        let targetHikeID = operation.targetHikeID
        let payload = (try? JSONSerialization.jsonObject(with: operation.payload)) as? [String: Any]
        let waitsForRecordedHike = operation.kind == .createFieldMark &&
            (payload?["wait_for_hike_create"] as? Bool == true)
        let coverPhotoID = operation.kind == .setHikeCover
            ? payload?["photo_id"] as? String
            : nil
        let waitsForCoverPhoto = coverPhotoID.map(context.pendingPhotoIDs.contains) == true

        if waitsForRecordedHike,
           targetHikeID.map(context.pendingCreateHikeIDs.contains) != true {
            return false
        }
        if waitsForCoverPhoto {
            return false
        }
        if operation.kind != .deleteHike,
           targetHikeID.map(context.deletingHikeIDs.contains) == true {
            return false
        }
        if operation.kind != .createHike,
           operation.kind != .deleteHike,
           targetHikeID.map(context.pendingCreateHikeIDs.contains) == true {
            return false
        }
        return true
    }

    private static func operationOrder(_ left: PendingOperation, _ right: PendingOperation) -> Bool {
        if left.createdAt != right.createdAt {
            return left.createdAt < right.createdAt
        }
        return left.id < right.id
    }
}
