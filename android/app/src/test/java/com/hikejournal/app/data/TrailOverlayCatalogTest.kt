package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TrailOverlayCatalogTest {
    @Test
    fun `catalog includes every national scenic trail with unique secure sources`() {
        assertEquals(11, NationalScenicTrailOverlays.size)
        assertEquals(11, NationalScenicTrailOverlays.map(TrailOverlayDefinition::id).distinct().size)
        assertEquals(
            setOf("appalachian", "pacific-crest", "continental-divide"),
            NationalScenicTrailOverlays.filter(TrailOverlayDefinition::featured).map(TrailOverlayDefinition::id).toSet(),
        )
        assertTrue(NationalScenicTrailOverlays.flatMap(TrailOverlayDefinition::layerUrls).all { it.startsWith("https://") })
    }
}
