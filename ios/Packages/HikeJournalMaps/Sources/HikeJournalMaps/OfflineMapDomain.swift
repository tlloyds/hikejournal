import Foundation

public enum OfflineMapError: Error, Equatable, Sendable {
  case invalidName
  case invalidBounds
  case latitudeOutsideWebMercator
  case regionTooLarge
  case invalidZoomRange
  case estimatedTileLimitExceeded(estimated: UInt64, maximum: UInt64)
  case networkPolicyMismatch
  case duplicatePack
  case packNotFound
  case corruptContext
  case contextTooLarge
  case storageUnavailable
  case sdkFailure(String)
}

extension OfflineMapError: LocalizedError {
  public var errorDescription: String? {
    switch self {
    case .invalidName: return "Offline map names must contain 1 to 100 characters."
    case .invalidBounds: return "Offline map bounds must cover a nonzero area."
    case .latitudeOutsideWebMercator:
      return "Offline map bounds exceed the Web Mercator latitude limit."
    case .regionTooLarge: return "The requested offline map region is too large."
    case .invalidZoomRange: return "The requested offline zoom range is not supported."
    case .estimatedTileLimitExceeded(let estimated, let maximum):
      return "The region is estimated to need \(estimated) tiles; the limit is \(maximum)."
    case .networkPolicyMismatch:
      return "The request does not match the offline store's global network policy."
    case .duplicatePack: return "An equivalent offline map already exists."
    case .packNotFound: return "The offline map could not be found."
    case .corruptContext: return "The offline map has invalid application context."
    case .contextTooLarge: return "The offline map context is too large."
    case .storageUnavailable: return "MapLibre offline storage is not ready."
    case .sdkFailure(let message): return message
    }
  }
}

public enum OfflineNetworkPolicy: String, Codable, Equatable, Sendable {
  case anyNetwork
  case wifiOnly
}

public struct OfflineRegionValidationPolicy: Codable, Equatable, Sendable {
  public static let webMercatorLatitudeLimit = 85.051_128_78

  public var maximumLatitudeSpan: Double
  public var maximumLongitudeSpan: Double
  public var maximumZoomLevel: Double
  public var maximumZoomLevels: Double
  public var maximumEstimatedTiles: UInt64

  public init(
    maximumLatitudeSpan: Double = 12,
    maximumLongitudeSpan: Double = 20,
    maximumZoomLevel: Double = 18,
    maximumZoomLevels: Double = 8,
    maximumEstimatedTiles: UInt64 = 50_000
  ) {
    self.maximumLatitudeSpan = maximumLatitudeSpan
    self.maximumLongitudeSpan = maximumLongitudeSpan
    self.maximumZoomLevel = maximumZoomLevel
    self.maximumZoomLevels = maximumZoomLevels
    self.maximumEstimatedTiles = maximumEstimatedTiles
  }

  public static let production = OfflineRegionValidationPolicy()
}

public struct OfflineStorageEstimate: Codable, Equatable, Sendable {
  public let tileCount: UInt64
  public let lowerBoundBytes: UInt64
  public let upperBoundBytes: UInt64

  public init(tileCount: UInt64, lowerBoundBytes: UInt64, upperBoundBytes: UInt64) {
    self.tileCount = tileCount
    self.lowerBoundBytes = lowerBoundBytes
    self.upperBoundBytes = upperBoundBytes
  }

  public static func estimate(
    bounds: MapCoordinateBounds,
    minimumZoomLevel: Double,
    maximumZoomLevel: Double
  ) -> OfflineStorageEstimate {
    let minimum = max(0, Int(floor(minimumZoomLevel)))
    let maximum = max(minimum, Int(ceil(maximumZoomLevel)))
    var tileCount: UInt64 = 0
    for zoom in minimum...maximum {
      tileCount = saturatingAdd(tileCount, estimatedTiles(bounds: bounds, zoom: zoom))
    }
    // Style, sprite, and glyph resources add a baseline. Tile size varies by style.
    let lower = saturatingAdd(2_000_000, saturatingMultiply(tileCount, 20_000))
    let upper = saturatingAdd(8_000_000, saturatingMultiply(tileCount, 100_000))
    return OfflineStorageEstimate(
      tileCount: tileCount,
      lowerBoundBytes: lower,
      upperBoundBytes: upper
    )
  }

  private static func estimatedTiles(bounds: MapCoordinateBounds, zoom: Int) -> UInt64 {
    let tileAxis = pow(2, Double(zoom))
    let xTiles = max(1, ceil(bounds.longitudeSpan / 360 * tileAxis) + 1)
    let northY = mercatorY(latitude: bounds.north)
    let southY = mercatorY(latitude: bounds.south)
    let yTiles = max(1, ceil(abs(southY - northY) * tileAxis) + 1)
    guard xTiles.isFinite, yTiles.isFinite,
      xTiles < Double(UInt64.max), yTiles < Double(UInt64.max)
    else {
      return UInt64.max
    }
    return saturatingMultiply(UInt64(xTiles), UInt64(yTiles))
  }

