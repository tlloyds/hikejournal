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

      var values = [style.attribution, Self.satelliteAttribution]
      values += NationalScenicTrailCatalog.selected(ids: scene.selectedTrailOverlayIDs)
        .flatMap(\.sourceAttributions)
      var seen: Set<String> = []
      attributions = values.filter { seen.insert($0.id).inserted }
    }

    private static let satelliteAttribution: MapAttribution = {
      // The imagery layer is intentionally owned by the map surface so the
      // configured vector style remains useful as a fallback while imagery
      // tiles load. Keep the provider credit visible alongside the style's
      // existing attribution.
      try! MapAttribution(
        id: "esri-world-imagery",
        title: "Esri World Imagery",
        url: URL(string: "https://www.esri.com/en-us/legal/terms/full-master-agreement")!
      )
    }()

  public var body: some View {
      VStack(spacing: 4) {
        ZStack(alignment: .topTrailing) {
          MapLibreRepresentable(
            scene: scene,
            styleURL: styleURL,
            cameraBehavior: cameraBehavior,
            cameraPadding: cameraPadding,
            onSelectPoint: onSelectPoint
          )
          // MapLibre exposes every rendered feature to UIKit accessibility.
          // A national trail can contain thousands of segments, so exposing
          // that internal tree makes accessibility traversal recurse for a
          // very long time. The map-details list is the detailed accessible
          // alternative; keep the canvas itself as one map element.
          .accessibilityElement(children: .ignore)
          .accessibilityLabel(Text(accessibility.summary))
          .accessibilityHint(Text("Explore the map visually or use the map details list."))

          MapZoomControls()
        }

        MapAttributionLinks(attributions: attributions)
      }
    }
  }

  private struct MapZoomControls: View {
    var body: some View {
      VStack(spacing: 0) {
        Button(action: { NotificationCenter.default.post(name: .hikeJournalMapZoomIn, object: nil) }) {
          Image(systemName: "plus")
        }
        .accessibilityLabel("Zoom in")

        Divider()

        Button(action: { NotificationCenter.default.post(name: .hikeJournalMapZoomOut, object: nil) }) {
          Image(systemName: "minus")
        }
        .accessibilityLabel("Zoom out")
      }
      .font(.headline.weight(.semibold))
      .frame(width: 42, height: 84)
      .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 10))
      .padding(12)
    }
  }

  private extension Notification.Name {
    static let hikeJournalMapZoomIn = Notification.Name("HikeJournalMapZoomIn")
    static let hikeJournalMapZoomOut = Notification.Name("HikeJournalMapZoomOut")
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
      mapView.isZoomEnabled = true
      mapView.isScrollEnabled = true
      mapView.isRotateEnabled = true
      mapView.isPitchEnabled = true
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
      private var routeTask: Task<Void, Never>?
      private var routeGeneration = UUID()
      private var routeStyleIdentifiers: [(source: String, layer: String)] = []
      private var trailTask: Task<Void, Never>?
      private var trailGeneration = UUID()
      private var trailStyleIdentifiers: [(source: String, layer: String)] = []
      private var hasFitCamera = false
      private var mapDidFinishLoading = false
      private var latestScene = MapScene()
      private var latestCameraBehavior: MapCameraBehavior = .fitOnce
      private var latestCameraPadding = EdgeInsets(top: 40, leading: 32, bottom: 48, trailing: 32)
      private var zoomObserverTokens: [NSObjectProtocol] = []
      private weak var mapView: MLNMapView?
      private var onSelectPoint: ((MapPoint) -> Void)?

      override init() {
        super.init()
        zoomObserverTokens = [
          NotificationCenter.default.addObserver(
            forName: .hikeJournalMapZoomIn,
            object: nil,
            queue: .main
          ) { [weak self] _ in
            self?.adjustZoom(by: 1)
          },
          NotificationCenter.default.addObserver(
            forName: .hikeJournalMapZoomOut,
            object: nil,
            queue: .main
          ) { [weak self] _ in
            self?.adjustZoom(by: -1)
          }
        ]
      }

      deinit {
        for token in zoomObserverTokens {
          NotificationCenter.default.removeObserver(token)
        }
      }

      func update(
        mapView: MLNMapView,
        scene: MapScene,
        styleURL: URL,
        cameraBehavior: MapCameraBehavior,
        cameraPadding: EdgeInsets,
        onSelectPoint: ((MapPoint) -> Void)?
      ) {
        self.mapView = mapView
        let routesChanged = currentScene.routes != scene.routes
        currentScene = scene
        latestScene = scene
        latestCameraBehavior = cameraBehavior
        latestCameraPadding = cameraPadding
        self.onSelectPoint = onSelectPoint
        mapView.isZoomEnabled = true
        mapView.isScrollEnabled = true
        let styleChanged = self.styleURL != styleURL
        if styleChanged {
          self.styleURL = styleURL
          mapView.styleURL = styleURL
          mapDidFinishLoading = false
          hasFitCamera = false
        }
        replaceAnnotations(on: mapView, scene: scene)

        if routesChanged || styleChanged {
          reloadRouteOverlays(on: mapView, scene: scene)
        }

        switch cameraBehavior {
        case .fitOnce where mapDidFinishLoading && !hasFitCamera:
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
        routeTask?.cancel()
        routeTask = nil
        trailTask?.cancel()
        trailTask = nil
        if let style = mapView?.style {
          removeRouteLayers(from: style)
          removeTrailLayers(from: style)
        }
        mapView = nil
      }

      func mapViewDidFinishLoadingMap(_ mapView: MLNMapView) {
        mapDidFinishLoading = true
        if latestCameraBehavior == .fitOnce && !hasFitCamera {
          fitCamera(
            on: mapView,
            scene: latestScene,
            padding: latestCameraPadding,
            animated: false
          )
          hasFitCamera = !latestScene.allCoordinates.isEmpty
        }
      }

      func mapView(_ mapView: MLNMapView, didFinishLoading style: MLNStyle) {
        configureSatelliteBasemap(on: style)
        // Re-add the annotations after the imagery layer so MapLibre places
        // point markers above the satellite raster. Recorded routes use an
        // explicit style layer below those markers; MapLibre's polyline
        // annotation layer otherwise remains underneath the raster.
        replaceAnnotations(on: mapView, scene: latestScene)
        reloadRouteOverlays(on: mapView, scene: latestScene)
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

      private func adjustZoom(by delta: Double) {
        guard let mapView else { return }
        mapView.setZoomLevel(
          min(mapView.maximumZoomLevel, max(mapView.minimumZoomLevel, mapView.zoomLevel + delta)),
          animated: true
        )
      }

      private func reloadRouteOverlays(on mapView: MLNMapView, scene: MapScene) {
        routeTask?.cancel()
        routeGeneration = UUID()
        let generation = routeGeneration
        removeRouteLayers(from: mapView.style)
        guard !scene.routes.isEmpty, mapView.style != nil else { return }

        routeTask = Task { [weak self, weak mapView] in
          guard let self else { return }
          do {
            let shape = try await Self.prepareRouteShape(routes: scene.routes)
            guard !Task.isCancelled, generation == routeGeneration,
              let mapView, let style = mapView.style
            else {
              return
            }
            try addRoutes(shape: shape, to: style)
          } catch is CancellationError {
            return
          } catch {
            // Route rendering is isolated from the satellite basemap and
            // point annotations so malformed route data cannot take down the
            // map surface.
            return
          }
        }
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
              let shape = try await Self.prepareTrailShape(data: data)
              guard !Task.isCancelled, generation == trailGeneration,
                let style = mapView.style
              else {
                return
              }
              try addTrail(definition, shape: shape, to: style)
            } catch is CancellationError {
              return
            } catch {
              // Overlay failure is intentionally isolated from the base map.
              continue
            }
          }
        }
      }

      private func addRoutes(shape: MLNShape, to style: MLNStyle) throws {
        let sourceID = "hike-journal-routes-source"
        let layerID = "hike-journal-routes-layer"
        if let existingLayer = style.layer(withIdentifier: layerID) {
          style.removeLayer(existingLayer)
        }
        if let existingSource = style.source(withIdentifier: sourceID) {
          style.removeSource(existingSource)
        }
        let source = MLNShapeSource(identifier: sourceID, shape: shape, options: nil)
        let layer = MLNLineStyleLayer(identifier: layerID, source: source)
        layer.lineColor = NSExpression(
          forConstantValue: UIColor(red: 0.08, green: 0.38, blue: 0.23, alpha: 0.96)
        )
        layer.lineWidth = NSExpression(forConstantValue: 4.0)
        layer.lineJoin = NSExpression(forConstantValue: "round")
        layer.lineCap = NSExpression(forConstantValue: "round")
        style.addSource(source)
        style.addLayer(layer)
        routeStyleIdentifiers = [(sourceID, layerID)]
      }

      private func configureSatelliteBasemap(on style: MLNStyle) {
        let sourceID = "hike-journal-satellite-source"
        let layerID = "hike-journal-satellite-layer"
        if let existingLayer = style.layer(withIdentifier: layerID) {
          style.removeLayer(existingLayer)
        }
        if let existingSource = style.source(withIdentifier: sourceID) {
          style.removeSource(existingSource)
        }

        let source = MLNRasterTileSource(
          identifier: sourceID,
          tileURLTemplates: [
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          ],
          options: [MLNTileSourceOption.tileSize: 256]
        )
        let layer = MLNRasterStyleLayer(identifier: layerID, source: source)
        layer.rasterOpacity = NSExpression(forConstantValue: 1.0)
        style.addSource(source)
        // Add imagery after the configured vector style, then re-add our
        // annotations above it in didFinishLoading(_:). This keeps the
        // satellite tiles as the visual base without hiding routes or points.
        style.addLayer(layer)
      }

      private nonisolated static func prepareRouteShape(routes: [RecordedRoute]) async throws
        -> MLNShape
      {
        let prepared = try await Task.detached(priority: .userInitiated) {
          let data = try routeGeoJSONData(routes: routes)
          return try PreparedRouteShape(
            shape: MLNShape(data: data, encoding: String.Encoding.utf8.rawValue)
          )
        }.value
        return prepared.shape
      }

      private nonisolated static func routeGeoJSONData(routes: [RecordedRoute]) throws -> Data {
        let coordinates = routes.flatMap { route in
          route.segments.map { segment in
            segment.coordinates.map { [$0.longitude, $0.latitude] }
          }
        }
        return try JSONSerialization.data(
          withJSONObject: ["type": "MultiLineString", "coordinates": coordinates]
        )
      }

      private nonisolated static func prepareTrailShape(data: Data) async throws -> MLNShape {
        let prepared = try await Task.detached(priority: .userInitiated) {
          try PreparedTrailShape(shape: MLNShape(data: data, encoding: String.Encoding.utf8.rawValue))
        }.value
        return prepared.shape
      }

      private func addTrail(
        _ definition: NationalScenicTrailDefinition,
        shape: MLNShape,
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
        let source = MLNShapeSource(identifier: sourceID, shape: shape, options: nil)
        let layer = MLNLineStyleLayer(identifier: layerID, source: source)
        layer.lineColor = NSExpression(
          forConstantValue: UIColor(red: 0.91, green: 0.39, blue: 0.08, alpha: 0.94)
        )
        layer.lineWidth = NSExpression(forConstantValue: 3.0)
        // MapLibre accepts the documented string constants here. Boxing the
        // Swift-imported enum directly produces __SwiftValue, which MapLibre
        // cannot unwrap and which crashes when the overlay is added.
        layer.lineJoin = NSExpression(forConstantValue: "round")
        layer.lineCap = NSExpression(forConstantValue: "round")
        style.addSource(source)
        style.addLayer(layer)
        trailStyleIdentifiers.append((sourceID, layerID))
      }

      private struct PreparedTrailShape: @unchecked Sendable {
        let shape: MLNShape
      }

      private struct PreparedRouteShape: @unchecked Sendable {
        let shape: MLNShape
      }

      private func removeRouteLayers(from style: MLNStyle?) {
        guard let style else {
          routeStyleIdentifiers.removeAll()
          return
        }
        for identifier in routeStyleIdentifiers {
          if let layer = style.layer(withIdentifier: identifier.layer) {
            style.removeLayer(layer)
          }
          if let source = style.source(withIdentifier: identifier.source) {
            style.removeSource(source)
          }
        }
        routeStyleIdentifiers.removeAll()
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
