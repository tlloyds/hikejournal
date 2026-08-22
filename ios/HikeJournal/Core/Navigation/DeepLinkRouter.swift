import Foundation

enum DeepLink: Equatable, Sendable {
    case hike(id: UUID)
    case inaturalist(status: INaturalistCallbackStatus, message: String?)
    case tracking(action: TrackingDeepLinkAction)
}

enum INaturalistCallbackStatus: Equatable, Sendable {
    case connected
    case error
    case cancelled
}

enum TrackingDeepLinkAction: String, Equatable, Sendable {
    case open
    case start
    case resume
    case pause
    case stop
}

struct DeepLinkRouter: Sendable {
    let callbackScheme: String

    init(callbackScheme: String = "hikejournal") {
        self.callbackScheme = callbackScheme.lowercased()
    }

    func destination(for url: URL) -> DeepLink? {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              components.scheme?.lowercased() == callbackScheme,
              components.user == nil,
              components.password == nil else {
            return nil
        }

        let host = components.host?.lowercased() ?? ""
        let pathComponents = components.path
            .split(separator: "/")
            .map(String.init)
        switch host {
        case "hike", "hikes":
            guard let rawID = pathComponents.first,
                  let id = UUID(uuidString: rawID) else { return nil }
            return .hike(id: id)
        case "inat", "inaturalist":
            return inaturalistDestination(components.queryItems ?? [])
        case "tracking", "record":
            let queryAction = components.queryItems?
                .first(where: { $0.name.caseInsensitiveCompare("action") == .orderedSame })?
                .value
            let rawAction = (queryAction ?? pathComponents.first ?? "open").lowercased()
            guard let action = TrackingDeepLinkAction(rawValue: rawAction) else { return nil }
            return .tracking(action: action)
        default:
            // Also accept path-style callbacks such as hikejournal:///hike/<uuid>.
            guard let first = pathComponents.first?.lowercased() else { return nil }
            let remaining = Array(pathComponents.dropFirst())
            switch first {
            case "hike", "hikes":
                guard let rawID = remaining.first,
                      let id = UUID(uuidString: rawID) else { return nil }
                return .hike(id: id)
            case "inat", "inaturalist":
                return inaturalistDestination(components.queryItems ?? [])
            case "tracking", "record":
                let rawAction = remaining.first?.lowercased() ?? "open"
                guard let action = TrackingDeepLinkAction(rawValue: rawAction) else { return nil }
                return .tracking(action: action)
            default:
                return nil
            }
        }
    }

    private func inaturalistDestination(_ items: [URLQueryItem]) -> DeepLink? {
        let statusValue = items
            .first(where: { $0.name.caseInsensitiveCompare("status") == .orderedSame })?
            .value?
            .lowercased()
        let status: INaturalistCallbackStatus
        switch statusValue {
        case "connected", "success": status = .connected
        case "error", "failed": status = .error
        case "cancelled", "canceled": status = .cancelled
        default: return nil
        }
        let message = items
            .first(where: { $0.name.caseInsensitiveCompare("message") == .orderedSame })?
            .value?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return .inaturalist(
            status: status,
            message: message?.isEmpty == false ? message : nil
        )
    }
}
