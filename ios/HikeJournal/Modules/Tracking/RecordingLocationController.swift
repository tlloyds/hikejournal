@preconcurrency import CoreLocation
import Dispatch
import Foundation
import HikeJournalTracking

@MainActor
protocol RecordingLocationControlling: AnyObject {
    var authorizationStatus: CLAuthorizationStatus { get }
    var onSample: ((LocationSample, Date) -> Void)? { get set }
    var onError: ((Error) -> Void)? { get set }
    var onAuthorizationChange: ((CLAuthorizationStatus) -> Void)? { get set }
    func requestAlwaysAuthorization()
    func start() throws
    func stop()
}

enum RecordingLocationError: Error, Equatable, LocalizedError {
    case alwaysAuthorizationRequired
    case locationServicesDisabled

    var errorDescription: String? {
        switch self {
        case .alwaysAuthorizationRequired:
            "Allow Always location access so HikeJournal can keep recording with the screen locked."
        case .locationServicesDisabled:
            "Location Services are unavailable on this iPhone."
        }
    }
}

@MainActor
final class RecordingLocationController: NSObject, RecordingLocationControlling {
    var onSample: ((LocationSample, Date) -> Void)?
    var onError: ((Error) -> Void)?
    var onAuthorizationChange: ((CLAuthorizationStatus) -> Void)?

    private let manager: CLLocationManager

    override init() {
        manager = CLLocationManager()
        super.init()
        manager.delegate = self
        manager.activityType = .fitness
        manager.desiredAccuracy = kCLLocationAccuracyBestForNavigation
        manager.distanceFilter = 2
        manager.pausesLocationUpdatesAutomatically = false
    }

    var authorizationStatus: CLAuthorizationStatus {
        manager.authorizationStatus
    }

    func requestAlwaysAuthorization() {
        manager.requestAlwaysAuthorization()
    }

    func start() throws {
        guard CLLocationManager.locationServicesEnabled() else {
            throw RecordingLocationError.locationServicesDisabled
        }
        guard manager.authorizationStatus == .authorizedAlways else {
            throw RecordingLocationError.alwaysAuthorizationRequired
        }
        manager.allowsBackgroundLocationUpdates = true
        manager.showsBackgroundLocationIndicator = true
        manager.startUpdatingLocation()
    }

    func stop() {
        manager.stopUpdatingLocation()
        manager.allowsBackgroundLocationUpdates = false
        manager.showsBackgroundLocationIndicator = false
    }
}

extension RecordingLocationController: @preconcurrency CLLocationManagerDelegate {
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        onAuthorizationChange?(manager.authorizationStatus)
        if manager.authorizationStatus == .denied || manager.authorizationStatus == .restricted {
            stop()
        }
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        onError?(error)
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        let receivedAt = Date()
        let receivedMonotonic = DispatchTime.now().uptimeNanoseconds
        for location in locations {
            let ageNanoseconds = max(0, receivedAt.timeIntervalSince(location.timestamp)) * 1_000_000_000
            let boundedAge = min(Double(receivedMonotonic), ageNanoseconds)
            let fixMonotonic = receivedMonotonic - UInt64(boundedAge.rounded(.towardZero))
            let altitude = location.verticalAccuracy >= 0 && location.altitude.isFinite
                ? location.altitude
                : nil
            onSample?(
                LocationSample(
                    latitude: location.coordinate.latitude,
                    longitude: location.coordinate.longitude,
                    altitudeMeters: altitude,
                    horizontalAccuracyMeters: location.horizontalAccuracy,
                    timestamp: location.timestamp,
                    monotonicTimestampNanoseconds: Int64(
                        min(fixMonotonic, UInt64(Int64.max))
                    )
                ),
                receivedAt
            )
        }
    }
}
