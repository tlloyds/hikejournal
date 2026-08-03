package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class WikipediaSummaryTest {
    @Test
    fun `plain summary removes iNaturalist markup and decodes common entities`() {
        assertEquals(
            "Maid Marian & a wetland plant",
            plainWikipediaSummary("<i><b>Maid Marian</b></i> &amp; a wetland plant"),
        )
    }
}
