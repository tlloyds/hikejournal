import Combine
import Foundation
import HikeJournalDomain

@MainActor
final class RiverGaugePreferencesStore: ObservableObject {
    @Published private(set) var followedGauges: [RiverGauge]

    private static let storageKey = "places.followedRiverGauges.v1"
    private let defaults: UserDefaults

    private struct PersistedGauge: Codable {
        let siteID: String
        let name: String
        let latitude: Double
        let longitude: Double
        let suggested: Bool

        init(_ gauge: RiverGauge) {
            siteID = gauge.siteId
            name = gauge.name
            latitude = gauge.latitude
            longitude = gauge.longitude
            suggested = gauge.suggested
        }
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        followedGauges = Self.load(from: defaults)
    }

    var followedIDs: [String] {
        followedGauges.map(\.siteId).sorted()
    }

    func isFollowed(_ gauge: RiverGauge) -> Bool {
        guard let siteID = Self.normalizedSiteID(gauge.siteId) else { return false }
        return followedGauges.contains { $0.siteId == siteID }
    }

    func setFollowed(_ gauge: RiverGauge, isFollowed: Bool) {
        guard let siteID = Self.normalizedSiteID(gauge.siteId) else { return }
        var values = followedGauges.filter { $0.siteId != siteID }
        if isFollowed {
            values.append(
                RiverGauge(
                    siteId: siteID,
                    name: gauge.name.trimmingCharacters(in: .whitespacesAndNewlines),
                    latitude: gauge.latitude,
                    longitude: gauge.longitude,
                    enabled: true,
                    suggested: gauge.suggested
                )
            )
        }
        followedGauges = Self.sorted(values)
        persist()
    }

    func remove(siteID: String) {
        guard let siteID = Self.normalizedSiteID(siteID) else { return }
        followedGauges.removeAll { $0.siteId == siteID }
        persist()
    }

    static func normalizedSiteID(_ rawValue: String) -> String? {
        var value = rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
        if let range = value.range(
            of: "monitoring-location/",
            options: [.caseInsensitive, .backwards]
        ) {
            value = String(value[range.upperBound...])
        }
        value = value
            .components(separatedBy: CharacterSet(charactersIn: "?/#"))
            .first?
            .uppercased() ?? ""
        if !value.hasPrefix("USGS-") {
            value = "USGS-" + value
        }
        let station = String(value.dropFirst("USGS-".count))
        guard (5...20).contains(station.count),
              station.unicodeScalars.allSatisfy({
                  CharacterSet.alphanumerics.contains($0) || $0 == "-"
              }) else {
            return nil
        }
        return value
    }

    private func persist() {
        guard let data = try? JSONEncoder().encode(followedGauges.map(PersistedGauge.init)) else { return }
        defaults.set(data, forKey: Self.storageKey)
    }

    private static func load(from defaults: UserDefaults) -> [RiverGauge] {
        guard let data = defaults.data(forKey: storageKey),
              let decoded = try? JSONDecoder().decode([PersistedGauge].self, from: data) else {
            return []
        }
        var seen = Set<String>()
        return sorted(decoded.compactMap { gauge in
            guard let siteID = normalizedSiteID(gauge.siteID), seen.insert(siteID).inserted else {
                return nil
            }
            return RiverGauge(
                siteId: siteID,
                name: gauge.name,
                latitude: gauge.latitude,
                longitude: gauge.longitude,
                enabled: true,
                suggested: gauge.suggested
            )
        })
    }

    private static func sorted(_ gauges: [RiverGauge]) -> [RiverGauge] {
        gauges.sorted {
            let comparison = $0.name.localizedCaseInsensitiveCompare($1.name)
            return comparison == .orderedSame ? $0.siteId < $1.siteId : comparison == .orderedAscending
        }
    }
}
