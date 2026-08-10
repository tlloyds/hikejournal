package com.hikejournal.app.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class ReviewNavigationTest {
    @Test
    fun `android back unwinds review state before leaving the tab`() {
        assertEquals(ReviewBackAction.Wait, reviewBackAction(batchMode = true, batchIdentifying = true, index = 4))
        assertEquals(ReviewBackAction.CloseBatch, reviewBackAction(batchMode = true, batchIdentifying = false, index = 4))
        assertEquals(ReviewBackAction.PreviousPhoto, reviewBackAction(batchMode = false, batchIdentifying = false, index = 4))
        assertEquals(ReviewBackAction.LeaveReview, reviewBackAction(batchMode = false, batchIdentifying = false, index = 0))
    }
}
