import Foundation
import XCTest

@testable import HikeJournalTracking

final class TCXTests: XCTestCase {
  func testGoldenGarminTCXMatchesAndroidStructureExactly() throws {
    let rendered = try TCXDocument.render(snapshot: snapshot())
    let fixtureURL = try XCTUnwrap(
      Bundle.module.url(forResource: "golden-multisegment", withExtension: "tcx")
    )
    let expected = try String(contentsOf: fixtureURL, encoding: .utf8)

    XCTAssertEqual(rendered, expected)
    XCTAssertEqual(rendered.occurrences(of: "<Track>"), 2)
    XCTAssertEqual(rendered.occurrences(of: "<Trackpoint>"), 4)
    XCTAssertFalse(rendered.contains("1970-01-01T00:00:10Z"))
    XCTAssertTrue(rendered.contains("<Activity Sport=\"Other\">"))
    XCTAssertTrue(rendered.contains("TrainingCenterDatabase/v2"))
  }

  func testNotesAreEscapedAndDecimalsRemainPOSIXDeterministic() throws {
    let rendered = try TCXDocument.render(
      snapshot: snapshot(),
      notes: "Rock & <ridge> \"north\" 'loop'\u{1}"
    )

    XCTAssertTrue(
      rendered.contains(
        "<Notes>Rock &amp; &lt;ridge&gt; &quot;north&quot; &apos;loop&apos;</Notes>"
      )
    )
    XCTAssertTrue(rendered.contains("<DistanceMeters>42.500000</DistanceMeters>"))
    XCTAssertFalse(rendered.contains("42,500000"))
    XCTAssertEqual(rendered.occurrences(of: "<AltitudeMeters>"), 3)
  }

  func testRendererRequiresUsableSegmentAndValidCoordinates() {
    var value = snapshot()
    value = TrackingSnapshot(
      sessionID: value.sessionID,
      hikeID: value.hikeID,
      status: value.status,
      startedAt: value.startedAt,
      hikeDate: value.hikeDate,
      distanceMeters: value.distanceMeters,
      activeElapsedMilliseconds: value.activeElapsedMilliseconds,
      currentSegment: 0,
      routeSegments: [[point(sequence: 0, segment: 0, milliseconds: 0)]],
      lastAccuracyMeters: value.lastAccuracyMeters,
      lastFixTimestamp: value.lastFixTimestamp,
      pointCount: 1,
      generatedTCXPath: nil,
      recoveryReason: nil,
      errorMessage: nil
    )
    XCTAssertThrowsError(try TCXDocument.render(snapshot: value)) { error in
      XCTAssertEqual(error as? TCXError, .noUsableRouteSegments)
    }

    let invalid = TrackingPoint(
      sequence: 1,
      segment: 0,
      latitude: 91,
      longitude: 0,
      altitudeMeters: nil,
      accuracyMeters: 3,
      timestamp: Date(timeIntervalSince1970: 1),
      monotonicTimestampNanoseconds: nil,
      distanceFromPreviousMeters: 0
    )
    let invalidSnapshot = TrackingSnapshot(
      sessionID: value.sessionID,
      hikeID: value.hikeID,
      status: value.status,
      startedAt: value.startedAt,
      hikeDate: value.hikeDate,
      distanceMeters: value.distanceMeters,
      activeElapsedMilliseconds: value.activeElapsedMilliseconds,
      currentSegment: 0,
      routeSegments: [[point(sequence: 0, segment: 0, milliseconds: 0), invalid]],
      lastAccuracyMeters: 3,
      lastFixTimestamp: invalid.timestamp,
      pointCount: 2,
      generatedTCXPath: nil,
      recoveryReason: nil,
      errorMessage: nil
    )
    XCTAssertThrowsError(try TCXDocument.render(snapshot: invalidSnapshot)) { error in
      XCTAssertEqual(error as? TCXError, .invalidCoordinate(sequence: 1))
    }
  }

  func testWriterCreatesAtomicSessionFileAndRejectsTraversalIdentifier() throws {
    let directory = FileManager.default.temporaryDirectory
      .appendingPathComponent(UUID().uuidString, isDirectory: true)
    defer { try? FileManager.default.removeItem(at: directory) }
    let destination = try TCXWriter(directoryURL: directory).write(snapshot: snapshot())

    XCTAssertEqual(destination.lastPathComponent, "session.tcx")
    XCTAssertEqual(
      try String(contentsOf: destination, encoding: .utf8),
      try TCXDocument.render(snapshot: snapshot())
    )

    let safe = snapshot()
    let unsafe = TrackingSnapshot(
      sessionID: "../escape",
      hikeID: safe.hikeID,
      status: safe.status,
      startedAt: safe.startedAt,
      hikeDate: safe.hikeDate,
      distanceMeters: safe.distanceMeters,
      activeElapsedMilliseconds: safe.activeElapsedMilliseconds,
      currentSegment: safe.currentSegment,
      routeSegments: safe.routeSegments,
      lastAccuracyMeters: safe.lastAccuracyMeters,
      lastFixTimestamp: safe.lastFixTimestamp,
      pointCount: safe.pointCount,
      generatedTCXPath: nil,
      recoveryReason: nil,
      errorMessage: nil
    )
    XCTAssertThrowsError(try TCXWriter(directoryURL: directory).write(snapshot: unsafe)) { error in
      XCTAssertEqual(error as? TrackingCoreError, .unsafeSessionIdentifier)
    }
  }

  private func snapshot() -> TrackingSnapshot {
    TrackingSnapshot(
      sessionID: "session",
      hikeID: "hike & ridge",
      status: .finalizing,
      startedAt: Date(timeIntervalSince1970: 0),
      hikeDate: "1970-01-01",
      distanceMeters: 42.5,
      activeElapsedMilliseconds: 65_500,
      currentSegment: 2,
      routeSegments: [
        [
          point(sequence: 0, segment: 0, milliseconds: 0, altitude: 100),
          point(sequence: 1, segment: 0, milliseconds: 5_000, altitude: 100.5),
        ],
        [point(sequence: 2, segment: 1, milliseconds: 10_000, altitude: 99)],
        [
          point(sequence: 3, segment: 2, milliseconds: 15_000, altitude: 101.25),
          point(sequence: 4, segment: 2, milliseconds: 20_500, altitude: .nan),
        ],
      ],
      lastAccuracyMeters: 3,
      lastFixTimestamp: Date(timeIntervalSince1970: 20.5),
      pointCount: 5,
      generatedTCXPath: nil,
      recoveryReason: nil,
      errorMessage: nil
    )
  }

  private func point(
    sequence: Int64,
    segment: Int,
    milliseconds: Int64,
    altitude: Double? = 100
  ) -> TrackingPoint {
    TrackingPoint(
      sequence: sequence,
      segment: segment,
      latitude: 40 + Double(sequence) / 10_000,
      longitude: -74,
      altitudeMeters: altitude,
      accuracyMeters: 3,
      timestamp: Date(timeIntervalSince1970: Double(milliseconds) / 1_000),
      monotonicTimestampNanoseconds: milliseconds * 1_000_000,
      distanceFromPreviousMeters: sequence == 0 ? 0 : 10
    )
  }
}

extension String {
  fileprivate func occurrences(of needle: String) -> Int {
    components(separatedBy: needle).count - 1
  }
}
