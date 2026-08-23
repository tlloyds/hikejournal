@preconcurrency import CoreLocation
import Foundation

@MainActor
protocol LocationPermissionClient: AnyObject {
    var authorizationStatus: CLAuthorizationStatus { get }
    var authorizationDidChange: ((CLAuthorizationStatus) -> Void)? { get set }
    func requestWhenInUse()
    func requestCurrentLocation() async throws -> CLLocation
}

enum CurrentLocationError: LocalizedError {
    case permissionDenied
    case unavailable

    var errorDescription: String? {
        switch self {
        case .permissionDenied: "Allow location access to search around where you are."
        case .unavailable: "Your current location is not available yet."
        }
    }
}

extension LocationPermissionClient {
    func requestCurrentLocation() async throws -> CLLocation {
        throw CurrentLocationError.unavailable
    }
}

@MainActor
final class SystemLocationPermissionClient: NSObject, LocationPermissionClient {
    var authorizationDidChange: ((CLAuthorizationStatus) -> Void)?

    private let manager: CLLocationManager
    private var locationContinuation: CheckedContinuation<CLLocation, Error>?

    override init() {
        manager = CLLocationManager()
        super.init()
        manager.activityType = .fitness
        manager.delegate = self
    }

    var authorizationStatus: CLAuthorizationStatus {
        manager.authorizationStatus
    }

    func requestWhenInUse() {
        manager.requestWhenInUseAuthorization()
    }

    func requestCurrentLocation() async throws -> CLLocation {
        guard CLLocationManager.locationServicesEnabled() else {
            throw CurrentLocationError.unavailable
        }
        if manager.authorizationStatus != .authorizedAlways && manager.authorizationStatus != .authorizedWhenInUse {
            if manager.authorizationStatus == .notDetermined {
                manager.requestWhenInUseAuthorization()
                try await Task.sleep(for: .milliseconds(250))
            }
            guard manager.authorizationStatus == .authorizedAlways || manager.authorizationStatus == .authorizedWhenInUse else {
                throw CurrentLocationError.permissionDenied
            }
        }
        return try await withCheckedThrowingContinuation { continuation in
            locationContinuation = continuation
            manager.requestLocation()
        }
    }

}

extension SystemLocationPermissionClient: @preconcurrency CLLocationManagerDelegate {
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        authorizationDidChange?(manager.authorizationStatus)
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let continuation = locationContinuation, let location = locations.last else { return }
        locationContinuation = nil
        continuation.resume(returning: location)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        guard let continuation = locationContinuation else { return }
        locationContinuation = nil
        continuation.resume(throwing: error)
    }
}
