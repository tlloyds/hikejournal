import Foundation

public let GROUPED_ID_MAX_PHOTOS = 8
public let REVIEW_BATCH_MAX_GROUPS_PER_JOB = 50
public let SMART_ID_MAX_DISTANCE_METERS = 12.0
public let SMART_ID_MAX_MINUTES = 2.0

public let GROUPED_PUBLISH_MAX_PHOTOS = 8
public let PUBLISH_MAX_DISTANCE_METERS = 50.0
public let PUBLISH_MAX_MINUTES = 15.0

public struct ReviewPhotoGroup: Codable, Equatable, Sendable {
    public let items: [ReviewItem]
    public let timeSpanMinutes: Double
    public let maxDistanceMeters: Double

    public init(items: [ReviewItem], timeSpanMinutes: Double, maxDistanceMeters: Double) {
        self.items = items
        self.timeSpanMinutes = timeSpanMinutes
        self.maxDistanceMeters = maxDistanceMeters
    }

    public var photoIds: [String] { items.map(\.id) }
}

public struct PublishObservationGroup: Codable, Equatable, Sendable {
    public let items: [PublishItem]
    public let timeSpanMinutes: Double
    public let maxDistanceMeters: Double

    public init(items: [PublishItem], timeSpanMinutes: Double, maxDistanceMeters: Double) {
        self.items = items
        self.timeSpanMinutes = timeSpanMinutes
        self.maxDistanceMeters = maxDistanceMeters
    }

    public var photoIds: [String] { items.map(\.photo.id) }
    public var observationIds: [String] { items.map(\.id) }
    public var oversized: Bool { items.count > GROUPED_PUBLISH_MAX_PHOTOS }
}

/// Preserves review-plan order while respecting the companion API job limit.
public func chunkReviewBatchGroups(
    _ groups: [[String]],
    maxGroupsPerJob: Int = REVIEW_BATCH_MAX_GROUPS_PER_JOB
) -> [[[String]]] {
    precondition(maxGroupsPerJob > 0, "A review batch job must allow at least one group.")
    guard !groups.isEmpty else { return [] }
    return stride(from: 0, to: groups.count, by: maxGroupsPerJob).map { start in
        Array(groups[start..<min(start + maxGroupsPerJob, groups.count)])
    }
}

public func buildReviewPhotoGroups(
    _ items: [ReviewItem],
    maxDistanceMeters: Double = SMART_ID_MAX_DISTANCE_METERS,
    maxMinutes: Double = SMART_ID_MAX_MINUTES,
    maxPhotos: Int = GROUPED_ID_MAX_PHOTOS
) -> [ReviewPhotoGroup] {
    let partitions = orderedPartitions(items) { $0.hikeId ?? "standalone" }
    var groups: [ReviewPhotoGroup] = []

    for partition in partitions {
        var compatibleGroups: [[ReviewItem]] = []
        for item in partition.sorted(by: reviewItemOrder) {
            guard reviewInstant(item) != nil, photoCoordinates(item.photo) != nil else {
                compatibleGroups.append([item])
                continue
            }
            if let index = compatibleGroups.firstIndex(where: { group in
                group.count < maxPhotos && fitsReviewGroup(
                    item,
                    group: group,
                    maxDistanceMeters: maxDistanceMeters,
                    maxMinutes: maxMinutes
                )
            }) {
                compatibleGroups[index].append(item)
            } else {
                compatibleGroups.append([item])
            }
        }
        groups.append(contentsOf: compatibleGroups.map(summarizeReviewGroup))
    }
    return groups.sorted(by: reviewGroupOrder)
}

public func splitReviewPhotoGroups(
    _ groups: [ReviewPhotoGroup],
    separatePhotoIds: Set<String>
) -> [ReviewPhotoGroup] {
    var split: [ReviewPhotoGroup] = []
    for group in groups {
        let groupedItems = group.items.filter { !separatePhotoIds.contains($0.id) }
        let separateItems = group.items.filter { separatePhotoIds.contains($0.id) }
        if !groupedItems.isEmpty { split.append(summarizeReviewGroup(groupedItems)) }
        split.append(contentsOf: separateItems.map { summarizeReviewGroup([$0]) })
    }
    return split.sorted(by: reviewGroupOrder)
}

