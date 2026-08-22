import Foundation

public enum MapDomainError: Error, Equatable, Sendable {
  case invalidCoordinate(latitude: Double, longitude: Double)
  case routeSegmentTooShort
  case emptyIdentifier
  case invalidAccuracy
  case invalidStyleURL
  case invalidAttribution
  case invalidTokenQueryItem
  case missingStyleCredential
  case unexpectedStyleCredential
  case invalidStyleCredential
}

extension MapDomainError: LocalizedError {
  public var errorDescription: String? {
    switch self {
    case .invalidCoordinate:
      return "Map coordinates must contain finite latitude and longitude values in range."
    case .routeSegmentTooShort:
      return "A recorded route segment requires at least two coordinates."
    case .emptyIdentifier:
      return "Map identifiers must not be empty."
    case .invalidAccuracy:
      return "Location accuracy must be finite and nonnegative."
    case .invalidStyleURL:
      return "The map style must use an absolute HTTPS URL without embedded credentials."
    case .invalidAttribution:
      return "Map attribution requires a title and an absolute HTTPS URL."
    case .invalidTokenQueryItem:
      return "The style token query-item name is not valid."
    case .missingStyleCredential:
      return "This map style requires a runtime credential."
    case .unexpectedStyleCredential:
      return "A credential was supplied to a style that does not accept one."
    case .invalidStyleCredential:
      return "The runtime map style credential is not valid."
    }
  }
}

public struct GeoCoordinate: Codable, Equatable, Hashable, Sendable {
  public let latitude: Double
  public let longitude: Double

  public init(latitude: Double, longitude: Double) throws {
    guard latitude.isFinite, longitude.isFinite,
      (-90.0...90.0).contains(latitude),
      (-180.0...180.0).contains(longitude)
    else {
      throw MapDomainError.invalidCoordinate(latitude: latitude, longitude: longitude)
    }
    self.latitude = latitude
    self.longitude = longitude
  }

  private enum CodingKeys: String, CodingKey {
    case latitude
    case longitude
  }

  public init(from decoder: Decoder) throws {
    let values = try decoder.container(keyedBy: CodingKeys.self)
    try self.init(
      latitude: values.decode(Double.self, forKey: .latitude),
      longitude: values.decode(Double.self, forKey: .longitude)
    )
  }
}

public struct RecordedRouteSegment: Codable, Equatable, Sendable {
  public let id: String
  public let coordinates: [GeoCoordinate]

  public init(id: String, coordinates: [GeoCoordinate]) throws {
    guard !id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
      throw MapDomainError.emptyIdentifier
    }
    guard coordinates.count >= 2 else {
      throw MapDomainError.routeSegmentTooShort
    }
    self.id = id
    self.coordinates = coordinates
  }

  private enum CodingKeys: String, CodingKey {
    case id
    case coordinates
  }

  public init(from decoder: Decoder) throws {
    let values = try decoder.container(keyedBy: CodingKeys.self)
    try self.init(
      id: values.decode(String.self, forKey: .id),
      coordinates: values.decode([GeoCoordinate].self, forKey: .coordinates)
    )
  }
}

public struct RecordedRoute: Codable, Equatable, Sendable {
  public let id: String
  public let name: String
  public let segments: [RecordedRouteSegment]

  public init(id: String, name: String, segments: [RecordedRouteSegment]) throws {
    guard !id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
      throw MapDomainError.emptyIdentifier
    }
    self.id = id
    self.name = name
    self.segments = segments
  }

  private enum CodingKeys: String, CodingKey {
    case id
    case name
    case segments
  }

  public init(from decoder: Decoder) throws {
    let values = try decoder.container(keyedBy: CodingKeys.self)
    try self.init(
      id: values.decode(String.self, forKey: .id),
      name: values.decode(String.self, forKey: .name),
      segments: values.decode([RecordedRouteSegment].self, forKey: .segments)
    )
  }
}

