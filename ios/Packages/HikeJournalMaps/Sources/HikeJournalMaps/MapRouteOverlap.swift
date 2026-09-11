import Foundation

struct MapRouteOverlapSegment: Sendable {
  let coordinates: [GeoCoordinate]
  let overlapsTrail: Bool
}

enum MapRouteOverlapClassifier {
  private static let earthRadiusMeters = 6_378_137.0
  private static let gridCellMeters = 120.0
  // A centerline can be displaced by normal GPS error, but a wider radius
  // incorrectly labels parallel paths and trail-side roads as shared.
  private static let overlapDistanceMeters = 24.0
  private static let minimumDirectionSimilarity = 0.88
  private static let minimumSegmentMeters = 0.5
  private static let maxRouteChunkMeters = 20.0
  private static let maxChunksPerEdge = 5_000

  static func classify(
    routes: [RecordedRoute],
    trailGeoJSON: [Data]
  ) -> [MapRouteOverlapSegment] {
    let trailRoutes = trailGeoJSON.flatMap(trailLines)
    let index = SegmentIndex(routes: trailRoutes)
    return routes.flatMap { route in
      route.segments.flatMap { segment in
        classifyRoute(segment.coordinates, segmentIndex: index)
      }
    }
  }

  static func geoJSONData(
    for segments: [MapRouteOverlapSegment],
    overlapsTrail: Bool
  ) throws -> Data? {
    let coordinates = segments
      .filter { $0.overlapsTrail == overlapsTrail }
      .map { segment in
        segment.coordinates.map { [$0.longitude, $0.latitude] }
      }
    guard !coordinates.isEmpty else { return nil }
    return try JSONSerialization.data(
      withJSONObject: ["type": "MultiLineString", "coordinates": coordinates]
    )
  }

  private static func trailLines(from data: Data) -> [[GeoCoordinate]] {
    guard
      let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
      let features = object["features"] as? [[String: Any]]
    else { return [] }

    return features.flatMap { feature -> [[GeoCoordinate]] in
      guard let geometry = feature["geometry"] as? [String: Any],
        let type = geometry["type"] as? String
      else { return [] }
      switch type {
      case "LineString":
        guard let values = geometry["coordinates"] as? [[Any]] else { return [] }
        return [coordinates(values)]
      case "MultiLineString":
        guard let values = geometry["coordinates"] as? [[[Any]]] else { return [] }
        return values.map(coordinates)
      default:
        return []
      }
    }.filter { $0.count >= 2 }
  }

  private static func coordinates(_ values: [[Any]]) -> [GeoCoordinate] {
    values.compactMap { pair in
      guard pair.count >= 2,
        let longitude = pair[0] as? NSNumber,
        let latitude = pair[1] as? NSNumber
      else { return nil }
      return try? GeoCoordinate(latitude: latitude.doubleValue, longitude: longitude.doubleValue)
    }
  }

  private static func classifyRoute(
    _ route: [GeoCoordinate],
    segmentIndex: SegmentIndex
  ) -> [MapRouteOverlapSegment] {
    guard route.count >= 2 else { return [] }
    var result: [MapRouteOverlapSegment] = []
    var currentOverlap: Bool?
    var currentCoordinates: [GeoCoordinate] = []

    for (start, end) in zip(route, route.dropFirst()) {
      let projectedStart = ProjectedPoint(coordinate: start)
      let projectedEnd = ProjectedPoint(coordinate: end)
      let distance = hypot(
        projectedEnd.x - projectedStart.x,
        projectedEnd.y - projectedStart.y
      )
      let chunks = min(
        max(1, Int(ceil(distance / maxRouteChunkMeters))),
        maxChunksPerEdge
      )
      for chunkIndex in 0..<chunks {
        let from = interpolate(start, end, amount: Double(chunkIndex) / Double(chunks))
        let to = interpolate(start, end, amount: Double(chunkIndex + 1) / Double(chunks))
        let overlaps = segmentIndex.overlaps(start: from, end: to)
        if currentOverlap == nil {
          currentOverlap = overlaps
          currentCoordinates = [from]
        } else if currentOverlap != overlaps {
          if currentCoordinates.count >= 2 {
            result.append(
              MapRouteOverlapSegment(
                coordinates: currentCoordinates,
                overlapsTrail: currentOverlap == true
              )
            )
          }
          currentOverlap = overlaps
          currentCoordinates = [from]
        }
        if currentCoordinates.last != to { currentCoordinates.append(to) }
      }
    }
    if currentCoordinates.count >= 2, let currentOverlap {
      result.append(
        MapRouteOverlapSegment(
          coordinates: currentCoordinates,
          overlapsTrail: currentOverlap
        )
      )
    }
    return result
  }

