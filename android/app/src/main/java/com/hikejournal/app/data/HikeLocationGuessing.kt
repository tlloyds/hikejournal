package com.hikejournal.app.data

import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

internal const val MAX_HIKE_LOCATION_SUGGESTION_METERS = 8_000.0

data class HikeLocationSuggestion(
    val location: HikeLocation,
    val distanceMeters: Double,
)

/** Suggests the library place nearest the first valid point recorded for the hike. */
internal fun suggestHikeLocation(
    routeSegments: List<List<RoutePoint>>,
    locations: List<HikeLocation>,
    maxDistanceMeters: Double = MAX_HIKE_LOCATION_SUGGESTION_METERS,
): HikeLocationSuggestion? {
    val start = routeSegments.asSequence()
        .flatten()
        .firstOrNull { it.latitude.isValidLatitude() && it.longitude.isValidLongitude() }
        ?: return null
    return locations.asSequence()
        .mapNotNull { location ->
            val latitude = location.latitude?.takeIf(Double::isValidLatitude) ?: return@mapNotNull null
            val longitude = location.longitude?.takeIf(Double::isValidLongitude) ?: return@mapNotNull null
            HikeLocationSuggestion(
                location = location,
                distanceMeters = haversineMeters(start.latitude, start.longitude, latitude, longitude),
            )
        }
        .filter { it.distanceMeters <= maxDistanceMeters }
        .minWithOrNull(compareBy<HikeLocationSuggestion> { it.distanceMeters }.thenBy { it.location.name })
}

private fun Double.isValidLatitude(): Boolean = isFinite() && this in -90.0..90.0

private fun Double.isValidLongitude(): Boolean = isFinite() && this in -180.0..180.0

private fun haversineMeters(
    latitudeA: Double,
    longitudeA: Double,
    latitudeB: Double,
    longitudeB: Double,
): Double {
    val lat1 = Math.toRadians(latitudeA)
    val lat2 = Math.toRadians(latitudeB)
    val deltaLat = lat2 - lat1
    val deltaLongitude = Math.toRadians(longitudeB - longitudeA)
    val haversine = sin(deltaLat / 2).pow(2) +
        cos(lat1) * cos(lat2) * sin(deltaLongitude / 2).pow(2)
    return 6_371_008.8 * 2 * asin(sqrt(haversine.coerceIn(0.0, 1.0)))
}