public struct MapCurrentLocation: Codable, Equatable, Sendable {
  public let coordinate: GeoCoordinate
  public let horizontalAccuracyMeters: Double
  public let recordedAt: Date

  public init(
    coordinate: GeoCoordinate,
    horizontalAccuracyMeters: Double,
    recordedAt: Date
  ) throws {
    guard horizontalAccuracyMeters.isFinite, horizontalAccuracyMeters >= 0 else {
      throw MapDomainError.invalidAccuracy
    }
    self.coordinate = coordinate
    self.horizontalAccuracyMeters = horizontalAccuracyMeters
    self.recordedAt = recordedAt
  }

  private enum CodingKeys: String, CodingKey {
    case coordinate
    case horizontalAccuracyMeters
    case recordedAt
  }

  public init(from decoder: Decoder) throws {
    let values = try decoder.container(keyedBy: CodingKeys.self)
    try self.init(
      coordinate: values.decode(GeoCoordinate.self, forKey: .coordinate),
      horizontalAccuracyMeters: values.decode(Double.self, forKey: .horizontalAccuracyMeters),
      recordedAt: values.decode(Date.self, forKey: .recordedAt)
    )
  }
}

public enum MapPointKind: String, Codable, CaseIterable, Sendable {
  case geotaggedPhoto
  case geotaggedVideo
  case fieldMark
  case sighting
  case discovery
  case place

  public var accessibilityName: String {
    switch self {
    case .geotaggedPhoto: return "Photo"
    case .geotaggedVideo: return "Video"
    case .fieldMark: return "Field mark"
    case .sighting: return "Sighting"
    case .discovery: return "Discovery"
    case .place: return "Place"
    }
  }
}

public struct MapPoint: Codable, Equatable, Sendable, Identifiable {
  public let id: String
  public let kind: MapPointKind
  public let title: String
  public let detail: String?
  public let coordinate: GeoCoordinate

  public init(
    id: String,
    kind: MapPointKind,
    title: String,
    detail: String? = nil,
    coordinate: GeoCoordinate
  ) throws {
    guard !id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
      throw MapDomainError.emptyIdentifier
    }
    self.id = id
    self.kind = kind
    self.title = title
    self.detail = detail
    self.coordinate = coordinate
  }

  private enum CodingKeys: String, CodingKey {
    case id
    case kind
    case title
    case detail
    case coordinate
  }

  public init(from decoder: Decoder) throws {
    let values = try decoder.container(keyedBy: CodingKeys.self)
    try self.init(
      id: values.decode(String.self, forKey: .id),
      kind: values.decode(MapPointKind.self, forKey: .kind),
      title: values.decode(String.self, forKey: .title),
      detail: values.decodeIfPresent(String.self, forKey: .detail),
      coordinate: values.decode(GeoCoordinate.self, forKey: .coordinate)
    )
  }

  public var accessibilityLabel: String {
    let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
    return trimmedTitle.isEmpty
      ? kind.accessibilityName
      : "\(kind.accessibilityName): \(trimmedTitle)"
  }
}

public struct MapScene: Codable, Equatable, Sendable {
  public var routes: [RecordedRoute]
  public var currentLocation: MapCurrentLocation?
  public var points: [MapPoint]
  public var selectedTrailOverlayIDs: Set<String>

  public init(
    routes: [RecordedRoute] = [],
    currentLocation: MapCurrentLocation? = nil,
    points: [MapPoint] = [],
    selectedTrailOverlayIDs: Set<String> = []
  ) {
    self.routes = routes
    self.currentLocation = currentLocation
    self.points = points
    self.selectedTrailOverlayIDs = selectedTrailOverlayIDs
  }

  public var allCoordinates: [GeoCoordinate] {
    routes.flatMap(\.segments).flatMap(\.coordinates)
      + points.map(\.coordinate)
      + [currentLocation?.coordinate].compactMap { $0 }
  }

  public func points(of kind: MapPointKind) -> [MapPoint] {
    points.filter { $0.kind == kind }
  }
}