  private static func mercatorY(latitude: Double) -> Double {
    let clamped = min(
      OfflineRegionValidationPolicy.webMercatorLatitudeLimit,
      max(-OfflineRegionValidationPolicy.webMercatorLatitudeLimit, latitude)
    )
    let radians = clamped * .pi / 180
    return (1 - asinh(tan(radians)) / .pi) / 2
  }

  private static func saturatingAdd(_ lhs: UInt64, _ rhs: UInt64) -> UInt64 {
    let (result, overflow) = lhs.addingReportingOverflow(rhs)
    return overflow ? UInt64.max : result
  }

  private static func saturatingMultiply(_ lhs: UInt64, _ rhs: UInt64) -> UInt64 {
    let (result, overflow) = lhs.multipliedReportingOverflow(by: rhs)
    return overflow ? UInt64.max : result
  }
}

public struct OfflinePackRequest: Equatable, Sendable {
  public let id: UUID
  public let name: String
  public let style: MapStyleConfiguration
  public let styleCredential: MapStyleCredential?
  public let bounds: MapCoordinateBounds
  public let minimumZoomLevel: Double
  public let maximumZoomLevel: Double
  public let networkPolicy: OfflineNetworkPolicy
  public let estimate: OfflineStorageEstimate

  public init(
    id: UUID = UUID(),
    name: String,
    style: MapStyleConfiguration,
    styleCredential: MapStyleCredential? = nil,
    bounds: MapCoordinateBounds,
    minimumZoomLevel: Double,
    maximumZoomLevel: Double,
    networkPolicy: OfflineNetworkPolicy,
    validationPolicy: OfflineRegionValidationPolicy = .production
  ) throws {
    let trimmedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
    guard (1...100).contains(trimmedName.count) else {
      throw OfflineMapError.invalidName
    }
    guard bounds.south < bounds.north, bounds.longitudeSpan > 0 else {
      throw OfflineMapError.invalidBounds
    }
    guard bounds.south >= -OfflineRegionValidationPolicy.webMercatorLatitudeLimit,
      bounds.north <= OfflineRegionValidationPolicy.webMercatorLatitudeLimit
    else {
      throw OfflineMapError.latitudeOutsideWebMercator
    }
    guard bounds.latitudeSpan <= validationPolicy.maximumLatitudeSpan,
      bounds.longitudeSpan <= validationPolicy.maximumLongitudeSpan
    else {
      throw OfflineMapError.regionTooLarge
    }
    guard minimumZoomLevel.isFinite, maximumZoomLevel.isFinite,
      minimumZoomLevel >= 0,
      maximumZoomLevel >= minimumZoomLevel,
      maximumZoomLevel <= validationPolicy.maximumZoomLevel,
      maximumZoomLevel - minimumZoomLevel <= validationPolicy.maximumZoomLevels
    else {
      throw OfflineMapError.invalidZoomRange
    }
    _ = try style.resolvedURL(credential: styleCredential)
    let estimate = OfflineStorageEstimate.estimate(
      bounds: bounds,
      minimumZoomLevel: minimumZoomLevel,
      maximumZoomLevel: maximumZoomLevel
    )
    guard estimate.tileCount <= validationPolicy.maximumEstimatedTiles else {
      throw OfflineMapError.estimatedTileLimitExceeded(
        estimated: estimate.tileCount,
        maximum: validationPolicy.maximumEstimatedTiles
      )
    }
    self.id = id
    self.name = trimmedName
    self.style = style
    self.styleCredential = styleCredential
    self.bounds = bounds
    self.minimumZoomLevel = minimumZoomLevel
    self.maximumZoomLevel = maximumZoomLevel
    self.networkPolicy = networkPolicy
    self.estimate = estimate
  }

  public var regionKey: String {
    OfflinePackContext.regionKey(
      styleID: style.id,
      bounds: bounds,
      minimumZoomLevel: minimumZoomLevel,
      maximumZoomLevel: maximumZoomLevel
    )
  }
}

public struct OfflinePackContext: Codable, Equatable, Sendable, Identifiable {
  public static let currentSchemaVersion = 1

  public let schemaVersion: Int
  public let id: UUID
  public let name: String
  public let styleID: String
  /// The credential-free style URL. Runtime tokens are intentionally never persisted.
  public let styleURL: URL
  public let styleAttribution: MapAttribution
  public let bounds: MapCoordinateBounds
  public let minimumZoomLevel: Double
  public let maximumZoomLevel: Double
  public let networkPolicy: OfflineNetworkPolicy
  public let createdAt: Date
  public let updatedAt: Date
  public let regionKey: String

  public init(request: OfflinePackRequest, createdAt: Date = Date()) {
    schemaVersion = Self.currentSchemaVersion
    id = request.id
    name = request.name
    styleID = request.style.id
    styleURL = request.style.styleURL
    styleAttribution = request.style.attribution
    bounds = request.bounds
    minimumZoomLevel = request.minimumZoomLevel
    maximumZoomLevel = request.maximumZoomLevel
    networkPolicy = request.networkPolicy
    self.createdAt = createdAt
    updatedAt = createdAt
    regionKey = request.regionKey
  }

