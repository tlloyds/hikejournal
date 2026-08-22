#if os(iOS) && canImport(MapLibre) && canImport(SwiftUI) && canImport(UIKit)
  import Foundation
  @preconcurrency import MapLibre
  import SwiftUI
  import UIKit

  public enum MapCameraBehavior: Sendable {
    case fitOnce
    case fitOnEveryUpdate
    case appControlled
  }

  /// Production SwiftUI surface backed by MapLibre Native. The app supplies only
  /// server-authoritative/domain data; this view performs no entitlement decisions.
  public struct HikeJournalMapSurface: View {
    private let scene: MapScene
    private let styleURL: URL
    private let cameraBehavior: MapCameraBehavior
    private let cameraPadding: EdgeInsets
    private let accessibility: MapAccessibilitySnapshot
    private let attributions: [MapAttribution]
    private let onSelectPoint: ((MapPoint) -> Void)?

    public init(
      scene: MapScene,
      style: MapStyleConfiguration,
      styleCredential: MapStyleCredential? = nil,
      cameraBehavior: MapCameraBehavior = .fitOnce,
      cameraPadding: EdgeInsets = EdgeInsets(top: 40, leading: 32, bottom: 48, trailing: 32),
      onSelectPoint: ((MapPoint) -> Void)? = nil
    ) throws {
      self.scene = scene
      styleURL = try style.resolvedURL(credential: styleCredential)
      self.cameraBehavior = cameraBehavior
      self.cameraPadding = cameraPadding
      self.onSelectPoint = onSelectPoint
      accessibility = MapAccessibility.snapshot(for: scene)

      var values = [style.attribution]
      values += NationalScenicTrailCatalog.selected(ids: scene.selectedTrailOverlayIDs)
        .flatMap(\.sourceAttributions)
      var seen: Set<String> = []
      attributions = values.filter { seen.insert($0.id).inserted }
    }

    public var body: some View {
      VStack(spacing: 4) {
        MapLibreRepresentable(
          scene: scene,
          styleURL: styleURL,
          cameraBehavior: cameraBehavior,
          cameraPadding: cameraPadding,
          onSelectPoint: onSelectPoint
        )
        .accessibilityLabel(Text(accessibility.summary))
        .accessibilityHint(Text("Explore the map visually or use the map details list."))

        MapAttributionLinks(attributions: attributions)
      }
    }
  }

  public struct MapAttributionLinks: View {
    public let attributions: [MapAttribution]

    public init(attributions: [MapAttribution]) {
      self.attributions = attributions
    }

    public var body: some View {
      ScrollView(.horizontal, showsIndicators: false) {
        HStack(spacing: 10) {
          Text("Map data:")
            .foregroundStyle(.secondary)
          ForEach(attributions) { attribution in
            Link(attribution.title, destination: attribution.url)
              .underline()
          }
        }
        .font(.caption2)
        .padding(.horizontal, 8)
        .frame(minHeight: 20)
      }
      .accessibilityElement(children: .contain)
      .accessibilityLabel("Map data attributions")
    }
  }

  private struct MapLibreRepresentable: UIViewRepresentable {
    let scene: MapScene
    let styleURL: URL
    let cameraBehavior: MapCameraBehavior
    let cameraPadding: EdgeInsets
    let onSelectPoint: ((MapPoint) -> Void)?

    func makeCoordinator() -> Coordinator {
      Coordinator()
    }

    func makeUIView(context: Context) -> MLNMapView {
      let mapView = MLNMapView(frame: .zero, styleURL: styleURL)
      mapView.delegate = context.coordinator
      mapView.showsLogoView = true
      mapView.showsAttributionButton = true
      mapView.compassViewPosition = .topRight
      mapView.accessibilityIdentifier = "hike-journal-map"
      context.coordinator.update(
        mapView: mapView,
        scene: scene,
        styleURL: styleURL,
        cameraBehavior: cameraBehavior,
        cameraPadding: cameraPadding,
        onSelectPoint: onSelectPoint
      )
      return mapView
    }

    func updateUIView(_ mapView: MLNMapView, context: Context) {
      context.coordinator.update(
        mapView: mapView,
        scene: scene,
        styleURL: styleURL,
        cameraBehavior: cameraBehavior,
        cameraPadding: cameraPadding,
        onSelectPoint: onSelectPoint
      )
    }

    static func dismantleUIView(_ mapView: MLNMapView, coordinator: Coordinator) {
      coordinator.stop()
      mapView.delegate = nil
    }

    @MainActor
    final class Coordinator: NSObject, @preconcurrency MLNMapViewDelegate {
      private enum RenderedPointKind {
        case domain(MapPointKind)
        case currentLocation
      }

      private let trailLoader = TrailGeoJSONLoader()
      private var annotations: [MLNAnnotation] = []
      private var pointKinds: [ObjectIdentifier: RenderedPointKind] = [:]
      private var pointsByAnnotation: [ObjectIdentifier: MapPoint] = [:]
      private var routeAnnotations: Set<ObjectIdentifier> = []
      private var currentScene = MapScene()
      private var selectedTrailIDs: Set<String> = []
      private var styleURL: URL?
      private var trailTask: Task<Void, Never>?
      private var trailGeneration = UUID()
      private var trailStyleIdentifiers: [(source: String, layer: String)] = []
      private var hasFitCamera = false
      private var onSelectPoint: ((MapPoint) -> Void)?

      func update(
        mapView: MLNMapView,
        scene: MapScene,
        styleURL: URL,
        cameraBehavior: MapCameraBehavior,
        cameraPadding: EdgeInsets,
        onSelectPoint: ((MapPoint) -> Void)?
      ) {
        currentScene = scene
        self.onSelectPoint = onSelectPoint
        let styleChanged = self.styleURL != styleURL
        if styleChanged {
          self.styleURL = styleURL
          mapView.styleURL = styleURL
        }
        replaceAnnotations(on: mapView, scene: scene)

        switch cameraBehavior {
        case .fitOnce where !hasFitCamera:
          fitCamera(on: mapView, scene: scene, padding: cameraPadding, animated: false)
          hasFitCamera = !scene.allCoordinates.isEmpty
        case .fitOnEveryUpdate:
          fitCamera(on: mapView, scene: scene, padding: cameraPadding, animated: true)
        case .fitOnce, .appControlled:
          break
        }

        if selectedTrailIDs != scene.selectedTrailOverlayIDs || styleChanged {
          selectedTrailIDs = scene.selectedTrailOverlayIDs
          reloadTrailOverlays(on: mapView)
        }
      }

      func stop() {
        trailTask?.cancel()
        trailTask = nil
      }

      func mapView(_ mapView: MLNMapView, didFinishLoading style: MLNStyle) {
        reloadTrailOverlays(on: mapView)
      }

      func mapView(
        _ mapView: MLNMapView,
        strokeColorForShapeAnnotation annotation: MLNShape
      ) -> UIColor {
        routeAnnotations.contains(ObjectIdentifier(annotation))
          ? UIColor(red: 0.11, green: 0.38, blue: 0.24, alpha: 1)
          : mapView.tintColor
      }

      func mapView(
        _ mapView: MLNMapView,
        lineWidthForPolylineAnnotation annotation: MLNPolyline
      ) -> CGFloat {
        routeAnnotations.contains(ObjectIdentifier(annotation)) ? 4 : 3
      }

      func mapView(
        _ mapView: MLNMapView,
        viewFor annotation: MLNAnnotation
      ) -> MLNAnnotationView? {
        let key = ObjectIdentifier(annotation as AnyObject)
        guard pointKinds.keys.contains(key) else { return nil }
        let reuseIdentifier = "hike-journal-point"
        let view =
          mapView.dequeueReusableAnnotationView(withIdentifier: reuseIdentifier)
          ?? MLNAnnotationView(reuseIdentifier: reuseIdentifier)
        view.frame = CGRect(x: 0, y: 0, width: 18, height: 18)
        view.layer.cornerRadius = 9
        view.layer.borderColor = UIColor.white.cgColor
        view.layer.borderWidth = 2
        view.layer.shadowColor = UIColor.black.cgColor
        view.layer.shadowOpacity = 0.22
        view.layer.shadowRadius = 2
        view.backgroundColor = Self.color(for: pointKinds[key])
        view.isAccessibilityElement = true
        view.accessibilityTraits = .button
        view.accessibilityLabel = annotation.title ?? "Map point"
        return view
      }

      func mapView(_ mapView: MLNMapView, annotationCanShowCallout annotation: MLNAnnotation)
        -> Bool
      {
        pointKinds.keys.contains(ObjectIdentifier(annotation as AnyObject))
      }

      func mapView(_ mapView: MLNMapView, didSelect annotation: MLNAnnotation) {
        guard let point = pointsByAnnotation[ObjectIdentifier(annotation as AnyObject)] else {
          return
        }
        onSelectPoint?(point)
      }

      private func replaceAnnotations(on mapView: MLNMapView, scene: MapScene) {
        if !annotations.isEmpty {
          mapView.removeAnnotations(annotations)
        }
        annotations.removeAll(keepingCapacity: true)
        pointKinds.removeAll(keepingCapacity: true)
        pointsByAnnotation.removeAll(keepingCapacity: true)
        routeAnnotations.removeAll(keepingCapacity: true)

        for route in scene.routes {
          for segment in route.segments {
            var coordinates = Self.unwrapped(segment.coordinates)
            let polyline = MLNPolyline(coordinates: &coordinates, count: UInt(coordinates.count))
            polyline.title = route.name.isEmpty ? "Recorded route" : route.name
            annotations.append(polyline)
            routeAnnotations.insert(ObjectIdentifier(polyline))
          }
        }
        for point in scene.points {
          let annotation = MLNPointAnnotation()
          annotation.coordinate = Self.sdkCoordinate(point.coordinate)
          annotation.title = point.accessibilityLabel
          annotation.subtitle = point.detail
          annotations.append(annotation)
          pointKinds[ObjectIdentifier(annotation)] = .domain(point.kind)
          pointsByAnnotation[ObjectIdentifier(annotation)] = point
        }
        if let location = scene.currentLocation {
          let annotation = MLNPointAnnotation()
          annotation.coordinate = Self.sdkCoordinate(location.coordinate)
          annotation.title = "Current location"
          annotation.subtitle =
            "Accurate to \(Int(location.horizontalAccuracyMeters.rounded())) meters"
          annotations.append(annotation)
          pointKinds[ObjectIdentifier(annotation)] = .currentLocation
        }
        if !annotations.isEmpty {
          mapView.addAnnotations(annotations)
        }
      }

      private func fitCamera(
        on mapView: MLNMapView,
        scene: MapScene,
        padding: EdgeInsets,
        animated: Bool
      ) {
        guard let fit = MapCameraFitter.fit(coordinates: scene.allCoordinates) else { return }
        let latitudeHalf = fit.latitudeSpan / 2
        let longitudeHalf = fit.longitudeSpan / 2
        let bounds = MLNCoordinateBounds(
          sw: CLLocationCoordinate2D(
            latitude: fit.center.latitude - latitudeHalf,
            longitude: fit.center.longitude - longitudeHalf
          ),
          ne: CLLocationCoordinate2D(
            latitude: fit.center.latitude + latitudeHalf,
            longitude: fit.center.longitude + longitudeHalf
          )
        )
        mapView.setVisibleCoordinateBounds(
          bounds,
          edgePadding: UIEdgeInsets(
            top: padding.top,
            left: padding.leading,
            bottom: padding.bottom,
            right: padding.trailing
          ),
          animated: animated,
          completionHandler: nil
        )
      }

      private func reloadTrailOverlays(on mapView: MLNMapView) {
        trailTask?.cancel()
        trailGeneration = UUID()
        let generation = trailGeneration
        removeTrailLayers(from: mapView.style)
        let definitions = NationalScenicTrailCatalog.selected(ids: selectedTrailIDs)
        guard !definitions.isEmpty, mapView.style != nil else { return }

        trailTask = Task { [weak self, weak mapView] in
          guard let self else { return }
          for definition in definitions {
            guard !Task.isCancelled else { return }
            do {
              let data = try await trailLoader.geoJSON(for: definition)
              guard !Task.isCancelled, generation == trailGeneration,
                let mapView, let style = mapView.style
              else {
                return
              }
              try addTrail(definition, data: data, to: style)
            } catch is CancellationError {
              return
            } catch {
              // Overlay failure is intentionally isolated from the base map.
              continue
            }
          }
        }
      }

      private func addTrail(
        _ definition: NationalScenicTrailDefinition,
        data: Data,
        to style: MLNStyle
      ) throws {
        let sourceID = "hike-journal-trail-source-\(definition.id)"
        let layerID = "hike-journal-trail-layer-\(definition.id)"
        if let existingLayer = style.layer(withIdentifier: layerID) {
          style.removeLayer(existingLayer)
        }
        if let existingSource = style.source(withIdentifier: sourceID) {
          style.removeSource(existingSource)
        }
        let shape = try MLNShape(data: data, encoding: String.Encoding.utf8.rawValue)
        let source = MLNShapeSource(identifier: sourceID, shape: shape, options: nil)
        let layer = MLNLineStyleLayer(identifier: layerID, source: source)
        layer.lineColor = NSExpression(
          forConstantValue: UIColor(red: 0.91, green: 0.39, blue: 0.08, alpha: 0.94)
        )
        layer.lineWidth = NSExpression(forConstantValue: 3.0)
        layer.lineJoin = NSExpression(forConstantValue: MLNLineJoin.round)
        layer.lineCap = NSExpression(forConstantValue: MLNLineCap.round)
        style.addSource(source)
        style.addLayer(layer)
        trailStyleIdentifiers.append((sourceID, layerID))
      }

      private func removeTrailLayers(from style: MLNStyle?) {
        guard let style else {
          trailStyleIdentifiers.removeAll()
          return
        }
        for identifier in trailStyleIdentifiers {
          if let layer = style.layer(withIdentifier: identifier.layer) {
            style.removeLayer(layer)
          }
          if let source = style.source(withIdentifier: identifier.source) {
            style.removeSource(source)
          }
        }
        trailStyleIdentifiers.removeAll()
      }

      private static func sdkCoordinate(_ coordinate: GeoCoordinate) -> CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: coordinate.latitude, longitude: coordinate.longitude)
      }

      private static func unwrapped(_ coordinates: [GeoCoordinate]) -> [CLLocationCoordinate2D] {
        var result: [CLLocationCoordinate2D] = []
        result.reserveCapacity(coordinates.count)
        var previousLongitude: Double?
        for coordinate in coordinates {
          var longitude = coordinate.longitude
          if let previousLongitude {
            while longitude - previousLongitude > 180 { longitude -= 360 }
            while longitude - previousLongitude < -180 { longitude += 360 }
          }
          result.append(CLLocationCoordinate2D(latitude: coordinate.latitude, longitude: longitude))
          previousLongitude = longitude
        }
        return result
      }

      private static func color(for kind: RenderedPointKind?) -> UIColor {
        switch kind {
        case .domain(.geotaggedPhoto):
          return UIColor(red: 0.06, green: 0.49, blue: 0.51, alpha: 1)
        case .domain(.geotaggedVideo):
          return UIColor(red: 0.16, green: 0.37, blue: 0.72, alpha: 1)
        case .domain(.fieldMark):
          return UIColor(red: 0.90, green: 0.42, blue: 0.08, alpha: 1)
        case .domain(.sighting):
          return UIColor(red: 0.18, green: 0.50, blue: 0.23, alpha: 1)
        case .domain(.discovery):
          return UIColor(red: 0.78, green: 0.62, blue: 0.09, alpha: 1)
        case .domain(.place):
          return UIColor(red: 0.45, green: 0.29, blue: 0.16, alpha: 1)
        case .currentLocation, nil:
          return UIColor(red: 0.06, green: 0.45, blue: 0.90, alpha: 1)
        }
      }
    }
  }

  private enum TrailGeoJSONError: Error {
    case invalidResponse
    case responseTooLarge
    case invalidGeoJSON
  }

  private actor TrailGeoJSONLoader {
    private static let maximumPageBytes = 30_000_000
    private static let maximumFeatures = 100_000
    private var memoryCache: [String: Data] = [:]

    func geoJSON(for definition: NationalScenicTrailDefinition) async throws -> Data {
      if let cached = memoryCache[definition.id] {
        return cached
      }
      var features: [[String: Any]] = []
      for layerURL in definition.layerURLs {
        for page in 0..<NationalScenicTrailCatalog.maximumPages {
          try Task.checkCancellation()
          guard let url = definition.geoJSONPageURL(layerURL: layerURL, page: page) else {
            throw TrailGeoJSONError.invalidResponse
          }
          var request = URLRequest(url: url)
          request.timeoutInterval = 30
          request.setValue("HikeJournal/iOS", forHTTPHeaderField: "User-Agent")
          let (data, response) = try await URLSession.shared.data(for: request)
          guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode)
          else {
            throw TrailGeoJSONError.invalidResponse
          }
          guard data.count <= Self.maximumPageBytes else {
            throw TrailGeoJSONError.responseTooLarge
          }
          guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any],
            object["type"] as? String == "FeatureCollection",
            let pageFeatures = object["features"] as? [[String: Any]]
          else {
            throw TrailGeoJSONError.invalidGeoJSON
          }
          guard features.count + pageFeatures.count <= Self.maximumFeatures else {
            throw TrailGeoJSONError.responseTooLarge
          }
          features += pageFeatures
          if pageFeatures.count < NationalScenicTrailCatalog.pageSize { break }
        }
      }
      let result = try JSONSerialization.data(
        withJSONObject: ["type": "FeatureCollection", "features": features]
      )
      memoryCache[definition.id] = result
      return result
    }
  }
#endif
