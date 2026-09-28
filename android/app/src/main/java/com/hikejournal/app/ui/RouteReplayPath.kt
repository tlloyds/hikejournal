package com.hikejournal.app.ui

import com.hikejournal.app.data.RoutePoint
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

internal const val ROUTE_REPLAY_METERS_PER_MILE = 1_609.344

internal data class RouteMileMarker(
    val mile: Int,
    val distanceMeters: Double,
    val point: RoutePoint,
)

/** A distance-weighted view of a saved route for fast visual replay. */
internal class RouteReplayPath(routeSegments: List<List<RoutePoint>>) {
    private data class Segment(
        val points: List<RoutePoint>,
        val cumulativeMeters: DoubleArray,
        val lengthMeters: Double,
    )

    private val segments = routeSegments.mapNotNull { rawPoints ->
        val points = rawPoints.filter(RoutePoint::isUsable)
        if (points.size < 2) return@mapNotNull null
        val cumulative = DoubleArray(points.size)
        for (index in 1 until points.size) {
            cumulative[index] = cumulative[index - 1] + distanceMeters(points[index - 1], points[index])
        }
        val length = cumulative.last()
        if (length <= 0.0) null else Segment(points, cumulative, length)
    }

    private val totalDistanceMeters = segments.sumOf(Segment::lengthMeters)

    val isPlayable: Boolean get() = totalDistanceMeters > 0.0
    val totalDistanceMiles: Double get() = totalDistanceMeters / ROUTE_REPLAY_METERS_PER_MILE

    fun distanceAt(progress: Float): Double = totalDistanceMeters * progress.coerceIn(0f, 1f)

    fun mileMarkers(): List<RouteMileMarker> = buildList {
        val wholeMiles = totalDistanceMiles.toInt()
        for (mile in 1..wholeMiles) {
            val distanceMeters = mile * ROUTE_REPLAY_METERS_PER_MILE
            pointAt((distanceMeters / totalDistanceMeters).toFloat())?.let { point ->
                add(RouteMileMarker(mile, distanceMeters, point))
            }
        }
    }

    fun visibleSegments(progress: Float): List<List<RoutePoint>> {
        if (!isPlayable || progress <= 0f) return emptyList()
        val targetDistance = totalDistanceMeters * progress.coerceIn(0f, 1f)
        val result = mutableListOf<List<RoutePoint>>()
        var distanceBeforeSegment = 0.0

        for (segment in segments) {
            val segmentEnd = distanceBeforeSegment + segment.lengthMeters
            if (targetDistance >= segmentEnd) {
                result += segment.points
                distanceBeforeSegment = segmentEnd
                continue
            }

            if (targetDistance > distanceBeforeSegment) {
                val localDistance = targetDistance - distanceBeforeSegment
                val partial = segment.points.takeThrough(localDistance, segment.cumulativeMeters)
                if (partial.size >= 2) result += partial
            }
            break
        }
        return result
    }

    fun pointAt(progress: Float): RoutePoint? {
        if (!isPlayable) return null
        val targetDistance = totalDistanceMeters * progress.coerceIn(0f, 1f)
        var distanceBeforeSegment = 0.0

        for (segment in segments) {
            val localDistance = targetDistance - distanceBeforeSegment
            if (localDistance <= segment.lengthMeters) {
                return segment.pointAt(localDistance.coerceAtLeast(0.0))
            }
            distanceBeforeSegment += segment.lengthMeters
        }
        return segments.lastOrNull()?.points?.lastOrNull()
    }

    private fun Segment.pointAt(distanceMeters: Double): RoutePoint {
        if (distanceMeters <= 0.0) return points.first()
        if (distanceMeters >= lengthMeters) return points.last()
        val nextIndex = cumulativeMeters.indexOfFirst { it >= distanceMeters }
            .coerceAtLeast(1)
        val startDistance = cumulativeMeters[nextIndex - 1]
        val edgeLength = cumulativeMeters[nextIndex] - startDistance
        if (edgeLength <= 0.0) return points[nextIndex]
        val amount = ((distanceMeters - startDistance) / edgeLength).coerceIn(0.0, 1.0)
        return interpolate(points[nextIndex - 1], points[nextIndex], amount)
    }

    private fun List<RoutePoint>.takeThrough(
        distanceMeters: Double,
        cumulativeMeters: DoubleArray,
    ): List<RoutePoint> {
        val result = mutableListOf(first())
        for (index in 1 until size) {
            val pointDistance = cumulativeMeters[index]
            if (pointDistance <= distanceMeters) {
                result += this[index]
            } else {
                val previousDistance = cumulativeMeters[index - 1]
                val edgeLength = pointDistance - previousDistance
                if (edgeLength > 0.0) {
                    result += interpolate(
                        this[index - 1],
                        this[index],
                        ((distanceMeters - previousDistance) / edgeLength).coerceIn(0.0, 1.0),
                    )
                }
                break
            }
        }
        return result
    }
}

private const val EARTH_RADIUS_METERS = 6_371_008.8

private fun RoutePoint.isUsable(): Boolean =
    latitude.isFinite() && latitude in -90.0..90.0 &&
        longitude.isFinite() && longitude in -180.0..180.0

private fun distanceMeters(start: RoutePoint, end: RoutePoint): Double {
    val latitudeDelta = Math.toRadians(end.latitude - start.latitude)
    val longitudeDelta = Math.toRadians(shortestLongitudeDelta(start.longitude, end.longitude))
    val startLatitude = Math.toRadians(start.latitude)
    val endLatitude = Math.toRadians(end.latitude)
    val halfChord = sin(latitudeDelta / 2).let { it * it } +
        cos(startLatitude) * cos(endLatitude) * sin(longitudeDelta / 2).let { it * it }
    return 2.0 * EARTH_RADIUS_METERS * atan2(sqrt(halfChord.coerceIn(0.0, 1.0)), sqrt((1.0 - halfChord).coerceAtLeast(0.0)))
}

private fun interpolate(start: RoutePoint, end: RoutePoint, amount: Double): RoutePoint {
    val longitudeDelta = shortestLongitudeDelta(start.longitude, end.longitude)
    val longitude = normalizeLongitude(start.longitude + longitudeDelta * amount)
    return RoutePoint(
        latitude = start.latitude + (end.latitude - start.latitude) * amount,
        longitude = longitude,
    )
}

private fun shortestLongitudeDelta(start: Double, end: Double): Double =
    ((end - start + 540.0) % 360.0) - 180.0

private fun normalizeLongitude(value: Double): Double = ((value + 540.0) % 360.0) - 180.0
