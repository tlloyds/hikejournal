import Foundation
import XCTest
@testable import HikeJournalDomain

final class ModelFixtureTests: XCTestCase {
    func testHikePreservesRouteEverydayCoverFieldMarksAndWeather() throws {
        let hike = try parseHike(
            """
            {
              "id":"everyday",
              "title":"Everyday sightings",
              "started_at":"2026-08-01T12:00:00Z",
              "duration_seconds":"3723",
              "is_standalone":true,
              "cover_photo_id":"photo-1",
              "route_segments":[
                [{"lat":28.1,"lng":-82.1},{"lat":28.2,"lng":-82.2}],
                [{"lat":28.3,"lng":-82.3}]
              ],
              "field_marks":[{
                "id":"mark-1","hike_id":"everyday","marked_at":"2026-08-01T12:05:00Z",
                "lat":28.15,"lng":-82.15,"mark_type":"wildlife","note":"Owl"
              }],
              "weather":{"provider":"open-meteo","temperature_max_c":"29.0","condition_label":"Rain"}
            }
            """
        )

        XCTAssertTrue(hike.isStandalone)
        XCTAssertEqual(hike.coverPhotoId, "photo-1")
        XCTAssertEqual(hike.durationSeconds, 3_723)
        XCTAssertEqual(hike.routeStartedAt, "2026-08-01T12:00:00Z")
        XCTAssertEqual(hike.routeSegments.count, 1)
        XCTAssertEqual(hike.routeSegments[0].last?.longitude, -82.2)
        XCTAssertEqual(hike.fieldMarks.first?.markType, "wildlife")
        XCTAssertEqual(hike.weather?.conditionLabel, "Rain")
        XCTAssertEqual(hike.weather?.temperatureMaxC, 29)
    }

    func testMapRoutesRetainIdentityAndDiscardOnePointSegments() throws {
        let routes = try parseMapRoutes(
            """
            [
              {"hike_id":"hike-1","route_segments":[[{"lat":1,"lng":2},{"lat":3,"lng":4}]]},
              {"hike_id":"hike-2","route_segments":[[{"lat":5,"lng":6}], [{"lat":7,"lng":8},{"lat":9,"lng":10}]]}
            ]
            """
        )

        XCTAssertEqual(routes.map(\.hikeId), ["hike-1", "hike-2"])
        XCTAssertEqual(routes[1].segments.count, 1)
        XCTAssertEqual(try parseMapRouteSegments(
            #"[{"hike_id":"a","route_segments":[[{"lat":1,"lng":2},{"lat":3,"lng":4}]]}]"#
        ).count, 1)
    }

    func testPhotoParsesMixedPhenophasesHistoryAndMarkup() throws {
        let photo = try HikeJournalDomainJSON.decode(
            Photo.self,
            from: """
            {
              "id":"photo-1","hike_id":"hike-1","url":"https://example.test/photo.jpg",
              "species":[{
                "common_name":"Maid Marian","scientific_name":"Rhexia nashii","is_primary":"yes",
                "taxon_id":"123","wikipedia_summary":"<i><b>Maid Marian</b></i> &amp; a wetland plant",
                "phenophases":["flowering",{"code":"fruiting"},{"code":""}],
                "identification_history":[{
                  "id":"event-1","common_name":"Maid Marian","scientific_name":"Rhexia nashii",
                  "source":"inat","confidence":"confirmed","became_current":1
                }]
              }]
            }
            """
        )

        let label = try XCTUnwrap(photo.species.first)
        XCTAssertTrue(label.isPrimary)
        XCTAssertEqual(label.taxonId, 123)
        XCTAssertEqual(label.phenophases, ["flowering", "fruiting"])
        XCTAssertEqual(label.wikipediaSummary, "Maid Marian & a wetland plant")
        XCTAssertEqual(label.identificationHistory.first?.becameCurrent, true)
        XCTAssertEqual(label.identificationHistory.first?.actor, "")
    }

    func testPhotoRoundTripUsesServerSnakeCase() throws {
        let original = fixturePhoto("photo-1")
        let data = try HikeJournalDomainJSON.encode(original)
        let json = try XCTUnwrap(String(data: data, encoding: .utf8))
        let decoded = try HikeJournalDomainJSON.decode(Photo.self, from: data)

        XCTAssertTrue(json.contains("\"hike_id\""))
        XCTAssertTrue(json.contains("\"processing_status\""))
        XCTAssertEqual(decoded, original)
    }

    func testLocationsFilterEmptyRowsNormalizeStatesAndRejectInvalidGPS() throws {
        let locations = try parseHikeLocations(
            """
            [
              {"id":"location-1","name":"Alafia Scrub Preserve","lat":27.8609,"lng":-82.3359,"state":"fl"},
              {"id":"bad-gps","name":"Somewhere","lat":91,"lng":-181,"state":"DC"},
              {"id":"","name":"Ignored"}
            ]
            """
        )

        XCTAssertEqual(locations.count, 2)
        XCTAssertEqual(locations[0].stateCode, "FL")
        XCTAssertNil(locations[1].latitude)
        XCTAssertNil(locations[1].longitude)
        XCTAssertNil(locations[1].stateCode)
        XCTAssertEqual(normalizeUSStateCode("me"), "ME")
        XCTAssertEqual(usStateCode(forName: "Maine"), "ME")
    }

