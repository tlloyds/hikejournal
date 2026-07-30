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
    }
}