  public static func regionKey(
    styleID: String,
    bounds: MapCoordinateBounds,
    minimumZoomLevel: Double,
    maximumZoomLevel: Double
  ) -> String {
    let values = [
      styleID,
      decimal(bounds.south),
      decimal(bounds.west),
      decimal(bounds.north),
      decimal(bounds.east),
      decimal(minimumZoomLevel),
      decimal(maximumZoomLevel),
    ]
    return values.joined(separator: "|")
  }

  private static func decimal(_ value: Double) -> String {
    String(format: "%.8f", locale: Locale(identifier: "en_US_POSIX"), value)
  }
}

public enum OfflinePackContextCodec {
  public static let maximumBytes = 16_384

  public static func encode(_ context: OfflinePackContext) throws -> Data {
    let encoder = JSONEncoder()
    encoder.dateEncodingStrategy = .millisecondsSince1970
    encoder.outputFormatting = [.sortedKeys]
    let data = try encoder.encode(context)
    guard data.count <= maximumBytes else {
      throw OfflineMapError.contextTooLarge
    }
    return data
  }

  public static func decode(_ data: Data) throws -> OfflinePackContext {
    guard !data.isEmpty, data.count <= maximumBytes else {
      throw data.count > maximumBytes
        ? OfflineMapError.contextTooLarge : OfflineMapError.corruptContext
    }
    let decoder = JSONDecoder()
    decoder.dateDecodingStrategy = .millisecondsSince1970
    guard let context = try? decoder.decode(OfflinePackContext.self, from: data),
      context.schemaVersion == OfflinePackContext.currentSchemaVersion,
      (1...100).contains(context.name.trimmingCharacters(in: .whitespacesAndNewlines).count),
      !context.styleID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
      context.minimumZoomLevel.isFinite,
      context.maximumZoomLevel.isFinite,
      context.minimumZoomLevel >= 0,
      context.maximumZoomLevel >= context.minimumZoomLevel,
      context.bounds.south >= -OfflineRegionValidationPolicy.webMercatorLatitudeLimit,
      context.bounds.north <= OfflineRegionValidationPolicy.webMercatorLatitudeLimit,
      context.regionKey
        == OfflinePackContext.regionKey(
          styleID: context.styleID,
          bounds: context.bounds,
          minimumZoomLevel: context.minimumZoomLevel,
          maximumZoomLevel: context.maximumZoomLevel
        )
    else {
      throw OfflineMapError.corruptContext
    }
    return context
  }
}

public enum OfflinePackState: String, Codable, Equatable, Sendable {
  case unknown
  case inactive
  case downloading
  case complete
  case failed
  case invalid
}

public struct OfflinePackProgress: Codable, Equatable, Sendable {
  public let resourcesCompleted: UInt64
  public let resourcesExpected: UInt64
  public let maximumResourcesExpected: UInt64?
  public let tilesCompleted: UInt64
  public let bytesCompleted: UInt64
  public let tileBytesCompleted: UInt64

  public init(
    resourcesCompleted: UInt64 = 0,
    resourcesExpected: UInt64 = 0,
    maximumResourcesExpected: UInt64? = nil,
    tilesCompleted: UInt64 = 0,
    bytesCompleted: UInt64 = 0,
    tileBytesCompleted: UInt64 = 0
  ) {
    self.resourcesCompleted = resourcesCompleted
    self.resourcesExpected = resourcesExpected
    self.maximumResourcesExpected = maximumResourcesExpected
    self.tilesCompleted = tilesCompleted
    self.bytesCompleted = bytesCompleted
    self.tileBytesCompleted = tileBytesCompleted
  }

  public var fractionCompleted: Double? {
    guard resourcesExpected > 0 else { return nil }
    return min(1, Double(resourcesCompleted) / Double(resourcesExpected))
  }
}

public struct OfflinePackFailure: Codable, Equatable, Sendable {
  public let code: Int?
  public let message: String
  public let isRecoverable: Bool

  public init(code: Int?, message: String, isRecoverable: Bool) {
    self.code = code
    self.message = message
    self.isRecoverable = isRecoverable
  }
}

public struct OfflinePackSnapshot: Codable, Equatable, Sendable, Identifiable {
  public let context: OfflinePackContext
  public let state: OfflinePackState
  public let progress: OfflinePackProgress
  public let estimate: OfflineStorageEstimate
  public let failure: OfflinePackFailure?
  /// MapLibre's full database usage, including offline packs and ambient cache resources.
  public let totalMapStorageBytes: UInt64

  public var id: UUID { context.id }
  public var isComplete: Bool { state == .complete }

  public init(
    context: OfflinePackContext,
    state: OfflinePackState,
    progress: OfflinePackProgress,
    failure: OfflinePackFailure? = nil,
    totalMapStorageBytes: UInt64 = 0
  ) {
    self.context = context
    self.state = state
    self.progress = progress
    estimate = OfflineStorageEstimate.estimate(
      bounds: context.bounds,
      minimumZoomLevel: context.minimumZoomLevel,
      maximumZoomLevel: context.maximumZoomLevel
    )
    self.failure = failure
    self.totalMapStorageBytes = totalMapStorageBytes
  }
}