    func testSeasonalSpeciesEncounterAndSightingFixtures() throws {
        let species = try parseSpecies(
            """
            {
              "key":"taxon:1","taxon_id":1,"common_name":"Sundew","scientific_name":"Drosera capillaris",
              "wikipedia_summary":"<b>A sundew</b>","encounter_count":2,"hike_count":1,
              "hike_ids":["hike-1"],"hike_encounter_counts":{"hike-1":2},
              "latest_seen":"2026-08-01","cover_url":"https://example.test/sundew.jpg",
              "seasonal_history":{"observation_count":2,"months":[{"label":"Aug","count":2,"relative_intensity":1}],"years":[{"year":2026,"first_observed_on":"2026-08-01","last_observed_on":"2026-08-02","observation_count":2}]},
              "encounters":[{"photo":{"id":"p","url":"u"},"hike_id":"hike-1","observed_on":"2026-08-01"}]
            }
            """
        )
        let sightings = try parseSightings(
            #"[{"id":"s","lat":28.1,"lng":-82.1,"species_name":"Sundew","confirmed":true}]"#
        )

        XCTAssertEqual(species.wikipediaSummary, "A sundew")
        XCTAssertEqual(species.seasonalHistory.months.first?.month, 1)
        XCTAssertEqual(species.encounters.first?.hikeTitle, "Everyday sighting")
        XCTAssertEqual(sightings.first?.hikeTitle, "Everyday sighting")
        XCTAssertTrue(try XCTUnwrap(sightings.first).confirmed)
    }

    func testWorkflowParsersDefaultMissingFieldsAndCoerceScalars() throws {
        let review = try parseReviewBatchStatus(
            #"{"job_id":99,"processed_photo_ids":["a","b"]}"#
        )
        let publish = try parsePublishBatchStatus(
            #"{"job_id":"publish-1","posted_group_count":"2","processed_photo_ids":["p"]}"#
        )
        let queue = try parsePublishQueue(
            #"{"connected":"true","counts":{"ready":"3","needs_attention":1,"posted":2}}"#
        )

        XCTAssertEqual(review.jobId, "99")
        XCTAssertEqual(review.processedCount, 2)
        XCTAssertEqual(review.state, "queued")
        XCTAssertEqual(publish.postedGroupCount, 2)
        XCTAssertEqual(queue.readyCount, 3)
        XCTAssertTrue(queue.connected)
        XCTAssertTrue(queue.items.isEmpty)
    }

    func testForecastRiverMediaAndLoadResultValueSemantics() throws {
        let forecast = try HikeJournalDomainJSON.decode(
            PlaceForecast.self,
            from: """
            {"timezone":"America/New_York","temperature_f":"77.5","condition_label":"Clear",
             "days":[{"date":"2026-08-10","temperature_max_f":88,"uv_index_max":7}],
             "planning_notes":["Bring water."]}
            """
        )
        let river = RiverGaugeSeries(
            gauge: RiverGauge(siteId: "1", name: "River", latitude: 28, longitude: -82),
            periodDays: 2,
            readings: [
                RiverGaugeReading(observedAt: "a", heightFeet: 4, provisional: false),
                RiverGaugeReading(observedAt: "b", heightFeet: 5.5, provisional: true),
            ]
        )
        let media = MediaLocationSummary(totalCount: 3, geotaggedCount: 1)
        let loaded = LoadResult(value: forecast, fromCache: true)

        XCTAssertEqual(forecast.temperatureF, 77.5)
        XCTAssertEqual(forecast.days.first?.uvIndexMax, 7)
        XCTAssertEqual(river.minimumHeightFeet, 4)
        XCTAssertEqual(river.maximumHeightFeet, 5.5)
        XCTAssertEqual(river.changeFeet, 1.5)
        XCTAssertEqual(media.missingCount, 2)
        XCTAssertFalse(media.allGeotagged)
        XCTAssertTrue(loaded.fromCache)
    }

    func testFailClosedEnumsRejectUnknownValues() throws {
        XCTAssertThrowsError(try HikeJournalDomainJSON.decode(SpeciesSort.self, from: "\"NewestFirst\""))
        XCTAssertThrowsError(try HikeJournalDomainJSON.decode(BadgeMetric.self, from: "\"FutureMetric\""))
        XCTAssertThrowsError(try HikeJournalDomainJSON.decode(CelebrationKind.self, from: "\"Surprise\""))
        XCTAssertEqual(
            try HikeJournalDomainJSON.decode(ObservationTypeFilter.self, from: "\"Birds\""),
            .birds
        )
    }

    func testMalformedTopLevelJSONThrows() {
        XCTAssertThrowsError(try parseHike("not-json"))
        XCTAssertThrowsError(try parseSpeciesList("{}"))
    }
}