  private struct Cell: Hashable {
    let x: Int
    let y: Int
  }

  private struct ProjectedPoint {
    let x: Double
    let y: Double

    init(coordinate: GeoCoordinate) {
      let latitude = min(85.0, max(-85.0, coordinate.latitude)) * .pi / 180
      x = earthRadiusMeters * coordinate.longitude * .pi / 180
      y = earthRadiusMeters * log(tan(.pi / 4 + latitude / 2))
    }
  }

  private struct ProjectedSegment {
    let start: ProjectedPoint
    let end: ProjectedPoint

    var deltaX: Double { end.x - start.x }
    var deltaY: Double { end.y - start.y }
    var length: Double { hypot(deltaX, deltaY) }

    func directionSimilarity(_ other: ProjectedSegment) -> Double {
      guard length >= minimumSegmentMeters, other.length >= minimumSegmentMeters else { return 0 }
      return abs(deltaX * other.deltaX + deltaY * other.deltaY) / (length * other.length)
    }

    func distance(to point: ProjectedPoint) -> Double {
      let lengthSquared = deltaX * deltaX + deltaY * deltaY
      guard lengthSquared > 0 else {
        return hypot(point.x - start.x, point.y - start.y)
      }
      let projection = (
        (point.x - start.x) * deltaX + (point.y - start.y) * deltaY
      ) / lengthSquared
      let amount = min(1, max(0, projection))
      return hypot(
        point.x - (start.x + amount * deltaX),
        point.y - (start.y + amount * deltaY)
      )
    }

    func distance(to other: ProjectedSegment) -> Double {
      min(
        min(distance(to: other.start), distance(to: other.end)),
        min(other.distance(to: start), other.distance(to: end))
      )
    }
  }

  private struct SegmentIndex {
    private var cells: [Cell: [ProjectedSegment]] = [:]

    init(routes: [[GeoCoordinate]]) {
      for route in routes {
        for (start, end) in zip(route, route.dropFirst()) {
          let segment = ProjectedSegment(
            start: ProjectedPoint(coordinate: start),
            end: ProjectedPoint(coordinate: end)
          )
          guard segment.length >= minimumSegmentMeters else { continue }
          let minX = cellCoordinate(min(segment.start.x, segment.end.x) - overlapDistanceMeters)
          let maxX = cellCoordinate(max(segment.start.x, segment.end.x) + overlapDistanceMeters)
          let minY = cellCoordinate(min(segment.start.y, segment.end.y) - overlapDistanceMeters)
          let maxY = cellCoordinate(max(segment.start.y, segment.end.y) + overlapDistanceMeters)
          for x in minX...maxX {
            for y in minY...maxY {
              cells[Cell(x: x, y: y), default: []].append(segment)
            }
          }
        }
      }
    }

    func overlaps(start: GeoCoordinate, end: GeoCoordinate) -> Bool {
      let userSegment = ProjectedSegment(
        start: ProjectedPoint(coordinate: start),
        end: ProjectedPoint(coordinate: end)
      )
      guard userSegment.length >= minimumSegmentMeters else { return false }
      let minX = cellCoordinate(min(userSegment.start.x, userSegment.end.x) - overlapDistanceMeters)
      let maxX = cellCoordinate(max(userSegment.start.x, userSegment.end.x) + overlapDistanceMeters)
      let minY = cellCoordinate(min(userSegment.start.y, userSegment.end.y) - overlapDistanceMeters)
      let maxY = cellCoordinate(max(userSegment.start.y, userSegment.end.y) + overlapDistanceMeters)
      for x in minX...maxX {
        for y in minY...maxY {
          for trailSegment in cells[Cell(x: x, y: y), default: []]
          where userSegment.directionSimilarity(trailSegment) >= minimumDirectionSimilarity
            && userSegment.distance(to: trailSegment) <= overlapDistanceMeters {
            return true
          }
        }
      }
      return false
    }

    private func cellCoordinate(_ value: Double) -> Int {
      Int(floor(value / gridCellMeters))
    }
  }

  private static func interpolate(
    _ start: GeoCoordinate,
    _ end: GeoCoordinate,
    amount: Double
  ) -> GeoCoordinate {
    try! GeoCoordinate(
      latitude: start.latitude + (end.latitude - start.latitude) * amount,
      longitude: start.longitude + (end.longitude - start.longitude) * amount
    )
  }
}
