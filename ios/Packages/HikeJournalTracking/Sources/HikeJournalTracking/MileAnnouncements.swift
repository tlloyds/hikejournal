import Foundation

public struct MileAnnouncement: Codable, Equatable, Sendable {
  public let completedMiles: Int
  public let activeElapsedMilliseconds: Int64
  public let message: String
  public let utteranceID: String

  public init(completedMiles: Int, activeElapsedMilliseconds: Int64) {
    self.completedMiles = completedMiles
    self.activeElapsedMilliseconds = max(0, activeElapsedMilliseconds)
    let label = completedMiles == 1 ? "mile" : "miles"
    message =
      "\(completedMiles) \(label) complete. Total time: "
      + Self.formatElapsed(self.activeElapsedMilliseconds)
    utteranceID = "hike-mile-\(completedMiles)"
  }

  public static func formatElapsed(_ elapsedMilliseconds: Int64) -> String {
    let seconds = max(0, elapsedMilliseconds) / 1_000
    let hours = seconds / 3_600
    let minutes = (seconds % 3_600) / 60
    let remainingSeconds = seconds % 60
    if hours > 0 {
      return String(
        format: "%lld:%02lld:%02lld",
        locale: Locale(identifier: "en_US_POSIX"),
        hours,
        minutes,
        remainingSeconds
      )
    }
    return String(
      format: "%02lld:%02lld",
      locale: Locale(identifier: "en_US_POSIX"),
      minutes,
      remainingSeconds
    )
  }
}

/// Pure scheduling state. The UI/service decides whether and how to speak the
/// returned value; the completed mile is checkpointed even if speech is muted.
public struct WholeMileAnnouncementScheduler: Codable, Equatable, Sendable {
  public static let metersPerMile = 1_609.344

  public private(set) var sessionID: String?
  public private(set) var lastAnnouncedMile: Int

  public init(sessionID: String? = nil, lastAnnouncedMile: Int = 0) {
    self.sessionID = sessionID
    self.lastAnnouncedMile = max(0, lastAnnouncedMile)
  }

  public mutating func update(
    sessionID: String,
    distanceMeters: Double,
    activeElapsedMilliseconds: Int64
  ) -> MileAnnouncement? {
    let completedMiles = Self.completedMiles(for: distanceMeters)
    guard self.sessionID == sessionID else {
      self.sessionID = sessionID
      lastAnnouncedMile = completedMiles
      return nil
    }
    guard completedMiles > lastAnnouncedMile else { return nil }
    lastAnnouncedMile = completedMiles
    return MileAnnouncement(
      completedMiles: completedMiles,
      activeElapsedMilliseconds: activeElapsedMilliseconds
    )
  }

  private static func completedMiles(for distanceMeters: Double) -> Int {
    guard distanceMeters.isFinite, distanceMeters > 0 else { return 0 }
    let value = floor(distanceMeters / metersPerMile)
    if value >= Double(Int.max) { return Int.max }
    return max(0, Int(value))
  }
}
