import XCTest
@testable import HikeJournalDomain

final class FilteringAndGroupingTests: XCTestCase {
    func testObservationFiltersUseIconicTaxonomy() {
        let species = [
            fixtureSpecies(nil, name: "Milkweed", iconicTaxonName: "Plantae"),
            fixtureSpecies(nil, name: "Wood stork", iconicTaxonName: "Aves"),
            fixtureSpecies(nil, name: "Bobcat", iconicTaxonName: "Mammalia"),
            fixtureSpecies(nil, name: "Monarch", iconicTaxonName: "Insecta"),
            fixtureSpecies(nil, name: "Slime mold", iconicTaxonName: "Protozoa"),
        ]

        XCTAssertEqual(filterSpeciesByObservationType(species, filter: .birds).map(\.commonName), ["Wood stork"])
        XCTAssertEqual(filterSpeciesByObservationType(species, filter: .plants).map(\.commonName), ["Milkweed"])
        XCTAssertEqual(
            filterSpeciesByObservationType(species, filter: .animals).map(\.commonName),
            ["Wood stork", "Bobcat", "Monarch"]
        )
        XCTAssertEqual(filterSpeciesByObservationType(species, filter: .otherLife).map(\.commonName), ["Slime mold"])
        XCTAssertEqual(ObservationTypeFilter.otherLife.label, "Other life")
    }

    func testSpeciesSearchMatchesWikipediaDescriptions() {
        let species = [
            fixtureSpecies(nil, name: "Ghost orchid", wikipediaSummary: "A rare orchid found in damp forests."),
            fixtureSpecies(nil, name: "Dune sunflower", wikipediaSummary: "A sandy coastal wildflower."),
            fixtureSpecies(nil, name: "Wood stork", wikipediaSummary: "A wading bird."),
        ]

        XCTAssertEqual(filterSpeciesBySearch(species, query: "orchid").map(\.commonName), ["Ghost orchid"])
        XCTAssertEqual(filterSpeciesBySearch(species, query: "SANDY").map(\.commonName), ["Dune sunflower"])
        XCTAssertEqual(filterSpeciesBySearch(species, query: " ").map(\.commonName), species.map(\.commonName))
    }

    func testSpeciesSortsAreDeterministicAcrossDatesAndOffsets() {
        let alphabetical = [
            fixtureSpecies(nil, name: "zebra longwing"),
            fixtureSpecies(nil, name: "Apple snail"),
            fixtureSpecies(nil, name: "anhinga"),
        ]
        XCTAssertEqual(
            sortSpeciesRecords(alphabetical, by: .alphabetical).map(\.commonName),
            ["anhinga", "Apple snail", "zebra longwing"]
        )

        let encountered = [
            fixtureSpecies(nil, name: "Zebra", encounterCount: 2),
            fixtureSpecies(nil, name: "Anhinga", encounterCount: 5),
            fixtureSpecies(nil, name: "Apple snail", encounterCount: 5),
        ]
        XCTAssertEqual(
            sortSpeciesRecords(encountered, by: .mostEncountered).map(\.commonName),
            ["Anhinga", "Apple snail", "Zebra"]
        )

        let recent = [
            fixtureSpecies(nil, name: "Local next day", latestSeen: "2026-07-30T00:30:00+02:00"),
            fixtureSpecies(nil, name: "Later UTC instant", latestSeen: "2026-07-29T23:00:00Z"),
            fixtureSpecies(nil, name: "Blank", latestSeen: " "),
            fixtureSpecies(nil, name: "Missing", latestSeen: nil),
        ]
        XCTAssertEqual(
            sortSpeciesRecords(recent, by: .mostRecent).map(\.commonName),
            ["Later UTC instant", "Local next day", "Blank", "Missing"]
        )
        XCTAssertEqual(
            latestObservedValue(["bad", "2026-01-01", "2026-01-02T01:00:00Z"]),
            "2026-01-02T01:00:00Z"
        )
    }

    func testHikeSelectionSearchSortsAndFormatsDates() {
        let hikes = [
            Hike(
                id: "older", title: "Éagle Ridge", hikeDate: "2025-03-02", distanceMiles: 1,
                locationName: "Pine Preserve", notes: "", isArchived: false,
                coverUrl: "", photoCount: 0, speciesCount: 0
            ),
            Hike(
                id: "newer", title: "Boardwalk", hikeDate: "2026-08-10", distanceMiles: 1,
                locationName: "Lettuce Lake", notes: "", isArchived: false,
                coverUrl: "", photoCount: 0, speciesCount: 0
            ),
        ]

        XCTAssertEqual(filterHikesForSelection(hikes, query: "").map(\.id), ["newer", "older"])
        XCTAssertEqual(filterHikesForSelection(hikes, query: "eagle").map(\.id), ["older"])
        XCTAssertEqual(filterHikesForSelection(hikes, query: "lettuce").map(\.id), ["newer"])
        XCTAssertEqual(formatHikeFilterDate("2026-08-10"), "Aug 10, 2026")
        XCTAssertEqual(formatHikeFilterDate("unknown"), "unknown")
    }

