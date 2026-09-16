import Foundation

public struct MileAnnouncement: Codable, Equatable, Sendable {
  public let completedMiles: Int
  public let activeElapsedMilliseconds: Int64
  public let lastMileElapsedMilliseconds: Int64
  public let message: String
  public let utteranceID: String

  public init(
    completedMiles: Int,
    activeElapsedMilliseconds: Int64,
    lastMileElapsedMilliseconds: Int64
  ) {
    self.completedMiles = completedMiles
    self.activeElapsedMilliseconds = max(0, activeElapsedMilliseconds)
    self.lastMileElapsedMilliseconds = max(0, lastMileElapsedMilliseconds)
    let label = completedMiles == 1 ? "mile" : "miles"
    message =
      "Total distance \(completedMiles) \(label). Total time "
      + Self.formatSpeechElapsed(self.activeElapsedMilliseconds)
      + ". Last mile time "
      + Self.formatSpeechElapsed(self.lastMileElapsedMilliseconds)
      + "."
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

  public static func formatSpeechElapsed(_ elapsedMilliseconds: Int64) -> String {
    let seconds = max(0, elapsedMilliseconds) / 1_000
    let hours = seconds / 3_600
    let minutes = (seconds % 3_600) / 60
    let remainingSeconds = seconds % 60
    var parts: [String] = []
    if hours > 0 {
      parts.append("\(hours) \(hours == 1 ? "hour" : "hours")")
    }
    if minutes > 0 {
      parts.append("\(minutes) \(minutes == 1 ? "minute" : "minutes")")
    }
    if hours == 0 && minutes == 0 {
      parts.append("\(remainingSeconds) \(remainingSeconds == 1 ? "second" : "seconds")")
    }
    return parts.joined(separator: " ")
  }
}

/// Pure scheduling state. The UI/service decides whether and how to speak the
/// returned value; the completed mile is checkpointed even if speech is muted.
public struct WholeMileAnnouncementScheduler: Codable, Equatable, Sendable {
  public static let metersPerMile = 1_609.344

  public private(set) var sessionID: String?
  public private(set) var lastAnnouncedMile: Int
  public private(set) var lastAnnouncedElapsedMilliseconds: Int64

  public init(
    sessionID: String? = nil,
    lastAnnouncedMile: Int = 0,
    lastAnnouncedElapsedMilliseconds: Int64 = 0
  ) {
    self.sessionID = sessionID
    self.lastAnnouncedMile = max(0, lastAnnouncedMile)
    self.lastAnnouncedElapsedMilliseconds = max(0, lastAnnouncedElapsedMilliseconds)
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
      lastAnnouncedElapsedMilliseconds = completedMiles > 0
        ? max(0, activeElapsedMilliseconds)
        : 0
      return nil
    }
    guard completedMiles > lastAnnouncedMile else { return nil }
    lastAnnouncedMile = completedMiles
    let elapsed = max(0, activeElapsedMilliseconds)
    let lastMileElapsed = max(0, elapsed - lastAnnouncedElapsedMilliseconds)
    lastAnnouncedElapsedMilliseconds = elapsed
    return MileAnnouncement(
      completedMiles: completedMiles,
      activeElapsedMilliseconds: elapsed,
      lastMileElapsedMilliseconds: lastMileElapsed
    )
  }

  private static func completedMiles(for distanceMeters: Double) -> Int {
    guard distanceMeters.isFinite, distanceMeters > 0 else { return 0 }
    let value = floor(distanceMeters / metersPerMile)
    if value >= Double(Int.max) { return Int.max }
    return max(0, Int(value))
  }
}
