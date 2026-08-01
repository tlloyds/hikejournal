package com.hikejournal.app.ui

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HikeDeletionUiPolicyTest {
    @Test
    fun `offline local draft can reach deletion`() {
        assertTrue(canConfirmHikeDeletion(connected = false, isLocalDraft = true))
    }

    @Test
    fun `offline synced hike remains connection gated`() {
        assertFalse(canConfirmHikeDeletion(connected = false, isLocalDraft = false))
    }

    @Test
    fun `connected synced hike can reach remote deletion`() {
        assertTrue(canConfirmHikeDeletion(connected = true, isLocalDraft = false))
    }
}
