package com.hikejournal.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ReviewSyncRefreshTest {
    @Test
    fun `loaded review queue refreshes when outstanding uploads settle`() {
        assertTrue(
            shouldRefreshReviewQueueAfterSync(
                reviewQueueRequested = true,
                previousOutstandingSyncCount = 19,
                outstandingSyncCount = 0,
                connected = true,
            ),
        )
    }

    @Test
    fun `review refresh waits for a requested online queue and a completed transition`() {
        assertFalse(shouldRefreshReviewQueueAfterSync(false, 19, 0, true))
        assertFalse(shouldRefreshReviewQueueAfterSync(true, 19, 1, true))
        assertFalse(shouldRefreshReviewQueueAfterSync(true, 19, 0, false))
        assertFalse(shouldRefreshReviewQueueAfterSync(true, 0, 0, true))
    }
}
