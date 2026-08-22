import Foundation

public struct MapCoordinateBounds: Codable, Equatable, Sendable {
  public let south: Double
  public let west: Double
  public let north: Double
  public let east: Double

  public init(south: Double, west: Double, north: Double, east: Double) throws {
    guard south.isFinite, west.isFinite, north.isFinite, east.isFinite,
      (-90.0...90.0).contains(south),
      (-90.0...90.0).contains(north),
      (-180.0...180.0).contains(west),
      (-180.0...180.0).contains(east),
      south <= north
    else {
      throw MapDomainError.invalidCoordinate(latitude: south, longitude: west)
    }
    self.south = south
    self.west = west
    self.north = north
    self.east = east
  }

  private enum CodingKeys: String, CodingKey {
    case south
    case west
    case north
    case east
  }

  public init(from decoder: Decoder) throws {
    let values = try decoder.container(keyedBy: CodingKeys.self)
    try self.init(
      south: values.decode(Double.self, forKey: .south),
      west: values.decode(Double.self, forKey: .west),
      north: values.decode(Double.self, forKey: .north),
      east: values.decode(Double.self, forKey: .east)
    )
  }

  public var crossesAntimeridian: Bool { west > east }
  public var latitudeSpan: Double { north - south }
  public var longitudeSpan: Double {
    crossesAntimeridian ? 360 - west + east : east - west
  }

  public var center: GeoCoordinate {
    let longitude = Self.normalizeLongitude(west + longitudeSpan / 2)
    // Values were validated during initialization, so this construction cannot fail.
    return try! GeoCoordinate(latitude: (south + north) / 2, longitude: longitude)
  }

  internal static func normalizeLongitude(_ longitude: Double) -> Double {
    var value = longitude.truncatingRemainder(dividingBy: 360)
    if value < -180 { value += 360 }
    if value > 180 { value -= 360 }
    return value == -0 ? 0 : value
  }
}

public struct MapCameraFit: Codable, Equatable, Sendable {
  public let bounds: MapCoordinateBounds
  public let center: GeoCoordinate
  public let latitudeSpan: Double
  public let longitudeSpan: Double

  public init(bounds: MapCoordinateBounds, minimumSpanDegrees: Double = 0.002) {
    self.bounds = bounds
    center = bounds.center
    let safeMinimum = minimumSpanDegrees.isFinite ? max(0, minimumSpanDegrees) : 0.002
    latitudeSpan = max(bounds.latitudeSpan, safeMinimum)
    longitudeSpan = max(bounds.longitudeSpan, safeMinimum)
  }
}

public enum MapCameraFitter {
  public static func fit(
    coordinates: [GeoCoordinate],
    minimumSpanDegrees: Double = 0.002
  ) -> MapCameraFit? {
    guard let first = coordinates.first else { return nil }
    let south = coordinates.reduce(first.latitude) { min($0, $1.latitude) }
    let north = coordinates.reduce(first.latitude) { max($0, $1.latitude) }
    let arc = minimalLongitudeArc(coordinates.map(\.longitude))
    guard
      let bounds = try? MapCoordinateBounds(
        south: south,
        west: arc.west,
        north: north,
        east: arc.east
      )
    else {
      return nil
    }
    return MapCameraFit(bounds: bounds, minimumSpanDegrees: minimumSpanDegrees)
  }

  private static func minimalLongitudeArc(_ longitudes: [Double]) -> (west: Double, east: Double) {
    guard longitudes.count > 1 else {
      let only = MapCoordinateBounds.normalizeLongitude(longitudes[0])
      return (only, only)
    }
    let sorted = longitudes.map { longitude -> Double in
      let normalized = MapCoordinateBounds.normalizeLongitude(longitude)
      return normalized < 0 ? normalized + 360 : normalized
    }.sorted()

    var largestGap = -Double.infinity
    var largestGapIndex = 0
    for index in sorted.indices {
      let next =
        index == sorted.index(before: sorted.endIndex)
        ? sorted[0] + 360
        : sorted[index + 1]
      let gap = next - sorted[index]
      if gap > largestGap {
        largestGap = gap
        largestGapIndex = index
      }
    }

    let startIndex = (largestGapIndex + 1) % sorted.count
    let west = MapCoordinateBounds.normalizeLongitude(sorted[startIndex])
    let east = MapCoordinateBounds.normalizeLongitude(sorted[largestGapIndex])
    return (west, east)
  }
}
