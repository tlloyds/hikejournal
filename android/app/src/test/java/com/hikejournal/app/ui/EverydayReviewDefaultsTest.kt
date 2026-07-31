package com.hikejournal.app.ui

import com.hikejournal.app.data.initialProcessingStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EverydayReviewDefaultsTest {
    @Test
    fun `everyday sightings default to species review while hikes do not`() {
        assertTrue(defaultQueueForReview(isEverydaySighting = true))
        assertFalse(defaultQueueForReview(isEverydaySighting = false))
    }

    @Test
    fun `review default never queues videos`() {
        assertEquals("in_review", initialProcessingStatus(true, "image/jpeg"))
        assertEquals("ready", initialProcessingStatus(true, "video/mp4"))
        assertEquals("ready", initialProcessingStatus(false, "image/jpeg"))
    }
}