public func buildPublishObservationGroups(
    _ items: [PublishItem],
    maxDistanceMeters: Double = PUBLISH_MAX_DISTANCE_METERS,
    maxMinutes: Double = PUBLISH_MAX_MINUTES
) -> [PublishObservationGroup] {
    let partitions = orderedPartitions(items) { item in
        "\(item.hikeId ?? "standalone")|\(publishSpeciesKey(item))"
    }
    var groups: [PublishObservationGroup] = []

    for partition in partitions {
        var compatibleGroups: [[PublishItem]] = []
        for item in partition.sorted(by: publishItemOrder) {
            guard publishInstant(item) != nil, photoCoordinates(item.photo) != nil else {
                compatibleGroups.append([item])
                continue
            }
            if let index = compatibleGroups.firstIndex(where: { group in
                fitsPublishGroup(
                    item,
                    group: group,
                    maxDistanceMeters: maxDistanceMeters,
                    maxMinutes: maxMinutes
                )
            }) {
                compatibleGroups[index].append(item)
            } else {
                compatibleGroups.append([item])
            }
        }
        groups.append(contentsOf: compatibleGroups.map(summarizePublishGroup))
    }
    return groups.sorted(by: publishGroupOrder)
}

public func splitPublishObservationGroups(
    _ groups: [PublishObservationGroup],
    separatePhotoIds: Set<String>
) -> [PublishObservationGroup] {
    var split: [PublishObservationGroup] = []
    for group in groups {
        let groupedItems = group.items.filter { !separatePhotoIds.contains($0.photo.id) }
        let separateItems = group.items.filter { separatePhotoIds.contains($0.photo.id) }
        if !groupedItems.isEmpty { split.append(summarizePublishGroup(groupedItems)) }
        split.append(contentsOf: separateItems.map { summarizePublishGroup([$0]) })
    }
    return split.sorted(by: publishGroupOrder)
}

private func orderedPartitions<Value>(
    _ values: [Value],
    key: (Value) -> String
) -> [[Value]] {
    var keys: [String] = []
    var partitions: [String: [Value]] = [:]
    for value in values {
        let valueKey = key(value)
        if partitions[valueKey] == nil {
            keys.append(valueKey)
            partitions[valueKey] = []
        }
        partitions[valueKey]?.append(value)
    }
    return keys.compactMap { partitions[$0] }
}

private func reviewInstant(_ item: ReviewItem) -> Date? {
    observedDate(item.photo.takenAt)
}

private func publishInstant(_ item: PublishItem) -> Date? {
    observedDate(item.photo.takenAt)
}

private func reviewItemOrder(_ left: ReviewItem, _ right: ReviewItem) -> Bool {
    dateAndIDOrder(reviewInstant(left), left.id, reviewInstant(right), right.id)
}

private func publishItemOrder(_ left: PublishItem, _ right: PublishItem) -> Bool {
    dateAndIDOrder(publishInstant(left), left.id, publishInstant(right), right.id)
}

private func reviewGroupOrder(_ left: ReviewPhotoGroup, _ right: ReviewPhotoGroup) -> Bool {
    guard let leftItem = left.items.first, let rightItem = right.items.first else {
        return !left.items.isEmpty && right.items.isEmpty
    }
    return reviewItemOrder(leftItem, rightItem)
}

private func publishGroupOrder(_ left: PublishObservationGroup, _ right: PublishObservationGroup) -> Bool {
    guard let leftItem = left.items.first, let rightItem = right.items.first else {
        return !left.items.isEmpty && right.items.isEmpty
    }
    return publishItemOrder(leftItem, rightItem)
}

private func dateAndIDOrder(
    _ leftDate: Date?,
    _ leftID: String,
    _ rightDate: Date?,
    _ rightID: String
) -> Bool {
    switch (leftDate, rightDate) {
    case let (left?, right?) where left != right: return left < right
    case (_?, nil): return true
    case (nil, _?): return false
    default: return leftID < rightID
    }
}

private func fitsReviewGroup(
    _ item: ReviewItem,
    group: [ReviewItem],
    maxDistanceMeters: Double,
    maxMinutes: Double
) -> Bool {
    guard let candidateTime = reviewInstant(item) else { return false }
    let times = group.compactMap(reviewInstant)
    guard let minimum = (times + [candidateTime]).min(),
          let maximum = (times + [candidateTime]).max(),
          !times.isEmpty,
          maximum.timeIntervalSince(minimum) / 60 <= maxMinutes,
          let coordinates = photoCoordinates(item.photo) else {
        return false
    }
    return group.allSatisfy { existing in
        guard let other = photoCoordinates(existing.photo) else { return false }
        return distanceMeters(coordinates, other) <= maxDistanceMeters
    }
}

