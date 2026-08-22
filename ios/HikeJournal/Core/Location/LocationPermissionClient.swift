@preconcurrency import CoreLocation
import Foundation

@MainActor
protocol LocationPermissionClient: AnyObject {
    var authorizationStatus: CLAuthorizationStatus { get }
    var authorizationDidChange: ((CLAuthorizationStatus) -> Void)? { get set }
    func requestWhenInUse()
}

@MainActor
final class SystemLocationPermissionClient: NSObject, LocationPermissionClient {
    var authorizationDidChange: ((CLAuthorizationStatus) -> Void)?

    private let manager: CLLocationManager

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

}

extension SystemLocationPermissionClient: @preconcurrency CLLocationManagerDelegate {
    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        authorizationDidChange?(manager.authorizationStatus)
    }
}
