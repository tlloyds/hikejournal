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
    fun `first quest target prompt omits more`() {
        assertEquals("Pick 5", questTargetPrompt(0))
        assertEquals("Pick 4 more", questTargetPrompt(1))
        assertEquals("Pick 1 more", questTargetPrompt(4))
    }
}