public struct MapAttribution: Codable, Equatable, Hashable, Sendable, Identifiable {
  public let id: String
  public let title: String
  public let url: URL

  public init(id: String, title: String, url: URL) throws {
    guard !id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
      throw MapDomainError.emptyIdentifier
    }
    guard !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
      url.scheme?.lowercased() == "https",
      url.host != nil
    else {
      throw MapDomainError.invalidAttribution
    }
    self.id = id
    self.title = title
    self.url = url
  }

  private enum CodingKeys: String, CodingKey {
    case id
    case title
    case url
  }

  public init(from decoder: Decoder) throws {
    let values = try decoder.container(keyedBy: CodingKeys.self)
    try self.init(
      id: values.decode(String.self, forKey: .id),
      title: values.decode(String.self, forKey: .title),
      url: values.decode(URL.self, forKey: .url)
    )
  }
}

public struct MapStyleCredential: Equatable, Sendable {
  fileprivate let value: String

  public init(_ value: String) throws {
    guard !value.isEmpty, value.count <= 4_096,
      value.unicodeScalars.allSatisfy({
        !CharacterSet.whitespacesAndNewlines.contains($0)
          && !CharacterSet.controlCharacters.contains($0)
      })
    else {
      throw MapDomainError.invalidStyleCredential
    }
    self.value = value
  }
}

public struct MapStyleConfiguration: Codable, Equatable, Sendable {
  public let id: String
  public let styleURL: URL
  public let attribution: MapAttribution
  public let tokenQueryItemName: String?

  public init(
    id: String,
    styleURL: URL,
    attribution: MapAttribution,
    tokenQueryItemName: String? = nil
  ) throws {
    guard !id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
      throw MapDomainError.emptyIdentifier
    }
    guard styleURL.absoluteString.count <= 2_048,
      styleURL.scheme?.lowercased() == "https",
      styleURL.host != nil,
      styleURL.user == nil,
      styleURL.password == nil,
      styleURL.fragment == nil
    else {
      throw MapDomainError.invalidStyleURL
    }
    if let tokenQueryItemName {
      let scalars = tokenQueryItemName.unicodeScalars
      let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_."))
      guard !tokenQueryItemName.isEmpty, tokenQueryItemName.count <= 64,
        scalars.allSatisfy(allowed.contains),
        !Self.queryNames(in: styleURL).contains(tokenQueryItemName)
      else {
        throw MapDomainError.invalidTokenQueryItem
      }
    }
    self.id = id
    self.styleURL = styleURL
    self.attribution = attribution
    self.tokenQueryItemName = tokenQueryItemName
  }

  private enum CodingKeys: String, CodingKey {
    case id
    case styleURL
    case attribution
    case tokenQueryItemName
  }

  public init(from decoder: Decoder) throws {
    let values = try decoder.container(keyedBy: CodingKeys.self)
    try self.init(
      id: values.decode(String.self, forKey: .id),
      styleURL: values.decode(URL.self, forKey: .styleURL),
      attribution: values.decode(MapAttribution.self, forKey: .attribution),
      tokenQueryItemName: values.decodeIfPresent(String.self, forKey: .tokenQueryItemName)
    )
  }

  public func resolvedURL(credential: MapStyleCredential? = nil) throws -> URL {
    switch (tokenQueryItemName, credential) {
    case (nil, nil):
      return styleURL
    case (nil, .some):
      throw MapDomainError.unexpectedStyleCredential
    case (.some, nil):
      throw MapDomainError.missingStyleCredential
    case (.some(let name), .some(let credential)):
      guard var components = URLComponents(url: styleURL, resolvingAgainstBaseURL: false) else {
        throw MapDomainError.invalidStyleURL
      }
      var items = components.queryItems ?? []
      items.append(URLQueryItem(name: name, value: credential.value))
      components.queryItems = items
      guard let result = components.url else {
        throw MapDomainError.invalidStyleURL
      }
      return result
    }
  }

  private static func queryNames(in url: URL) -> Set<String> {
    Set(URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?.map(\.name) ?? [])
  }
}