    func testReviewGroupingMatchesOutingTimeDistanceAndPhotoCap() {
        let base = [
            fixtureReviewItem("a", takenAt: "2026-08-05T10:00:00Z", latitude: 28.60000),
            fixtureReviewItem("b", takenAt: "2026-08-05T10:01:00Z", latitude: 28.60005),
            fixtureReviewItem("far", takenAt: "2026-08-05T10:01:00Z", latitude: 28.60100),
            fixtureReviewItem("other", takenAt: "2026-08-05T10:01:00Z", latitude: 28.60001, hikeId: "hike-2"),
        ]
        let groups = buildReviewPhotoGroups(base)

        XCTAssertEqual(groups.map(\.items.count), [2, 1, 1])
        XCTAssertEqual(groups.first?.photoIds, ["a", "b"])
        XCTAssertLessThanOrEqual(try XCTUnwrap(groups.first).maxDistanceMeters, 12)

        let nine = (0..<9).map {
            fixtureReviewItem("cap-\($0)", takenAt: "2026-08-05T10:00:0\($0)Z", latitude: 28.6)
        }
        XCTAssertEqual(buildReviewPhotoGroups(nine).map(\.items.count), [8, 1])
    }

    func testReviewGroupingKeepsMissingOrInvalidMetadataSeparateAndSplitsStably() {
        let items = [
            fixtureReviewItem("a", takenAt: "2026-08-05T10:00:00Z"),
            fixtureReviewItem("b", takenAt: "2026-08-05T10:01:00Z", latitude: 28.60005),
            fixtureReviewItem("no-time", takenAt: nil),
            fixtureReviewItem("bad-gps", takenAt: "2026-08-05T10:01:00Z", latitude: 100),
        ]
        let groups = buildReviewPhotoGroups(items)
        let split = splitReviewPhotoGroups(groups, separatePhotoIds: ["b"])

        XCTAssertEqual(groups.map(\.items.count), [2, 1, 1])
        XCTAssertEqual(split.flatMap(\.photoIds), ["a", "b", "bad-gps", "no-time"])
        XCTAssertTrue(groups.filter { $0.items.count == 1 }.allSatisfy { $0.timeSpanMinutes == 0 })
    }

    func testReviewPlanChunkingPreservesOrder() {
        let groups = (1...121).map { ["photo-\($0)"] }
        let chunks = chunkReviewBatchGroups(groups)

        XCTAssertEqual(chunks.map(\.count), [50, 50, 21])
        XCTAssertEqual(chunks.flatMap { $0 }, groups)
        XCTAssertEqual(chunkReviewBatchGroups([]), [])
    }

    func testPublishGroupingUsesSpeciesOutingTimeAndDistance() {
        let groups = buildPublishObservationGroups([
            fixturePublishItem("a", takenAt: "2026-08-05T10:00:00Z", latitude: 28.60000),
            fixturePublishItem("b", takenAt: "2026-08-05T10:08:00Z", latitude: 28.60020),
            fixturePublishItem("late", takenAt: "2026-08-05T10:16:00Z", latitude: 28.60000),
            fixturePublishItem("other", takenAt: "2026-08-05T10:01:00Z", latitude: 28.60001, taxonId: 200),
            fixturePublishItem("outing", takenAt: "2026-08-05T10:01:00Z", latitude: 28.60001, hikeId: "hike-2"),
        ])

        XCTAssertEqual(groups.map(\.items.count), [2, 1, 1, 1])
        XCTAssertEqual(groups.first?.observationIds, ["observation-a", "observation-b"])
        XCTAssertLessThan(try XCTUnwrap(groups.first).maxDistanceMeters, 50)
    }

    func testPublishSplitAndOversizedIndicatorAreDeterministic() {
        let items = (0..<9).map {
            fixturePublishItem("\($0)", takenAt: "2026-08-05T10:00:0\($0)Z", latitude: 28.6)
        }
        let proposed = buildPublishObservationGroups(items)
        let split = splitPublishObservationGroups(proposed, separatePhotoIds: ["photo-1"])

        XCTAssertEqual(proposed.count, 1)
        XCTAssertTrue(try XCTUnwrap(proposed.first).oversized)
        XCTAssertEqual(split.map(\.items.count), [8, 1])
        XCTAssertEqual(split.last?.photoIds, ["photo-1"])
    }

    func testConfidenceNormalizationClampsAndOmitsNonFinite() throws {
        XCTAssertEqual(try XCTUnwrap(normalizedReviewConfidence(97.9455)), 0.979455, accuracy: 0.000001)
        XCTAssertEqual(normalizedReviewConfidence(0.78), 0.78)
        XCTAssertEqual(normalizedReviewConfidence(-2), 0)
        XCTAssertEqual(normalizedReviewConfidence(250), 1)
        XCTAssertNil(normalizedReviewConfidence(.nan))
        XCTAssertNil(normalizedReviewConfidence(.infinity))
    }
}
