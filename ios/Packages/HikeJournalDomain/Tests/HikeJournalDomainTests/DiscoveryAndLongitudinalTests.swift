import XCTest
@testable import HikeJournalDomain

final class DiscoveryAndLongitudinalTests: XCTestCase {
    func testNearbyResponsePreservesFrequencyAttributionProgressAndDefaults() throws {
        let nearby = try parseNearbySpecies(
            """
            {
              "area":{"id":"trail-1","name":"Florida Trail","lat":28.1,"lng":-81.5,"radius_km":10},
              "period":{"target_date":"2026-07-26","label":"Jun · Jul · Aug"},
              "filters":{"iconic_taxon":"Aves"},
              "source":{"from_cache":true,"guidance":"Reporting frequency is not a probability of encounter."},
              "data_density":{"level":"normal","message":""},
              "progress":{"collected_count":1,"total_count":2,"remaining_count":1},
              "taxa":[{
                "taxon_id":"123","common_name":"Florida Scrub-Jay",
                "scientific_name":"Aphelocoma coerulescens","iconic_taxon_name":"Aves",
                "observation_count":42,"nearby_rank":1,"frequency_band":"Often reported",
                "reference_photo":{"url":"https://example.test/jay.jpg","attribution":"© Naturalist","license_code":"cc-by"},
                "collected":false,"pending_credit":true
              }]
            }
            """
        )
        let defaulted = try parseNearbySpecies(#"{"source":{},"taxa":[{"taxon_id":1}]}"#)

        XCTAssertEqual(nearby.areaName, "Florida Trail")
        XCTAssertEqual(nearby.progress.collectedCount, 1)
        XCTAssertTrue(nearby.fromCache)
        XCTAssertEqual(nearby.taxa.first?.frequencyBand, "Often reported")
        XCTAssertEqual(nearby.taxa.first?.referencePhoto?.licenseCode, "cc-by")
        XCTAssertEqual(nearby.taxa.first?.id, 123)
        XCTAssertTrue(try XCTUnwrap(nearby.taxa.first).pendingCredit)
        XCTAssertEqual(defaulted.sourceGuidance, defaultReportingFrequencyGuidance)
        XCTAssertEqual(defaulted.taxa.first?.frequencyBand, defaultReportingFrequencyBand)
        XCTAssertFalse(defaulted.sourceGuidance.lowercased().contains("abundance"))
    }

    func testQuestResponsePreservesFrozenChecklistAndFocusOrder() throws {
        let quest = try parseFieldQuest(
            """
            {
              "id":"quest-1","title":"Wetland birds","status":"active","linked_hike_id":"hike-1",
              "area":{"id":"trail-1","name":"Lake Trail","radius_km":25},
              "period":{"target_date":"2026-07-26","label":"Jun · Jul · Aug"},
              "filters":{"iconic_taxon":"Aves"},
              "progress":{"collected_count":0,"total_count":1,"remaining_count":1},
              "taxa":[{"taxon_id":456,"common_name":"Limpkin","scientific_name":"Aramus guarauna",
                       "nearby_rank":3,"frequency_band":"Regularly reported","focus_order":1,
                       "collected":false,"pending_credit":false}]
            }
            """
        )

        XCTAssertEqual(quest.id, "quest-1")
        XCTAssertEqual(quest.linkedHikeId, "hike-1")
        XCTAssertEqual(quest.progress.totalCount, 1)
        XCTAssertEqual(quest.taxa.first?.focusOrder, 1)
        XCTAssertEqual(quest.iconicTaxon, "Aves")
    }

    func testQuestSightingsPreserveCoordinatesPrivacyAndMapGuidance() throws {
        let map = try parseQuestSightingsMap(
            """
            {
              "quest":{"id":"quest-1","title":"Summer lilies","area_name":"Florida Trail",
                       "lat":28.4985,"lng":-80.99675,"radius_km":10,"period_label":"Jun · Jul · Aug"},
              "taxon":{"taxon_id":163916,"common_name":"Alligator lily","scientific_name":"Hymenocallis palmeri"},
              "total_results":33,"mapped_count":1,"limited":false,"source":{},
              "sightings":[{"id":"384453204","lat":28.5692990957,"lng":-80.9994369018,
                            "observed_on":"2026-07-23","observer":"csoliz","uri":"https://example.test/observation",
                            "photo_url":"https://images.example/medium.jpg","positional_accuracy_m":14,"obscured":true}]
            }
            """
        )

        XCTAssertEqual(map.totalResults, 33)
        XCTAssertEqual(map.commonName, "Alligator lily")
        let firstSighting = try XCTUnwrap(map.sightings.first)
        XCTAssertEqual(firstSighting.latitude, 28.5692990957, accuracy: 0.0000001)
        XCTAssertEqual(firstSighting.positionalAccuracyMeters, 14)
        XCTAssertTrue(firstSighting.obscured)
        XCTAssertEqual(map.sourceGuidance, "Markers use locations iNaturalist makes public.")
    }

    func testFieldBriefingRetainsReasonsAndConvertsPreviewTaxon() throws {
        let briefing = try parseFieldBriefing(
            """
            {
              "area":{"id":"trail-1","name":"Florida Trail","lat":28.1,"lng":-82.2,"radius_km":10},
              "target_date":"2026-08-10","period":{"label":"Jul · Aug · Sep"},
              "guidance":"Reporting frequency is not encounter probability.",
              "sections":[{"title":"Worth watching for","items":[{
                "key":"taxon:123","taxon_id":123,"common_name":"Florida Scrub-Jay",
                "scientific_name":"Aphelocoma coerulescens","iconic_taxon_name":"Aves",
                "section":"Worth watching for","reasons":["Often reported here.","Seen last summer."],
                "nearby_rank":2,"frequency_band":"Often reported",
                "reference_photo":{"url":"https://example.test/jay.jpg","attribution":"© Naturalist","license_code":"cc-by"},
                "wikipedia_summary":"A Florida endemic bird.","collected":true,
                "collection_photo_url":"https://example.test/my-jay.jpg"
              }]}]
            }
            """
        )
        let item = try XCTUnwrap(briefing.sections.first?.items.first)
        let taxon = item.toDiscoveryTaxon()

        XCTAssertEqual(briefing.areaId, "trail-1")
        XCTAssertEqual(briefing.periodLabel, "Jul · Aug · Sep")
        XCTAssertEqual(item.referencePhotoAttribution, "© Naturalist")
        XCTAssertEqual(taxon.taxonId, 123)
        XCTAssertEqual(taxon.matchReason, "Often reported here.\n\nSeen last summer.")
        XCTAssertEqual(taxon.collectionPhotoUrl, "https://example.test/my-jay.jpg")
        XCTAssertTrue(taxon.collected)
    }

    func testPlaceProfileKeepsSummaryTaxaSeasonsVisitsAndRejectsInvalidCoordinates() throws {
        let profile = try parsePlaceProfile(
            """
            {
              "location":{"id":"place-1","name":"Oak Flat","lat":128.1,"lng":-182.2},
              "summary":{"first_visit":"2024-02-01","latest_visit":"2026-02-01","outing_count":2,
                         "total_distance_miles":5.5,"total_duration_seconds":7200,"observation_count":4,"species_count":3},
              "taxon_counts":[{"name":"Plantae","count":2}],
              "taxon_groups":[{"name":"Plantae","count":2,"species":[{
                "key":"taxon:1","taxon_id":1,"common_name":"Pink sundew",
                "scientific_name":"Drosera capillaris","iconic_taxon_name":"Plantae",
                "encounter_count":3,"reference_photo_url":"https://example.test/sundew.jpg"
              }]}],
              "seasonal_history":{"observation_count":4,"months":[{"month":2,"label":"Feb","count":4,"relative_intensity":1}],"years":[]},
              "visits":[{"hike_id":"hike-2","title":"Return","hike_date":"2026-02-01","distance_miles":3,
                         "observation_count":2,"species_count":2,"new_species_count":1,"cumulative_species_count":3}],
              "guidance":"Your records.","live_conditions_notice":"Live conditions may differ."
            }
            """
        )

        XCTAssertEqual(profile.name, "Oak Flat")
        XCTAssertNil(profile.latitude)
        XCTAssertNil(profile.longitude)
        XCTAssertEqual(profile.speciesCount, 3)
        XCTAssertEqual(profile.taxonCounts, [TaxonCount(name: "Plantae", count: 2)])
        XCTAssertEqual(profile.seasonalHistory.months.first?.count, 4)
        XCTAssertEqual(profile.visits.first?.cumulativeSpeciesCount, 3)
        XCTAssertEqual(profile.taxonGroups.first?.species.first?.referencePhotoUrl, "https://example.test/sundew.jpg")
        XCTAssertEqual(profile.liveConditionsNotice, "Live conditions may differ.")
    }

    func testComparisonRetainsSpeciesImagesAndOneSidedWeather() throws {
        let comparison = try parseHikeComparison(
            """
            {
              "hike_a":{"id":"a","hike_date":"2026-08-09"},"hike_b":{"id":"b","hike_date":"2025-08-09"},
              "species":{"shared":[{"key":"taxon:1","taxon_id":1,"common_name":"Sundew",
                                     "reference_photo_url":"https://example.test/sundew.jpg"}],"only_a":[],"only_b":[]},
              "weather":{"hike_a":{"provider":"open-meteo","condition_label":"Overcast","temperature_mean_c":27},"hike_b":null},
              "guidance":"Compare like seasons."
            }
            """
        )

        XCTAssertEqual(comparison.hikeA.id, "a")
        XCTAssertEqual(comparison.shared.first?.referencePhotoUrl, "https://example.test/sundew.jpg")
        XCTAssertEqual(comparison.weatherA?.conditionLabel, "Overcast")
        XCTAssertNil(comparison.weatherB)
    }

    func testDiscoveryAreaSearchIsStableLimitedAndDiacriticInsensitive() {
        let areas = [
            DiscoveryArea(id: "1", name: "Alafía River", latitude: 27.8, longitude: -82.1, locationType: "saved"),
            DiscoveryArea(id: "2", name: "Lettuce Lake", latitude: 28.1, longitude: -82.4, locationType: "saved"),
            DiscoveryArea(id: "3", name: "Florida Trail", latitude: 28.2, longitude: -81.7, locationType: "saved"),
        ]

        XCTAssertEqual(filterDiscoveryAreas(areas, query: "").map(\.id), ["1", "2", "3"])
        XCTAssertEqual(filterDiscoveryAreas(areas, query: "alafia").map(\.id), ["1"])
        XCTAssertEqual(filterDiscoveryAreas(areas, query: "", limit: 2).map(\.id), ["1", "2"])
        XCTAssertEqual(roundedDiscoveryCoordinate(28.53831), 28.54, accuracy: 0.000001)
        XCTAssertEqual(roundedDiscoveryCoordinate(-81.37924), -81.38, accuracy: 0.000001)
    }

    func testQuestFocusSelectionIsOrderedCappedAndFilteredToNearbyTaxa() {
        var selected = toggleQuestFocus([], taxonID: 101)
        selected = toggleQuestFocus(selected, taxonID: 202)
        selected = toggleQuestFocus(selected, taxonID: 101)

        let available = (1...12).map { fixtureDiscoveryTaxon(Int64($0)) }
        let normalized = normalizeQuestFocusTaxonIDs(
            [202, 999, 202, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            availableTaxa: available
        )

        XCTAssertEqual(selected, [202])
        XCTAssertEqual(normalized, [3, 4, 5, 6, 7, 8, 9, 10, 11])
        XCTAssertEqual(questTargetPrompt(selectedCount: 0), "Pick at least 1")
        XCTAssertEqual(questTargetPrompt(selectedCount: 1), "Save quest")
    }
}
