package com.hikejournal.app.ui

import android.content.Context
import com.hikejournal.app.BuildConfig
import com.hikejournal.app.data.FLORIDA_TRAIL_ID
import com.hikejournal.app.data.NationalScenicTrailOverlays
import com.hikejournal.app.data.RoutePoint
import com.hikejournal.app.data.TrailOverlayDefinition
import java.io.File
import java.util.concurrent.TimeUnit
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.hypot
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.tan
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.LineString
import org.maplibre.geojson.MultiLineString

internal const val FLORIDA_TRAIL_GEOJSON_URL = "https://services9.arcgis.com/soy9dtLUh5hYXg8U/arcgis/rest/services/FNST%20Master/FeatureServer/0/query?where=1%3D1&outFields=FID&returnGeometry=true&outSR=4326&f=geojson&maxAllowableOffset=0.00002"

internal data class ClassifiedRouteSegment(
    val points: List<RoutePoint>,
    val overlapsFloridaTrail: Boolean,
)

internal object NationalScenicTrailOverlayData {
    private val CacheLifetimeMillis = TimeUnit.DAYS.toMillis(7)
    private const val PageSize = 2_000
    private const val MaximumPages = 20
    private val client = OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(25, TimeUnit.SECONDS)
        .build()

    private val memoryCache = mutableMapOf<String, FeatureCollection>()

    suspend fun load(context: Context, selectedTrailIds: Set<String>): FeatureCollection? = coroutineScope {
        val selected = NationalScenicTrailOverlays.filter { it.id in selectedTrailIds }
        if (selected.isEmpty()) return@coroutineScope null
        val collections = selected.map { trail ->
            async(Dispatchers.IO) { loadTrail(context, trail) }
        }.awaitAll().filterNotNull()
        FeatureCollection.fromFeatures(collections.flatMap { it.features().orEmpty() })
    }

    private fun loadTrail(context: Context, trail: TrailOverlayDefinition): FeatureCollection? {
        synchronized(memoryCache) { memoryCache[trail.id] }?.let { return it }
        val cacheFile = File(context.applicationContext.cacheDir, "national-scenic-trail-${trail.id}.geojson")
        val cached = runCatching { cacheFile.takeIf(File::isFile)?.readText() }.getOrNull()
        val cacheIsFresh = cacheFile.isFile &&
            System.currentTimeMillis() - cacheFile.lastModified() <= CacheLifetimeMillis
        val raw = if (cacheIsFresh && !cached.isNullOrBlank()) {
            cached
        } else {
            download(trail)?.also { downloaded -> writeCache(cacheFile, downloaded) } ?: cached
        }
        return runCatching { raw?.let(FeatureCollection::fromJson) }
            .getOrNull()
            ?.also { collection -> synchronized(memoryCache) { memoryCache[trail.id] = collection } }
    }

    private fun download(trail: TrailOverlayDefinition): String? = runCatching {
        val features = mutableListOf<Feature>()
        trail.layerUrls.forEach { layerUrl ->
            for (page in 0 until MaximumPages) {
                val url = layerUrl.toHttpUrl().newBuilder()
                    .addPathSegment("query")
                    .addQueryParameter("where", "1=1")
                    .addQueryParameter("outFields", trail.objectIdField)
                    .addQueryParameter("returnGeometry", "true")
                    .addQueryParameter("outSR", "4326")
                    .addQueryParameter("f", "geojson")
                    .addQueryParameter("maxAllowableOffset", "0.00005")
                    .addQueryParameter("resultRecordCount", PageSize.toString())
                    .addQueryParameter("resultOffset", (page * PageSize).toString())
                    .build()
                val request = Request.Builder()
                    .url(url)
                    .header("User-Agent", "HikeJournal/${BuildConfig.VERSION_NAME}")
                    .build()
                val pageFeatures = client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@runCatching null
                    val body = response.body?.string()?.takeIf(String::isNotBlank)
                        ?: return@runCatching null
                    FeatureCollection.fromJson(body).features().orEmpty()
                }
                features += pageFeatures
                if (pageFeatures.size < PageSize) break
            }
        }
        FeatureCollection.fromFeatures(features).toJson()
    }.getOrNull()

    private fun writeCache(cacheFile: File, value: String) {
        runCatching {
            val temporary = File.createTempFile("florida-trail-", ".geojson", cacheFile.parentFile)
            temporary.writeText(value)
            if (!temporary.renameTo(cacheFile)) {
                cacheFile.writeText(value)
                temporary.delete()
            }
        }
    }
}

