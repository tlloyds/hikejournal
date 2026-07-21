package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ReviewConfidenceTest {
    @Test
    fun `percentage point confidence is converted to a fraction for API requests`() {
        assertEquals(0.979455, normalizedReviewConfidence(97.9455)!!, 0.000001)
    }

    @Test
    fun `fractional confidence remains unchanged`() {
        assertEquals(0.78, normalizedReviewConfidence(0.78)!!, 0.000001)
    }

    @Test
    fun `non finite confidence is omitted`() {
        assertNull(normalizedReviewConfidence(Double.NaN))
    }
}
