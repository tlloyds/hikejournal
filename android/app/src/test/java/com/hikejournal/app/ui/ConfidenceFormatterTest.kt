package com.hikejournal.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ConfidenceFormatterTest {
    @Test
    fun `percentage point values are not multiplied again`() {
        val values = listOf(97.9455, 1.3334823379, 0.1640132701)
        val usesFractionalScale = usesFractionalConfidenceScale(values)

        assertFalse(usesFractionalScale)
        assertEquals("98%", formatConfidencePercent(values[0], usesFractionalScale))
        assertEquals("1%", formatConfidencePercent(values[1], usesFractionalScale))
        assertEquals("0%", formatConfidencePercent(values[2], usesFractionalScale))
    }

    @Test
    fun `older fractional values are still converted to percentages`() {
        val values = listOf(0.78, 0.13)
        val usesFractionalScale = usesFractionalConfidenceScale(values)

        assertTrue(usesFractionalScale)
        assertEquals("78%", formatConfidencePercent(values[0], usesFractionalScale))
        assertEquals("13%", formatConfidencePercent(values[1], usesFractionalScale))
    }

    @Test
    fun `displayed percentage stays within a valid range`() {
        assertEquals("0%", formatConfidencePercent(-2.0, usesFractionalScale = false))
        assertEquals("100%", formatConfidencePercent(120.0, usesFractionalScale = false))
        assertEquals("0%", formatConfidencePercent(Double.NaN, usesFractionalScale = false))
    }
}