private func fitsPublishGroup(
    _ item: PublishItem,
    group: [PublishItem],
    maxDistanceMeters: Double,
    maxMinutes: Double
) -> Bool {
    guard let candidateTime = publishInstant(item) else { return false }
    let times = group.compactMap(publishInstant)
    guard let minimum = (times + [candidateTime]).min(),
          let maximum = (times + [candidateTime]).max(),
          !times.isEmpty,
          maximum.timeIntervalSince(minimum) / 60 <= maxMinutes,
          let coordinates = photoCoordinates(item.photo) else {
        return false
    }
    return group.allSatisfy { existing in
        guard let other = photoCoordinates(existing.photo) else { return false }
        return distanceMeters(coordinates, other) <= maxDistanceMeters
    }
}

private func summarizeReviewGroup(_ items: [ReviewItem]) -> ReviewPhotoGroup {
    let ordered = items.sorted(by: reviewItemOrder)
    let summary = temporalSpatialSummary(ordered.map { (reviewInstant($0), photoCoordinates($0.photo)) })
    return ReviewPhotoGroup(
        items: ordered,
        timeSpanMinutes: summary.timeSpanMinutes,
        maxDistanceMeters: summary.maxDistanceMeters
    )
}

private func summarizePublishGroup(_ items: [PublishItem]) -> PublishObservationGroup {
    let ordered = items.sorted(by: publishItemOrder)
    let summary = temporalSpatialSummary(ordered.map { (publishInstant($0), photoCoordinates($0.photo)) })
    return PublishObservationGroup(
        items: ordered,
        timeSpanMinutes: summary.timeSpanMinutes,
        maxDistanceMeters: summary.maxDistanceMeters
    )
}

private func temporalSpatialSummary(
    _ values: [(date: Date?, coordinates: (Double, Double)?)]
) -> (timeSpanMinutes: Double, maxDistanceMeters: Double) {
    let dates = values.compactMap { $0.date }
    let timeSpan: Double
    if let minimum = dates.min(), let maximum = dates.max(), dates.count > 1 {
        timeSpan = maximum.timeIntervalSince(minimum) / 60
    } else {
        timeSpan = 0
    }
    var maximumDistance = 0.0
    for leftIndex in values.indices {
        for rightIndex in values.indices where rightIndex > leftIndex {
            guard let left = values[leftIndex].coordinates,
                  let right = values[rightIndex].coordinates else { continue }
            maximumDistance = max(maximumDistance, distanceMeters(left, right))
        }
    }
    return (timeSpan, maximumDistance)
}

private func photoCoordinates(_ photo: Photo) -> (Double, Double)? {
    guard let latitude = validLatitude(photo.latitude),
          let longitude = validLongitude(photo.longitude) else { return nil }
    return (latitude, longitude)
}

private func distanceMeters(_ left: (Double, Double), _ right: (Double, Double)) -> Double {
    let earthRadiusMeters = 6_371_000.0
    let latitude1 = left.0 * .pi / 180
    let longitude1 = left.1 * .pi / 180
    let latitude2 = right.0 * .pi / 180
    let longitude2 = right.1 * .pi / 180
    let deltaLatitude = latitude2 - latitude1
    let deltaLongitude = longitude2 - longitude1
    let haversine = pow(sin(deltaLatitude / 2), 2)
        + cos(latitude1) * cos(latitude2) * pow(sin(deltaLongitude / 2), 2)
    return earthRadiusMeters * 2 * asin(sqrt(min(1, max(0, haversine))))
}

private func publishSpeciesKey(_ item: PublishItem) -> String {
    if let taxonID = item.taxonId { return "taxon:\(taxonID)" }
    if !item.scientificName.domainTrimmed.isEmpty {
        return "scientific:\(item.scientificName.domainFolded)"
    }
    if !item.commonName.domainTrimmed.isEmpty {
        return "common:\(item.commonName.domainFolded)"
    }
    return "id:\(item.id)"
}
