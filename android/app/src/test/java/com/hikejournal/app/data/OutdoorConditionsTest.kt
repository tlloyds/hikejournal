package com.hikejournal.app.data

import org.junit.Assert.assertEquals
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
}
