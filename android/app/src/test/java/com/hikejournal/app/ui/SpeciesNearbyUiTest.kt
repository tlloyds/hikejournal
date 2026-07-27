package com.hikejournal.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SpeciesNearbyUiTest {
    @Test
    fun `saved trail results stay hidden until search text is entered`() {
        assertFalse(shouldShowSavedTrailResults("", hasSelectedArea = false))
        assertFalse(shouldShowSavedTrailResults("   ", hasSelectedArea = false))
        assertTrue(shouldShowSavedTrailResults("mill", hasSelectedArea = false))
        assertFalse(shouldShowSavedTrailResults("Mills Creek", hasSelectedArea = true))
    }

    @Test
    fun `quest target prompt requires only one selection`() {
        assertEquals("Pick at least 1", questTargetPrompt(0))
        assertEquals("Save quest", questTargetPrompt(1))
        assertEquals("Save quest", questTargetPrompt(10))
    }

    @Test
    fun `collected species retain their nearby reporting score`() {
        assertEquals(
            "COLLECTED · REGULARLY REPORTED",
            discoveryStatusLabel(collected = true, frequencyBand = "Regularly reported"),
        )
        assertEquals(
            "LESS OFTEN REPORTED",
            discoveryStatusLabel(collected = false, frequencyBand = "Less often reported"),
        )
    }
}
