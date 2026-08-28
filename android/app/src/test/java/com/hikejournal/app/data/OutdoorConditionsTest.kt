package com.hikejournal.app.data

import java.time.Instant
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class OutdoorConditionsTest {
    @Test
    fun `forecast parser keeps current planning signals and daily outlook`() {
        val forecast = parsePlaceForecast(
            """
            {
              "timezone":"America/New_York",
              "current":{"time":"2026-08-12T09:00","temperature_2m":82.0,"apparent_temperature":91.0,"relative_humidity_2m":81,"weather_code":2,"cloud_cover":34,"wind_speed_10m":6.0,"wind_gusts_10m":15.0},
              "daily":{"time":["2026-08-12","2026-08-13"],"weather_code":[95,3],"temperature_2m_max":[94.0,90.0],"temperature_2m_min":[77.0,75.0],"apparent_temperature_max":[105.0,96.0],"precipitation_probability_max":[65,20],"precipitation_sum":[0.8,0.0],"wind_speed_10m_max":[12,8],"wind_gusts_10m_max":[28,16],"uv_index_max":[9.2,6.0],"sunrise":["2026-08-12T06:52","2026-08-13T06:53"],"sunset":["2026-08-12T20:07","2026-08-13T20:06"]}
            }
            """.trimIndent(),
        )

        assertEquals("Partly cloudy", forecast.conditionLabel)
        assertEquals(2, forecast.days.size)
        assertEquals("Thunderstorms", forecast.days.first().conditionLabel)
        assertEquals(94.0, forecast.days.first().temperatureMaxF!!, 0.001)
        assertTrue(forecast.planningNotes.any { it.contains("feels-like") })
        assertTrue(forecast.planningNotes.any { it.contains("Rain") })
    }

    @Test
    fun `place conditions parser accepts the shared backend response`() {
        val conditions = parsePlaceConditions(
            """
            {
              "forecast": {
                "observed_at":"2026-08-12T09:00",
                "timezone":"America/New_York",
                "temperature_f":82.0,
                "apparent_temperature_f":91.0,
                "relative_humidity_percent":81,
                "precipitation_inches":0.0,
                "cloud_cover_percent":34,
                "wind_speed_mph":6.0,
                "wind_gust_mph":15.0,
                "condition_label":"Partly cloudy",
                "days":[{"date":"2026-08-12","condition_label":"Thunderstorms","temperature_max_f":94.0,"temperature_min_f":77.0,"apparent_temperature_max_f":105.0,"precipitation_probability_percent":65,"precipitation_total_inches":0.8,"wind_speed_max_mph":12.0,"wind_gust_max_mph":28.0,"uv_index_max":9.2,"sunrise":"2026-08-12T06:52","sunset":"2026-08-12T20:07"}],
                "planning_notes":["Plan a cooler, earlier outing: the peak feels-like temperature is near 105°F."]
              },
              "river_gauges":[{
                "gauge":{"site_id":"USGS-02233484","name":"Econ River","lat":28.65,"lng":-81.17,"enabled":true,"suggested":true},
                "period_days":7,
                "readings":[{"observed_at":"2026-08-11T12:30:00+00:00","height_feet":13.20,"provisional":true},{"observed_at":"2026-08-12T12:30:00+00:00","height_feet":14.64,"provisional":true}],
                "distance_miles":2.5,
                "error_message":null
              }],
              "live_conditions_notice":null
            }
            """.trimIndent(),
        )

        assertEquals("America/New_York", conditions.forecast?.timezone)
        assertEquals("Partly cloudy", conditions.forecast?.conditionLabel)
        assertEquals(82.0, conditions.forecast?.temperatureF!!, 0.001)
        assertEquals("Thunderstorms", conditions.forecast?.days?.first()?.conditionLabel)
        assertEquals(9.2, conditions.forecast?.days?.first()?.uvIndexMax!!, 0.001)
        assertEquals(1, conditions.forecast?.planningNotes?.size)
        assertEquals(1, conditions.riverGauges.size)
        assertEquals("USGS-02233484", conditions.riverGauges.first().gauge.siteId)
        assertEquals(14.64, conditions.riverGauges.first().currentHeightFeet!!, 0.001)
        assertEquals(1.44, conditions.riverGauges.first().changeFeet!!, 0.001)
        assertNull(conditions.riverGauges.first().errorMessage)
    }

    @Test
    fun `river parser chooses the populated series and orders readings`() {
        val gauge = RiverGauge("USGS-02233484", "Econ River", 28.65, -81.17, enabled = true)
        val series = parseRiverGaugeSeries(
            json = """
                {"features":[
                  {"properties":{"time_series_id":"primary","time":"2026-08-12T12:30:00+00:00","value":"14.64","approval_status":"Provisional"}},
                  {"properties":{"time_series_id":"primary","time":"2026-08-11T12:30:00+00:00","value":"13.20","approval_status":"Approved"}},
                  {"properties":{"time_series_id":"secondary","time":"2026-08-12T12:30:00+00:00","value":"1.0","approval_status":"Approved"}}
                ]}
            """.trimIndent(),
            gauge = gauge,
            periodDays = 7,
            placeLatitude = 28.70,
            placeLongitude = -81.10,
        )

        assertEquals(2, series.readings.size)
        assertEquals(13.20, series.readings.first().heightFeet, 0.001)
        assertEquals(14.64, series.currentHeightFeet!!, 0.001)
        assertEquals(1.44, series.changeFeet!!, 0.001)
        assertTrue(series.distanceMiles!! > 0)
        assertTrue(series.readings.last().provisional)
    }

    @Test
    fun `USGS station input accepts site numbers and monitoring links`() {
        assertEquals("USGS-02233484", normalizeUsgsSiteId("02233484"))
        assertEquals("USGS-02233484", normalizeUsgsSiteId("usgs-02233484"))
        assertEquals(
            "USGS-02233484",
            normalizeUsgsSiteId("https://waterdata.usgs.gov/monitoring-location/USGS-02233484/#data"),
        )
        assertEquals(null, normalizeUsgsSiteId("river by my house"))
    }

    @Test
    fun `USGS metadata parser keeps station name and coordinates`() {
        val gauge = parseRiverGaugeMetadata(
            """
            {"features":[{"properties":{"id":"USGS-02234000","monitoring_location_name":"ST. JOHNS RIVER ABOVE LAKE HARNEY NEAR GENEVA, FL"},"id":"USGS-02234000","geometry":{"type":"Point","coordinates":[-81.0353,28.7142]}}]}
            """.trimIndent(),
            "USGS-02234000",
        )

        assertEquals("St. Johns River above Lake Harney near Geneva", gauge.name)
        assertEquals(28.7142, gauge.latitude, 0.0001)
    }

    @Test
    fun `nearby USGS search keeps recent gage height stations and sorts by distance`() {
        val results = parseNearbyRiverGauges(
            latestJson = """
                {"features":[
                  {"properties":{"monitoring_location_id":"USGS-02234000","time":"2026-08-12T14:30:00Z","value":"2.31","unit_of_measure":"ft","approval_status":"Provisional"},"geometry":{"type":"Point","coordinates":[-81.0353,28.7142]}},
                  {"properties":{"monitoring_location_id":"USGS-02233500","time":"2026-08-12T14:45:00Z","value":"4.66","unit_of_measure":"ft","approval_status":"Approved"},"geometry":{"type":"Point","coordinates":[-81.1142,28.6778]}},
                  {"properties":{"monitoring_location_id":"USGS-OLD","time":"2025-08-12T14:45:00Z","value":"9.99","unit_of_measure":"ft","approval_status":"Approved"},"geometry":{"type":"Point","coordinates":[-81.11,28.68]}}
                ]}
            """.trimIndent(),
            metadataJson = """
                {"features":[
                  {"properties":{"id":"USGS-02234000","monitoring_location_name":"ST. JOHNS RIVER ABOVE LAKE HARNEY NEAR GENEVA, FL"}},
                  {"properties":{"id":"USGS-02233500","monitoring_location_name":"ECONLOCKHATCHEE RIVER NEAR CHULUOTA, FL"}}
                ]}
            """.trimIndent(),
            originLatitude = 28.68,
            originLongitude = -81.12,
            now = Instant.parse("2026-08-12T15:00:00Z"),
        )

        assertEquals(2, results.size)
        assertEquals("USGS-02233500", results.first().gauge.siteId)
        assertEquals("Econlockhatchee River near Chuluota", results.first().gauge.name)
        assertEquals(4.66, results.first().currentHeightFeet, 0.001)
        assertTrue(results.first().distanceMiles < results.last().distanceMiles)
    }

    @Test
    fun `relevant water gauges prefer nearby stations and omit distant followed gauges`() {
        val nearby = listOf(
            NearbyRiverGauge(
                gauge = RiverGauge("USGS-NEAR", "Nearby Lake", 44.81, -92.70),
                distanceMiles = 2.0,
                currentHeightFeet = 4.2,
                observedAt = "2026-08-12T14:45:00Z",
                provisional = false,
            ),
        )
        val followed = listOf(
            RiverGauge("USGS-FOLLOWED-MN", "Followed Creek", 44.82, -92.71, enabled = true),
            RiverGauge("USGS-FOLLOWED-FL", "Econlockhatchee River", 28.65, -81.17, enabled = true),
        )

        val selected = selectRelevantWaterGauges(
            nearby = nearby,
            followed = followed,
            originLatitude = 44.80,
            originLongitude = -92.70,
        )

        assertEquals(
            listOf("USGS-NEAR", "USGS-FOLLOWED-MN"),
            selected.map(RiverGauge::siteId),
        )
    }
}
