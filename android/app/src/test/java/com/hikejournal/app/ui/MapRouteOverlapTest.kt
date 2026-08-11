package com.hikejournal.app.ui

import com.hikejournal.app.data.RoutePoint
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MapRouteOverlapTest {
    @Test
    fun parallelNearbyRouteIsMarkedAsShared() {
        val trail = listOf(
            listOf(point(29.0, -81.82), point(29.0, -81.80)),
        )
        val route = listOf(
            listOf(point(29.00005, -81.82), point(29.00005, -81.80)),
        )

        val classified = classifyFloridaTrailOverlap(route, FloridaTrailSegmentIndex(trail))

        assertTrue(classified.isNotEmpty())
        assertTrue(classified.all(ClassifiedRouteSegment::overlapsFloridaTrail))
    }

    @Test
    fun perpendicularCrossingIsNotMarkedAsShared() {
        val trail = listOf(
            listOf(point(29.0, -81.82), point(29.0, -81.80)),
        )
        val crossingRoute = listOf(
            listOf(point(28.999, -81.81), point(29.001, -81.81)),
        )

        val classified = classifyFloridaTrailOverlap(
            crossingRoute,
            FloridaTrailSegmentIndex(trail),
        )

        assertTrue(classified.isNotEmpty())
        assertFalse(classified.any(ClassifiedRouteSegment::overlapsFloridaTrail))
    }

    @Test
    fun routeThatLeavesTrailHasSharedAndPersonalSections() {
        val trail = listOf(
            listOf(point(29.0, -81.82), point(29.0, -81.80)),
        )
        val partialRoute = listOf(
            listOf(
                point(29.00005, -81.82),
                point(29.00005, -81.81),
                point(29.002, -81.81),
            ),
        )

        val classified = classifyFloridaTrailOverlap(
            partialRoute,
            FloridaTrailSegmentIndex(trail),
        )

        assertTrue(classified.any(ClassifiedRouteSegment::overlapsFloridaTrail))
        assertTrue(classified.any { !it.overlapsFloridaTrail })
    }

    @Test
    fun disabledOverlayLeavesEveryRoutePersonal() {
        val route = listOf(
            listOf(point(29.0, -81.82), point(29.0, -81.80)),
        )

        val classified = classifyFloridaTrailOverlap(route, trailIndex = null)

        assertTrue(classified.isNotEmpty())
        assertFalse(classified.any(ClassifiedRouteSegment::overlapsFloridaTrail))
    }

    private fun point(latitude: Double, longitude: Double) = RoutePoint(
        latitude = latitude,
        longitude = longitude,
    )
}
