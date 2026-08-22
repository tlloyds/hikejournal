import Foundation
import HikeJournalDomain
import HikeJournalMaps
import HikeJournalTracking

enum JournalMapSceneFactory {
    static func make(
        routes sourceRoutes: [MapRoute],
        hikes: [Hike],
        details: [String: Hike],
        sightings: [Sighting],
        tracking: TrackingSnapshot?,
        selectedTrailOverlayIDs: Set<String>
    ) -> MapScene {
        let titles = Dictionary(
            uniqueKeysWithValues: (hikes + Array(details.values)).map { ($0.id, $0.title) }
        )
        var routes: [RecordedRoute] = sourceRoutes.compactMap { route in
            recordedRoute(
                id: route.hikeId,
                name: titles[route.hikeId] ?? "Recorded outing",
                segments: route.segments.map { $0.map { ($0.latitude, $0.longitude) } }
            )
        }
        var routeIDs = Set(routes.map(\.id))
        for hike in details.values where !routeIDs.contains(hike.id) {
            guard let route = recordedRoute(
                id: hike.id,
                name: hike.title,
                segments: hike.routeSegments.map { $0.map { ($0.latitude, $0.longitude) } }
            ) else { continue }
            routes.append(route)
            routeIDs.insert(hike.id)
        }

        var currentLocation: MapCurrentLocation?
        if let tracking {
            let activeSegments = tracking.routeSegments.map {
                $0.map { ($0.latitude, $0.longitude) }
            }
            if let route = recordedRoute(
                id: "tracking:\(tracking.sessionID)",
                name: tracking.status == .paused ? "Paused recording" : "Recording now",
                segments: activeSegments
            ) {
                routes.removeAll { $0.id == tracking.hikeID }
                routes.append(route)
            }
            if tracking.status != .finished,
               let last = tracking.routeSegments.flatMap({ $0 }).last,
               let coordinate = try? GeoCoordinate(
                   latitude: last.latitude,
                   longitude: last.longitude
               ) {
                currentLocation = try? MapCurrentLocation(
                    coordinate: coordinate,
                    horizontalAccuracyMeters: max(0, last.accuracyMeters),
                    recordedAt: last.timestamp
                )
            }
        }

        var pointsByID: [String: MapPoint] = [:]
        for sighting in sightings {
            let kind: MapPointKind = sighting.confirmed || !sighting.speciesName.isEmpty
                ? .sighting
                : .geotaggedPhoto
            let title = firstNonempty(
                sighting.speciesName,
                sighting.caption,
                sighting.hikeTitle,
                fallback: "Geotagged photo"
            )
            let detail = [sighting.hikeTitle, sighting.locationName]
                .filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
                .joined(separator: " · ")
            if let point = mapPoint(
                id: "media:\(sighting.id)",
                kind: kind,
                title: title,
                detail: detail,
                latitude: sighting.latitude,
                longitude: sighting.longitude
            ) {
                pointsByID[point.id] = point
            }
        }

        for hike in details.values {
            for photo in hike.photos {
                guard let latitude = photo.latitude, let longitude = photo.longitude else { continue }
                let species = photo.species.first { $0.isPrimary } ?? photo.species.first
                let kind: MapPointKind
                if photo.contentType.lowercased().hasPrefix("video/") {
                    kind = .geotaggedVideo
                } else if species != nil {
                    kind = .sighting
                } else {
                    kind = .geotaggedPhoto
                }
                let title = firstNonempty(
                    species?.commonName,
                    photo.caption,
                    hike.title,
                    fallback: kind == .geotaggedVideo ? "Geotagged video" : "Geotagged photo"
                )
                if let point = mapPoint(
                    id: "media:\(photo.id)",
                    kind: kind,
                    title: title,
                    detail: hike.title,
                    latitude: latitude,
                    longitude: longitude
                ) {
                    pointsByID[point.id] = point
                }
            }
            for mark in hike.fieldMarks {
                let markName = mark.markType
                    .replacingOccurrences(of: "_", with: " ")
                    .localizedCapitalized
                if let point = mapPoint(
                    id: "field-mark:\(mark.id)",
                    kind: .fieldMark,
                    title: firstNonempty(mark.note, markName, fallback: "Field mark"),
                    detail: "\(markName) · \(hike.title)",
                    latitude: mark.latitude,
                    longitude: mark.longitude
                ) {
                    pointsByID[point.id] = point
                }
            }
        }

        return MapScene(
            routes: routes,
            currentLocation: currentLocation,
            points: pointsByID.values.sorted { $0.id < $1.id },
            selectedTrailOverlayIDs: selectedTrailOverlayIDs
        )
    }

    private static func recordedRoute(
        id: String,
        name: String,
        segments: [[(Double, Double)]]
    ) -> RecordedRoute? {
        let validSegments: [RecordedRouteSegment] = segments.enumerated().compactMap { index, points in
            let coordinates = points.compactMap { point in
                try? GeoCoordinate(latitude: point.0, longitude: point.1)
            }
            return try? RecordedRouteSegment(id: "\(id):\(index)", coordinates: coordinates)
        }
        guard !validSegments.isEmpty else { return nil }
        return try? RecordedRoute(id: id, name: name, segments: validSegments)
    }

    private static func mapPoint(
        id: String,
        kind: MapPointKind,
        title: String,
        detail: String,
        latitude: Double,
        longitude: Double
    ) -> MapPoint? {
        guard let coordinate = try? GeoCoordinate(latitude: latitude, longitude: longitude) else {
            return nil
        }
        return try? MapPoint(
            id: id,
            kind: kind,
            title: title,
            detail: detail.isEmpty ? nil : detail,
            coordinate: coordinate
        )
    }

    private static func firstNonempty(
        _ values: String? ...,
        fallback: String
    ) -> String {
        values
            .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
            .first { !$0.isEmpty } ?? fallback
    }
}
