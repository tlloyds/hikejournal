package com.hikejournal.app.ui

import com.hikejournal.app.data.initialProcessingStatus
import org.junit.Assert.assertEquals
import org.junit.Test

class EverydayReviewDefaultsTest {
    @Test
    fun `photo uploads are not automatically queued and videos cannot be reviewed`() {
        assertEquals("ready", initialProcessingStatus(false, "image/jpeg"))
        assertEquals("in_review", initialProcessingStatus(true, "image/jpeg"))
        assertEquals("ready", initialProcessingStatus(true, "video/mp4"))
    }
}
