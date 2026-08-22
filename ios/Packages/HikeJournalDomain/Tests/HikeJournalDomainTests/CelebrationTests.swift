import XCTest
@testable import HikeJournalDomain

final class CelebrationTests: XCTestCase {
    func testFirstHikeUnlocksMilestoneCelebration() throws {
        let hike = fixtureHike("first", miles: 3.25, title: "Cypress Loop")

        let celebration = try XCTUnwrap(
            buildHikeMilestoneCelebration(
                previousHikes: [],
                updatedHikes: [hike],
                savedHike: hike
            )
        )

        XCTAssertEqual(celebration.kind, .milestone)
        XCTAssertEqual(celebration.title, "First hike logged!")
        XCTAssertEqual(celebration.badgeTitle, "First Footfall")
        XCTAssertEqual(celebration.highlights.first?.value, "1")
    }

    func testFirstConfirmedSpeciesCreatesDiscoveryCelebration() throws {
        let candidate = ReviewCandidate(
            taxonId: 47126,
            commonName: "Monarch",
            scientificName: "Danaus plexippus",
            confidence: 0.98,
            iconicTaxonName: "Insecta"
        )

        let celebration = try XCTUnwrap(
            buildConfirmedSpeciesCelebration(
                candidate: candidate,
                photo: fixturePhoto("monarch"),
                observedOn: "2026-08-05T10:00:00Z",
                existingSpecies: []
            )
        )

        XCTAssertEqual(celebration.kind, .discovery)
        XCTAssertEqual(celebration.title, "Monarch")
        XCTAssertEqual(celebration.highlights.last?.value, "Insects")
    }

    func testSpeciesSeenAfterSixtyDaysCreatesRediscoveryCelebration() throws {
        let existing = fixtureSpecies(
            47126,
            name: "Monarch",
            iconicTaxonName: "Insecta",
            encounterCount: 3,
            latestSeen: "2026-05-01T10:00:00Z"
        )
        let candidate = ReviewCandidate(
            taxonId: 47126,
            commonName: "Monarch",
            scientificName: "Danaus plexippus",
            confidence: 0.91,
            iconicTaxonName: "Insecta"
        )

        let celebration = try XCTUnwrap(
            buildConfirmedSpeciesCelebration(
                candidate: candidate,
                photo: fixturePhoto("monarch-return", takenAt: "2026-08-05T10:00:00Z"),
                observedOn: "2026-08-05T10:00:00Z",
                existingSpecies: [existing]
            )
        )

        XCTAssertEqual(celebration.kind, .rediscovery)
        XCTAssertEqual(celebration.highlights.last?.value, "4")
        XCTAssertTrue(celebration.detail.contains("96 days"))
    }
}
