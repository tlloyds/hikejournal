package com.hikejournal.app.ui

import android.content.Context
import android.graphics.Bitmap
import com.hikejournal.app.data.RoutePoint
import kotlin.coroutines.resume
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import org.maplibre.android.MapLibre
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.maps.Style
import org.maplibre.android.snapshotter.MapSnapshotter
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.LineString
import org.maplibre.geojson.Point

private const val SHARE_ROUTE_SOURCE = "share-route"
private const val SHARE_ROUTE_HALO = "share-route-halo"
private const val SHARE_ROUTE_LINE = "share-route-line"
private const val SHARE_START_SOURCE = "share-start"
private const val SHARE_START_LAYER = "share-start-layer"
private const val SHARE_END_SOURCE = "share-end"
private const val SHARE_END_LAYER = "share-end-layer"
private const val SATELLITE_SNAPSHOT_TIMEOUT_MS = 15_000L

internal data class ShareRouteBounds(
    val north: Double,
    val east: Double,
    val south: Double,
    val west: Double,
)

internal fun shareRouteBounds(routeSegments: List<List<RoutePoint>>): ShareRouteBounds? {
    val points = routeSegments.flatten().filter { it.latitude.isFinite() && it.longitude.isFinite() }
    if (points.isEmpty()) return null
    val rawNorth = points.maxOf(RoutePoint::latitude)
    val rawSouth = points.minOf(RoutePoint::latitude)
    val rawEast = points.maxOf(RoutePoint::longitude)
    val rawWest = points.minOf(RoutePoint::longitude)
    val latitudePadding = ((rawNorth - rawSouth) * 0.12).coerceAtLeast(0.001)
    val longitudePadding = ((rawEast - rawWest) * 0.12).coerceAtLeast(0.001)
    return ShareRouteBounds(
        north = (rawNorth + latitudePadding).coerceAtMost(90.0),
        east = (rawEast + longitudePadding).coerceAtMost(180.0),
        south = (rawSouth - latitudePadding).coerceAtLeast(-90.0),
        west = (rawWest - longitudePadding).coerceAtLeast(-180.0),
    )
}

internal fun satelliteShareStyle(routeSegments: List<List<RoutePoint>>): String? {
    val usableSegments = routeSegments.map { segment ->
        segment.filter { it.latitude.isFinite() && it.longitude.isFinite() }
    }.filter(List<RoutePoint>::isNotEmpty)
    if (usableSegments.isEmpty()) return null

    val routeFeatures = usableSegments.filter { it.size >= 2 }.map { segment ->
        Feature.fromGeometry(
            LineString.fromLngLats(
                segment.map { point -> Point.fromLngLat(point.longitude, point.latitude) },
            ),
        )
    }
    val start = usableSegments.first().first()
    val end = usableSegments.last().last()
    val style = JSONObject(SATELLITE_STYLE)
    val sources = style.getJSONObject("sources")
    if (routeFeatures.isNotEmpty()) {
        sources.put(
            SHARE_ROUTE_SOURCE,
            geoJsonStyleSource(FeatureCollection.fromFeatures(routeFeatures).toJson()),
        )
    }
    sources.put(
        SHARE_START_SOURCE,
        geoJsonStyleSource(Feature.fromGeometry(Point.fromLngLat(start.longitude, start.latitude)).toJson()),
    )
    sources.put(
        SHARE_END_SOURCE,
        geoJsonStyleSource(Feature.fromGeometry(Point.fromLngLat(end.longitude, end.latitude)).toJson()),
    )

    val layers = style.getJSONArray("layers")
    if (routeFeatures.isNotEmpty()) {
        layers.put(
            JSONObject(
                """{"id":"$SHARE_ROUTE_HALO","type":"line","source":"$SHARE_ROUTE_SOURCE","layout":{"line-cap":"round","line-join":"round"},"paint":{"line-color":"#14251D","line-width":10,"line-opacity":0.78}}""",
            ),
        )
        layers.put(
            JSONObject(
                """{"id":"$SHARE_ROUTE_LINE","type":"line","source":"$SHARE_ROUTE_SOURCE","layout":{"line-cap":"round","line-join":"round"},"paint":{"line-color":"#F09A55","line-width":6,"line-opacity":1}}""",
            ),
        )
    }
    layers.put(
        JSONObject(
            """{"id":"$SHARE_START_LAYER","type":"circle","source":"$SHARE_START_SOURCE","paint":{"circle-color":"#FFFCF3","circle-radius":7,"circle-opacity":1,"circle-stroke-color":"#183A2D","circle-stroke-width":3}}""",
        ),
    )
    layers.put(
        JSONObject(
            """{"id":"$SHARE_END_LAYER","type":"circle","source":"$SHARE_END_SOURCE","paint":{"circle-color":"#F09A55","circle-radius":7,"circle-opacity":1,"circle-stroke-color":"#FFFCF3","circle-stroke-width":2}}""",
        ),
    )
    return style.toString()
}

private fun geoJsonStyleSource(data: String): JSONObject = JSONObject()
    .put("type", "geojson")
    .put("data", JSONObject(data))

internal suspend fun captureSatelliteRouteMap(
    context: Context,
    routeSegments: List<List<RoutePoint>>,
    width: Int = 968,
    height: Int = 555,
): Bitmap? {
    val usableSegments = routeSegments.map { segment ->
        segment.filter { it.latitude.isFinite() && it.longitude.isFinite() }
    }.filter(List<RoutePoint>::isNotEmpty)
    val bounds = shareRouteBounds(usableSegments) ?: return null
    val styleJson = satelliteShareStyle(usableSegments) ?: return null
    return withTimeoutOrNull(SATELLITE_SNAPSHOT_TIMEOUT_MS) {
        withContext(Dispatchers.Main.immediate) {
            try {
                MapLibre.getInstance(context.applicationContext)
                val options = MapSnapshotter.Options(width, height)
                    .withStyleBuilder(Style.Builder().fromJson(styleJson))
                    .withRegion(
                        LatLngBounds.Builder()
                            .include(LatLng(bounds.north, bounds.east))
                            .include(LatLng(bounds.south, bounds.west))
                            .build(),
                    )
                    .withPadding(28, 28, 28, 28)
                    .withLogo(false)
                    .withAttribution(false)
                suspendCancellableCoroutine { continuation ->
                    val snapshotter = MapSnapshotter(context.applicationContext, options)
                    continuation.invokeOnCancellation { snapshotter.cancel() }
                    snapshotter.start(
                        { snapshot ->
                            if (continuation.isActive) continuation.resume(snapshot.bitmap)
                        },
                        {
                            if (continuation.isActive) continuation.resume(null)
                        },
                    )
                }
            } catch (_: RuntimeException) {
                null
            }
        }
    }
}
