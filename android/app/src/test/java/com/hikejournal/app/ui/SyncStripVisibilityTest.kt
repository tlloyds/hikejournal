package com.hikejournal.app.ui

import com.hikejournal.app.data.SyncStatus
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncStripVisibilityTest {
    @Test
    fun `connected and caught up hides sync strip`() {
        assertFalse(shouldShowSyncStrip(SyncStatus(), syncing = false))
    }

    @Test
    fun `active and actionable sync states keep sync strip visible`() {
        assertTrue(shouldShowSyncStrip(SyncStatus(connected = false), syncing = false))
        assertTrue(shouldShowSyncStrip(SyncStatus(), syncing = true))
        assertTrue(shouldShowSyncStrip(SyncStatus(pendingCount = 1), syncing = false))
        assertTrue(shouldShowSyncStrip(SyncStatus(syncingCount = 1), syncing = false))
        assertTrue(shouldShowSyncStrip(SyncStatus(needsAttentionCount = 1), syncing = false))
        assertTrue(shouldShowSyncStrip(SyncStatus(pendingPhotoCount = 1), syncing = false))
        assertTrue(shouldShowSyncStrip(SyncStatus(syncingPhotoCount = 1), syncing = false))
    }
}
