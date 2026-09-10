import XCTest
@testable import HikeJournalDomain

final class CelebrationTests: XCTestCase {
    func testBatchCelebrationUsesPhotosForPossibleNewSpecies() throws {
        let known = ReviewCandidate(
            taxonId: 1,
            commonName: "Known species",
            scientificName: "Species knownus",
            confidence: 0.95,
            iconicTaxonName: "Aves"
        )
        let newPlant = ReviewCandidate(
            taxonId: 2,
            commonName: "New plant",
            scientificName: "Plant newus",
            confidence: 0.95,
            iconicTaxonName: "Plantae"
        )
        let newInsect = ReviewCandidate(
            taxonId: 3,
            commonName: "New insect",
            scientificName: "Insect newus",
            confidence: 0.95,
            iconicTaxonName: "Insecta"
        )
        let items = [
            fixtureReviewItem("known", candidate: known),
            fixtureReviewItem("new-plant", candidate: newPlant),
            fixtureReviewItem("new-insect", candidate: newInsect),
        ]
        let status = ReviewBatchStatus(
            jobId: "batch-1",
            state: "completed",
            totalPhotos: items.count,
            processedCount: items.count,
            processedPhotoIds: items.map(\.id),
            currentPhotoNumber: items.count,
            currentPhotoId: nil,
            totalGroups: items.count,
            currentGroup: items.count,
            groupedCount: 0,
            individualCount: items.count,
            warnings: [],
            error: nil,
            items: items
        )

        let celebration = try XCTUnwrap(
            buildReviewBatchCelebration(status: status, existingSpecies: [fixtureSpecies(1, name: "Known species")])
        )

        XCTAssertEqual(
            celebration.imageUrls,
            ["https://example.test/new-plant.jpg", "https://example.test/new-insect.jpg"]
        )
    }

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
