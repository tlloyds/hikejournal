package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class HikeMapParserTest {
    @Test
    fun `hike detail preserves route segments for the native map`() {
        val hike = parseHike(
            """
            {
              "id":"hike-1",
              "title":"Pine Loop",
              "started_at":"2026-08-01T12:00:00Z",
              "duration_seconds":3723,
              "photos":[],
              "route_segments":[
                [{"lat":28.1,"lng":-82.1},{"lat":28.2,"lng":-82.2}],
                [{"lat":28.3,"lng":-82.3}]
              ]
            }
            """.trimIndent(),
        )

        assertEquals(1, hike.routeSegments.size)
        assertEquals(28.1, hike.routeSegments.single().first().latitude, 0.000001)
        assertEquals(-82.2, hike.routeSegments.single().last().longitude, 0.000001)
        assertEquals(3723L, hike.durationSeconds)
        assertEquals("2026-08-01T12:00:00Z", hike.routeStartedAt)
    }

    @Test
    fun `hike parser preserves everyday and cover metadata`() {
        val hike = parseHike(
            """
            {
              "id":"everyday",
              "title":"Everyday sightings",
              "is_standalone":true,
              "cover_photo_id":"photo-1",
              "cover_url":"https://example.test/photo-1.jpg",
              "photos":[]
            }
            """.trimIndent(),
        )

        assertEquals(true, hike.isStandalone)
        assertEquals("photo-1", hike.coverPhotoId)
    }

    @Test
    fun `map routes retain hike identity for offline route reconciliation`() {
        val routes = parseMapRoutes(
            """
            [
              {
                "hike_id":"hike-1",
                "route_segments":[
                  [{"lat":28.1,"lng":-82.1},{"lat":28.2,"lng":-82.2}],
                  [{"lat":28.3,"lng":-82.3}]
                ]
              },
              {
                "hike_id":"hike-2",
                "route_segments":[
                  [{"lat":29.1,"lng":-83.1},{"lat":29.2,"lng":-83.2}]
                ]
              }
            ]
            """.trimIndent(),
        )

        assertEquals(listOf("hike-1", "hike-2"), routes.map { it.hikeId })
        assertEquals(1, routes.first().segments.size)
        assertEquals(-83.2, routes.last().segments.single().last().longitude, 0.000001)
        assertEquals(2, parseMapRouteSegments(
            """[{"hike_id":"hike-1","route_segments":[[{"lat":1,"lng":2},{"lat":3,"lng":4}]]},{"hike_id":"hike-2","route_segments":[[{"lat":5,"lng":6},{"lat":7,"lng":8}]]}]""",
        ).size)
    }
}
