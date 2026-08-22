import Foundation

public struct MapAccessibilityItem: Codable, Equatable, Sendable, Identifiable {
  public let id: String
  public let label: String

  public init(id: String, label: String) {
    self.id = id
    self.label = label
  }
}

public struct MapAccessibilitySnapshot: Codable, Equatable, Sendable {
  public let summary: String
  public let items: [MapAccessibilityItem]

  public init(summary: String, items: [MapAccessibilityItem]) {
    self.summary = summary
    self.items = items
  }
}

public enum MapAccessibility {
  public static func snapshot(for scene: MapScene) -> MapAccessibilitySnapshot {
    let segments = scene.routes.flatMap(\.segments)
    let routePoints = segments.reduce(0) { $0 + $1.coordinates.count }
    let photoCount = scene.points(of: .geotaggedPhoto).count
    let videoCount = scene.points(of: .geotaggedVideo).count
    let fieldMarkCount = scene.points(of: .fieldMark).count
    let sightingCount = scene.points(of: .sighting).count
    let discoveryCount = scene.points(of: .discovery).count
    let placeCount = scene.points(of: .place).count

    var parts = ["Hike map"]
    parts.append(
      "\(segments.count) \(plural(segments.count, singular: "recorded route segment")) with \(routePoints) \(plural(routePoints, singular: "track point"))"
    )
    parts.append(
      scene.currentLocation == nil ? "current location unavailable" : "current location shown")
    parts.append("\(photoCount) \(plural(photoCount, singular: "geotagged photo"))")
    parts.append("\(videoCount) \(plural(videoCount, singular: "geotagged video"))")
    parts.append("\(fieldMarkCount) \(plural(fieldMarkCount, singular: "field mark"))")
    parts.append("\(sightingCount) \(plural(sightingCount, singular: "sighting"))")
    parts.append(
      "\(discoveryCount) \(plural(discoveryCount, singular: "discovery", plural: "discoveries"))")
    parts.append("\(placeCount) \(plural(placeCount, singular: "place"))")

    let overlayNames = NationalScenicTrailCatalog.all
      .filter { scene.selectedTrailOverlayIDs.contains($0.id) }
      .map(\.name)
    if !overlayNames.isEmpty {
      parts.append("trail overlays: \(overlayNames.joined(separator: ", "))")
    }

    var items: [MapAccessibilityItem] = []
    for route in scene.routes {
      for (index, segment) in route.segments.enumerated() {
        let routeName = route.name.trimmingCharacters(in: .whitespacesAndNewlines)
        let title = routeName.isEmpty ? "Recorded route" : routeName
        items.append(
          MapAccessibilityItem(
            id: "route:\(route.id):\(segment.id)",
            label: "\(title), segment \(index + 1), \(segment.coordinates.count) track points"
          )
        )
      }
    }
    if let currentLocation = scene.currentLocation {
      items.append(
        MapAccessibilityItem(
          id: "current-location",
          label:
            "Current location, accurate to \(Int(currentLocation.horizontalAccuracyMeters.rounded())) meters"
        )
      )
    }
    items += scene.points.map {
      MapAccessibilityItem(id: "point:\($0.id)", label: $0.accessibilityLabel)
    }

    return MapAccessibilitySnapshot(summary: parts.joined(separator: ". ") + ".", items: items)
  }

  private static func plural(
    _ count: Int,
    singular: String,
    plural: String? = nil
  ) -> String {
    count == 1 ? singular : (plural ?? singular + "s")
  }
}
