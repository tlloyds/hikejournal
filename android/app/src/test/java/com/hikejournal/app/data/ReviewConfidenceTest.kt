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

    @Test
    fun `confidence label displays normalized percentage`() {
        assertEquals("98% confidence", reviewConfidenceLabel(0.979455))
        assertEquals("98% confidence", reviewConfidenceLabel(97.9455))
    }

    @Test
    fun `confidence label omits invalid values`() {
        assertNull(reviewConfidenceLabel(Double.NaN))
        assertNull(reviewConfidenceLabel(null))
    }
}
