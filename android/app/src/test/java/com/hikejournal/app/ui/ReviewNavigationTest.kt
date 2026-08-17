package com.hikejournal.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ReviewNavigationTest {
    @Test
    fun `android back unwinds review state before leaving the tab`() {
        assertEquals(ReviewBackAction.Wait, reviewBackAction(batchMode = true, batchIdentifying = true, index = 4))
        assertEquals(ReviewBackAction.CloseBatch, reviewBackAction(batchMode = true, batchIdentifying = false, index = 4))
        assertEquals(ReviewBackAction.PreviousPhoto, reviewBackAction(batchMode = false, batchIdentifying = false, index = 4))
        assertEquals(ReviewBackAction.LeaveReview, reviewBackAction(batchMode = false, batchIdentifying = false, index = 0))
    }

    @Test
    fun `only a completed batch closes automatically`() {
        assertTrue(shouldAutoCloseReviewBatch(batchIdentifying = false, state = "completed"))
        assertFalse(shouldAutoCloseReviewBatch(batchIdentifying = false, state = "failed"))
        assertFalse(shouldAutoCloseReviewBatch(batchIdentifying = true, state = "completed"))
    }

    @Test
    fun `an active or failed batch can be reopened from ordinary review`() {
        assertTrue(shouldResumeReviewBatch(batchIdentifying = true, state = "running"))
        assertTrue(shouldResumeReviewBatch(batchIdentifying = false, state = "queued"))
        assertTrue(shouldResumeReviewBatch(batchIdentifying = false, state = "failed"))
        assertFalse(shouldResumeReviewBatch(batchIdentifying = false, state = "completed"))
        assertFalse(shouldResumeReviewBatch(batchIdentifying = false, state = null))
    }
}