internal object FloridaTrailOverlayData {
    suspend fun load(context: Context): FeatureCollection? =
        NationalScenicTrailOverlayData.load(context, setOf(FLORIDA_TRAIL_ID))
}

internal fun FeatureCollection.trailOverlaySegments(): List<List<RoutePoint>> =
    features().orEmpty().flatMap { feature ->
        when (val geometry = feature.geometry()) {
            is LineString -> listOf(geometry.coordinates().toRoutePoints())
            is MultiLineString -> geometry.coordinates().map { it.toRoutePoints() }
            else -> emptyList()
        }
    }.filter { it.size >= 2 }

internal fun FeatureCollection.floridaTrailSegments(): List<List<RoutePoint>> = trailOverlaySegments()

private fun List<org.maplibre.geojson.Point>.toRoutePoints(): List<RoutePoint> = map { point ->
    RoutePoint(latitude = point.latitude(), longitude = point.longitude())
}

internal fun classifyFloridaTrailOverlap(
    routes: List<List<RoutePoint>>,
    trailIndex: FloridaTrailSegmentIndex?,
): List<ClassifiedRouteSegment> {
    if (trailIndex == null || trailIndex.isEmpty) {
        return routes.filter { it.size >= 2 }.map { ClassifiedRouteSegment(it, false) }
    }
    return routes.flatMap { route -> classifyRoute(route, trailIndex) }
}

private fun classifyRoute(
    route: List<RoutePoint>,
    trailIndex: FloridaTrailSegmentIndex,
): List<ClassifiedRouteSegment> {
    val valid = route.filter { point ->
        point.latitude.isFinite() && point.longitude.isFinite() &&
            point.latitude in -90.0..90.0 && point.longitude in -180.0..180.0
    }
    if (valid.size < 2) return emptyList()
    val result = mutableListOf<ClassifiedRouteSegment>()
    var currentOverlap: Boolean? = null
    var currentPoints = mutableListOf<RoutePoint>()

    valid.zipWithNext().forEach { (start, end) ->
        val projectedStart = start.projected()
        val projectedEnd = end.projected()
        val distance = hypot(projectedEnd.x - projectedStart.x, projectedEnd.y - projectedStart.y)
        val chunks = ceil(distance / MaxRouteChunkMeters).toInt().coerceIn(1, MaxChunksPerEdge)
        repeat(chunks) { index ->
            val from = interpolate(start, end, index.toDouble() / chunks)
            val to = interpolate(start, end, (index + 1).toDouble() / chunks)
            val overlaps = trailIndex.overlaps(from, to)
            if (currentOverlap == null) {
                currentOverlap = overlaps
                currentPoints.add(from)
            } else if (currentOverlap != overlaps) {
                if (currentPoints.size >= 2) {
                    result.add(ClassifiedRouteSegment(currentPoints.toList(), currentOverlap == true))
                }
                currentOverlap = overlaps
                currentPoints = mutableListOf(from)
            }
            if (currentPoints.lastOrNull() != to) currentPoints.add(to)
        }
    }
    if (currentPoints.size >= 2) {
        result.add(ClassifiedRouteSegment(currentPoints.toList(), currentOverlap == true))
    }
    return result
}

