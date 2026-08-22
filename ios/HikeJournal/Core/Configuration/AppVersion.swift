import Foundation

struct AppVersion: Equatable {
    let marketingVersion: String
    let buildNumber: String

    init(marketingVersion: String, buildNumber: String) {
        self.marketingVersion = marketingVersion
        self.buildNumber = buildNumber
    }

    init(bundle: Bundle) {
        marketingVersion = bundle.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.0.0"
        buildNumber = bundle.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "0"
    }

    var displayName: String {
        "Version \(marketingVersion) (\(buildNumber))"
    }

    static func isSemanticRelease(_ value: String) -> Bool {
        value.range(of: #"^[0-9]+\.[0-9]+\.[0-9]+$"#, options: .regularExpression) != nil
    }
}
