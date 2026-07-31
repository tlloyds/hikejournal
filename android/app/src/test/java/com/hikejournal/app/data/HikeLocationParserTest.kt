package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class HikeLocationParserTest {
    @Test
    fun `imported hike locations keep stable ids and names`() {
        val locations = parseHikeLocations(
            """[
                {"id":"location-1","name":"Alafia Scrub Preserve"},
                {"id":"","name":"Ignored"}
            ]""",
        )

        assertEquals(
            listOf(HikeLocation("location-1", "Alafia Scrub Preserve")),
            locations,
        )
    }
}
