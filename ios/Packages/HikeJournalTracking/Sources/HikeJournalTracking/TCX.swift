import Foundation

public enum TCXError: Error, Equatable, Sendable {
  case noUsableRouteSegments
  case invalidDistance
  case invalidCoordinate(sequence: Int64)
}

extension TCXError: LocalizedError {
  public var errorDescription: String? {
    switch self {
    case .noUsableRouteSegments:
      return "At least one route segment with two points is required for TCX."
    case .invalidDistance:
      return "The route distance is not valid for TCX."
    case .invalidCoordinate(let sequence):
      return "Tracking point \(sequence) has an invalid coordinate."
    }
  }
}

public enum TCXDocument {
  public static func render(
    snapshot: TrackingSnapshot,
    notes: String? = nil
  ) throws -> String {
    let usableSegments = snapshot.routeSegments.filter { $0.count >= 2 }
    guard !usableSegments.isEmpty else {
      throw TCXError.noUsableRouteSegments
    }
    guard snapshot.distanceMeters.isFinite, snapshot.distanceMeters >= 0 else {
      throw TCXError.invalidDistance
    }
    for point in usableSegments.joined() {
      guard point.latitude.isFinite,
        point.longitude.isFinite,
        (-90.0...90.0).contains(point.latitude),
        (-180.0...180.0).contains(point.longitude)
      else {
        throw TCXError.invalidCoordinate(sequence: point.sequence)
      }
    }

    var xml = ""
    xml += "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
    xml += "<TrainingCenterDatabase "
    xml += "xmlns=\"http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2\" "
    xml += "xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
    xml += "xsi:schemaLocation=\"http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 "
    xml += "http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd\">\n"
    xml += "  <Activities>\n"
    xml += "    <Activity Sport=\"Other\">\n"
    xml += "      <Id>\(utc(snapshot.startedAt))</Id>\n"
    xml += "      <Lap StartTime=\"\(utc(snapshot.startedAt))\">\n"
    xml += "        <TotalTimeSeconds>"
    xml += decimal(Double(max(0, snapshot.activeElapsedMilliseconds)) / 1_000)
    xml += "</TotalTimeSeconds>\n"
    xml += "        <DistanceMeters>\(decimal(snapshot.distanceMeters))</DistanceMeters>\n"
    xml += "        <Intensity>Active</Intensity>\n"
    for segment in usableSegments {
      xml += "        <Track>\n"
      for point in segment {
        xml += "          <Trackpoint>\n"
        xml += "            <Time>\(utc(point.timestamp))</Time>\n"
        xml += "            <Position>\n"
        xml += "              <LatitudeDegrees>\(decimal(point.latitude))</LatitudeDegrees>\n"
        xml += "              <LongitudeDegrees>\(decimal(point.longitude))</LongitudeDegrees>\n"
        xml += "            </Position>\n"
        if let altitude = point.altitudeMeters, altitude.isFinite {
          xml += "            <AltitudeMeters>\(decimal(altitude))</AltitudeMeters>\n"
        }
        xml += "          </Trackpoint>\n"
      }
      xml += "        </Track>\n"
    }
    xml += "        <TriggerMethod>Manual</TriggerMethod>\n"
    xml += "      </Lap>\n"
    if let notes, !notes.isEmpty {
      xml += "      <Notes>\(escapeXML(notes))</Notes>\n"
    }
    xml += "    </Activity>\n"
    xml += "  </Activities>\n"
    xml += "</TrainingCenterDatabase>\n"
    return xml
  }

  private static func utc(_ date: Date) -> String {
    let milliseconds = epochMilliseconds(date)
    var seconds = milliseconds / 1_000
    var remainder = milliseconds % 1_000
    if remainder < 0 {
      seconds -= 1
      remainder += 1_000
    }
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.calendar = Calendar(identifier: .gregorian)
    formatter.timeZone = TimeZone(secondsFromGMT: 0)
    formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
    let base = formatter.string(from: Date(timeIntervalSince1970: Double(seconds)))
    guard remainder != 0 else { return base + "Z" }
    return String(
      format: "%@.%03lldZ",
      locale: Locale(identifier: "en_US_POSIX"),
      base,
      remainder
    )
  }

  private static func decimal(_ value: Double) -> String {
    String(
      format: "%.6f",
      locale: Locale(identifier: "en_US_POSIX"),
      value
    )
  }

  private static func escapeXML(_ value: String) -> String {
    var xmlSafe = ""
    for scalar in value.unicodeScalars
    where scalar.value == 0x9 || scalar.value == 0xA || scalar.value == 0xD
      || (0x20...0xD7FF).contains(scalar.value)
      || (0xE000...0xFFFD).contains(scalar.value)
      || (0x10000...0x10FFFF).contains(scalar.value)
    {
      xmlSafe.unicodeScalars.append(scalar)
    }
    return
      xmlSafe
      .replacingOccurrences(of: "&", with: "&amp;")
      .replacingOccurrences(of: "<", with: "&lt;")
      .replacingOccurrences(of: ">", with: "&gt;")
      .replacingOccurrences(of: "\"", with: "&quot;")
      .replacingOccurrences(of: "'", with: "&apos;")
  }
}

public struct TCXWriter: Sendable {
  public let directoryURL: URL

  public init(directoryURL: URL) {
    self.directoryURL = directoryURL
  }

  @discardableResult
  public func write(
    snapshot: TrackingSnapshot,
    notes: String? = nil
  ) throws -> URL {
    guard isSafeFileComponent(snapshot.sessionID) else {
      throw TrackingCoreError.unsafeSessionIdentifier
    }
    let xml = try TCXDocument.render(snapshot: snapshot, notes: notes)
    try FileManager.default.createDirectory(
      at: directoryURL,
      withIntermediateDirectories: true
    )
    let destination =
      directoryURL
      .appendingPathComponent(snapshot.sessionID, isDirectory: false)
      .appendingPathExtension("tcx")
    try Data(xml.utf8).write(to: destination, options: .atomic)
    return destination
  }

  private func isSafeFileComponent(_ value: String) -> Bool {
    guard !value.isEmpty, value.count <= 160, value != ".", value != ".." else {
      return false
    }
    let allowed = CharacterSet.alphanumerics.union(
      CharacterSet(charactersIn: "-_")
    )
    return value.unicodeScalars.allSatisfy(allowed.contains)
  }
}