internal class FloridaTrailSegmentIndex(
    trailRoutes: List<List<RoutePoint>>,
) {
    private val cells = mutableMapOf<Long, MutableList<ProjectedSegment>>()
    val isEmpty: Boolean get() = cells.isEmpty()

    init {
        trailRoutes.forEach { route ->
            route.zipWithNext().forEach segmentLoop@{ (start, end) ->
                if (!start.isValidCoordinate() || !end.isValidCoordinate()) return@segmentLoop
                val segment = ProjectedSegment(start.projected(), end.projected())
                if (segment.length < MinimumSegmentMeters) return@segmentLoop
                val minCellX = cellCoordinate(min(segment.start.x, segment.end.x) - OverlapDistanceMeters)
                val maxCellX = cellCoordinate(max(segment.start.x, segment.end.x) + OverlapDistanceMeters)
                val minCellY = cellCoordinate(min(segment.start.y, segment.end.y) - OverlapDistanceMeters)
                val maxCellY = cellCoordinate(max(segment.start.y, segment.end.y) + OverlapDistanceMeters)
                for (cellX in minCellX..maxCellX) {
                    for (cellY in minCellY..maxCellY) {
                        cells.getOrPut(cellKey(cellX, cellY), ::mutableListOf).add(segment)
                    }
                }
            }
        }
    }

    fun overlaps(start: RoutePoint, end: RoutePoint): Boolean {
        val projectedStart = start.projected()
        val projectedEnd = end.projected()
        val userSegment = ProjectedSegment(projectedStart, projectedEnd)
        if (userSegment.length < MinimumSegmentMeters) return false
        val midpoint = ProjectedPoint(
            x = (projectedStart.x + projectedEnd.x) / 2.0,
            y = (projectedStart.y + projectedEnd.y) / 2.0,
        )
        val candidates = cells[cellKey(cellCoordinate(midpoint.x), cellCoordinate(midpoint.y))].orEmpty()
        return candidates.any { trailSegment ->
            userSegment.directionSimilarity(trailSegment) >= MinimumDirectionSimilarity &&
                trailSegment.distanceTo(midpoint) <= OverlapDistanceMeters
        }
    }

    private fun cellCoordinate(value: Double): Int = floor(value / GridCellMeters).toInt()

    private fun cellKey(x: Int, y: Int): Long =
        (x.toLong() shl 32) xor (y.toLong() and 0xffffffffL)
}

private data class ProjectedPoint(val x: Double, val y: Double)

private data class ProjectedSegment(val start: ProjectedPoint, val end: ProjectedPoint) {
    val deltaX = end.x - start.x
    val deltaY = end.y - start.y
    val length = hypot(deltaX, deltaY)

    fun directionSimilarity(other: ProjectedSegment): Double {
        if (length < MinimumSegmentMeters || other.length < MinimumSegmentMeters) return 0.0
        return abs(deltaX * other.deltaX + deltaY * other.deltaY) / (length * other.length)
    }

    fun distanceTo(point: ProjectedPoint): Double {
        val lengthSquared = deltaX * deltaX + deltaY * deltaY
        if (lengthSquared <= 0.0) return hypot(point.x - start.x, point.y - start.y)
        val projection = (
            (point.x - start.x) * deltaX + (point.y - start.y) * deltaY
        ) / lengthSquared
        val amount = projection.coerceIn(0.0, 1.0)
        return hypot(
            point.x - (start.x + amount * deltaX),
            point.y - (start.y + amount * deltaY),
        )
    }
}

private fun RoutePoint.projected(): ProjectedPoint {
    val latitudeRadians = Math.toRadians(latitude.coerceIn(-85.0, 85.0))
    return ProjectedPoint(
        x = EarthRadiusMeters * Math.toRadians(longitude),
        y = EarthRadiusMeters * ln(tan(PI / 4.0 + latitudeRadians / 2.0)),
    )
}

private fun RoutePoint.isValidCoordinate(): Boolean =
    latitude.isFinite() && longitude.isFinite() &&
        latitude in -90.0..90.0 && longitude in -180.0..180.0

private fun interpolate(start: RoutePoint, end: RoutePoint, amount: Double): RoutePoint = RoutePoint(
    latitude = start.latitude + (end.latitude - start.latitude) * amount,
    longitude = start.longitude + (end.longitude - start.longitude) * amount,
)

private const val EarthRadiusMeters = 6_378_137.0
private const val GridCellMeters = 120.0
private const val OverlapDistanceMeters = 45.0
private const val MinimumDirectionSimilarity = 0.72
private const val MinimumSegmentMeters = 0.5
private const val MaxRouteChunkMeters = 20.0
private const val MaxChunksPerEdge = 5_000
