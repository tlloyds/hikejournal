import XCTest

@testable import HikeJournalTracking

final class MileAnnouncementTests: XCTestCase {
  func testNewSessionBaselinesCurrentDistanceWithoutRetroactiveSpeech() {
    var scheduler = WholeMileAnnouncementScheduler()

    XCTAssertNil(
      scheduler.update(
        sessionID: "restored-session",
        distanceMeters: 2.4 * WholeMileAnnouncementScheduler.metersPerMile,
        activeElapsedMilliseconds: 1
      )
    )
    XCTAssertEqual(scheduler.sessionID, "restored-session")
    XCTAssertEqual(scheduler.lastAnnouncedMile, 2)
  }

  func testAnnouncesExactWholeMileOnceWithAndroidMessageFormat() {
    var scheduler = WholeMileAnnouncementScheduler()
    _ = scheduler.update(
      sessionID: "session",
      distanceMeters: 0,
      activeElapsedMilliseconds: 0
    )
    let first = scheduler.update(
      sessionID: "session",
      distanceMeters: WholeMileAnnouncementScheduler.metersPerMile,
      activeElapsedMilliseconds: 3_725_999
    )

    XCTAssertEqual(first?.completedMiles, 1)
    XCTAssertEqual(first?.message, "1 mile complete. Total time: 1:02:05")
    XCTAssertEqual(first?.utteranceID, "hike-mile-1")
    XCTAssertNil(
      scheduler.update(
        sessionID: "session",
        distanceMeters: WholeMileAnnouncementScheduler.metersPerMile + 100,
        activeElapsedMilliseconds: 4_000_000
      )
    )
  }

  func testJumpAcrossMilesAnnouncesLatestCompletedMileAndPersistsIt() {
    var scheduler = WholeMileAnnouncementScheduler(sessionID: "session")
    let result = scheduler.update(
      sessionID: "session",
      distanceMeters: 3.2 * WholeMileAnnouncementScheduler.metersPerMile,
      activeElapsedMilliseconds: 65_500
    )

    XCTAssertEqual(result?.completedMiles, 3)
    XCTAssertEqual(result?.message, "3 miles complete. Total time: 01:05")
    XCTAssertEqual(scheduler.lastAnnouncedMile, 3)
  }

  func testInvalidOrNegativeDistancesNeverSchedule() {
    var scheduler = WholeMileAnnouncementScheduler(sessionID: "session")

    XCTAssertNil(
      scheduler.update(
        sessionID: "session",
        distanceMeters: -.infinity,
        activeElapsedMilliseconds: -1
      )
    )
    XCTAssertNil(
      scheduler.update(
        sessionID: "session",
        distanceMeters: .nan,
        activeElapsedMilliseconds: -1
      )
    )
    XCTAssertEqual(scheduler.lastAnnouncedMile, 0)
  }
}
