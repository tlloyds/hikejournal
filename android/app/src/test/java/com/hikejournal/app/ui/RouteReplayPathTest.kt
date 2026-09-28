package com.hikejournal.app.ui

import com.hikejournal.app.data.RoutePoint
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RouteReplayPathTest {
    @Test
    fun progressFollowsRouteDistanceAndInterpolatesTheMovingPoint() {
        val path = RouteReplayPath(
            listOf(
                listOf(point(0.0, 0.0), point(0.0, 0.01), point(0.01, 0.01)),
            ),
        )

        val halfway = path.pointAt(0.5f)

        assertEquals(0.0, halfway?.latitude ?: Double.NaN, 0.0001)
        assertEquals(0.01, halfway?.longitude ?: Double.NaN, 0.0001)
        assertEquals(3, path.visibleSegments(0.75f).single().size)
        assertEquals(2, path.visibleSegments(0.25f).single().size)
    }

    @Test
    fun separateTrackSegmentsStaySeparateDuringReplay() {
        val first = listOf(point(0.0, 0.0), point(0.0, 0.01))
        val second = listOf(point(0.0, 0.05), point(0.0, 0.06))
        val path = RouteReplayPath(listOf(first, second))

        assertEquals(1, path.visibleSegments(0.49f).size)
        assertEquals(2, path.visibleSegments(0.51f).size)
        assertEquals(2, path.visibleSegments(1f).size)
        val point = path.pointAt(0.51f)
        assertEquals(0.0, point?.latitude ?: Double.NaN, 0.0001)
        assertTrue(point!!.longitude > second.first().longitude)
        assertTrue(point.longitude < second.last().longitude)
    }

    @Test
    fun invalidAndStationarySegmentsDoNotMakeAPlayableRoute() {
        val path = RouteReplayPath(
            listOf(
                listOf(point(91.0, 0.0), point(91.0, 1.0)),
                listOf(point(1.0, 1.0), point(1.0, 1.0)),
            ),
        )

        assertFalse(path.isPlayable)
        assertTrue(path.visibleSegments(0.5f).isEmpty())
        assertEquals(null, path.pointAt(0.5f))
    }

    private fun point(latitude: Double, longitude: Double) = RoutePoint(latitude, longitude)
}
