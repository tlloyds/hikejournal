package com.hikejournal.app.ui

import com.hikejournal.app.data.RoutePoint
import org.junit.Assert.assertEquals
import org.junit.Test

class JournalRoutePreviewTest {
    @Test
    fun `route summary uses singular segment label`() {
        val route = listOf(
            listOf(
                RoutePoint(28.0, -82.0),
                RoutePoint(28.1, -81.9),
            ),
        )

        assertEquals("2 saved GPS points · 1 segment", journalRouteSummary(route))
    }

    @Test
    fun `route summary totals every saved segment`() {
        val route = listOf(
            listOf(RoutePoint(28.0, -82.0)),
            listOf(
                RoutePoint(28.1, -81.9),
                RoutePoint(28.2, -81.8),
                RoutePoint(28.3, -81.7),
            ),
        )

        assertEquals("4 saved GPS points · 2 segments", journalRouteSummary(route))
    }
}
