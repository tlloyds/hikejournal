@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.hikejournal.app.ui

import android.graphics.RectF
import android.os.Bundle
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.Layers
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Route
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.hikejournal.app.BuildConfig
import com.hikejournal.app.data.OfflineMapPack
import com.hikejournal.app.data.OfflineMapPacks
import com.hikejournal.app.data.NationalScenicTrailOverlays
import com.hikejournal.app.data.RoutePoint
import com.hikejournal.app.data.Sighting
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.TrailText
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapLibreMapOptions
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.style.expressions.Expression
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.PropertyFactory.circleColor
import org.maplibre.android.style.layers.PropertyFactory.circleOpacity
import org.maplibre.android.style.layers.PropertyFactory.circleRadius
import org.maplibre.android.style.layers.PropertyFactory.circleStrokeColor
import org.maplibre.android.style.layers.PropertyFactory.circleStrokeWidth
import org.maplibre.android.style.layers.PropertyFactory.lineColor
import org.maplibre.android.style.layers.PropertyFactory.lineOpacity
import org.maplibre.android.style.layers.PropertyFactory.lineWidth
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.LineString
import org.maplibre.geojson.Point
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private const val SOURCE_ID = "hikejournal-sightings"
private const val LAYER_ID = "hikejournal-sightings-circles"
private const val SELECTED_SOURCE_ID = "hikejournal-selected-sighting"
private const val SELECTED_LAYER_ID = "hikejournal-selected-sighting-circle"
private const val ROUTE_SOURCE_ID = "hikejournal-routes"
private const val ROUTE_HALO_LAYER_ID = "hikejournal-route-halo"
private const val ROUTE_LAYER_ID = "hikejournal-route-lines"
private const val ROUTE_OVERLAP_LAYER_ID = "hikejournal-route-overlap-lines"
private const val FLORIDA_TRAIL_SOURCE_ID = "florida-trail"
private const val FLORIDA_TRAIL_HALO_LAYER_ID = "florida-trail-halo"
private const val FLORIDA_TRAIL_LAYER_ID = "florida-trail-lines"
internal const val FLORIDA_TRAIL_COLOR = "#F47A32"
internal const val HIKE_ROUTE_COLOR = "#22D3EE"
internal const val ROUTE_OVERLAP_COLOR = "#FF4D8D"
internal const val PHOTO_POINT_COLOR = "#8BD3FF"
private const val CURRENT_POSITION_SOURCE_ID = "hikejournal-current-position"
private const val CURRENT_POSITION_HALO_LAYER_ID = "hikejournal-current-position-halo"
private const val CURRENT_POSITION_LAYER_ID = "hikejournal-current-position-dot"
internal val SATELLITE_STYLE = """
    {
      "version": 8,
      "name": "HikeJournal Satellite",
      "sources": {
        "esri-world-imagery": {
          "type": "raster",
          "tiles": ["https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
          "tileSize": 256,
          "attribution": "Sources: Esri, Maxar, Earthstar Geographics, and the GIS User Community"
        }
      },
      "layers": [
        {"id": "satellite", "type": "raster", "source": "esri-world-imagery"}
      ]
    }
""".trimIndent()

internal enum class MapLayerMode { Trail, Satellite }

internal data class MapViewport(val bounds: LatLngBounds, val zoom: Double)

@Composable
fun SightingsMapScreen(
    sightings: List<Sighting>,
    routeSegments: List<List<RoutePoint>>,
    selectedTrailIds: Set<String>,
    loading: Boolean,
    openingPhotoId: String?,
    onRefresh: () -> Unit,
    onOpenHike: (String) -> Unit,
    onOpenPhoto: (Sighting) -> Unit,
) {
    var selected by remember { mutableStateOf<Sighting?>(null) }
    var layerMode by remember { mutableStateOf(MapLayerMode.Satellite) }
    var viewport by remember { mutableStateOf<MapViewport?>(null) }
    var packsOpen by remember { mutableStateOf(false) }

    Box(Modifier.fillMaxSize().background(Moss)) {
        HikeJournalMap(
            sightings = sightings,
            routeSegments = routeSegments,
            selectedSighting = selected,
            layerMode = layerMode,
            onSelect = { selected = it },
            onViewportChanged = { viewport = it },
            selectedTrailIds = selectedTrailIds,
            modifier = Modifier.fillMaxSize(),
        )

        Column(
            Modifier.fillMaxWidth().background(Color(0xF2183A2D)).statusBarsPadding().padding(start = 20.dp, end = 8.dp, top = 12.dp, bottom = 12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("HikeJournal", style = MaterialTheme.typography.titleMedium, color = Color(0xFFB7C8B5))
                    Text("Sightings map", style = MaterialTheme.typography.headlineMedium, color = Paper)
                    Text(
                        "${sightings.size} GEOTAGGED PHOTOS · ${routeSegments.size} ROUTE SEGMENTS",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFFB7C8B5),
                    )
                }
                TextButton(onClick = {
                    layerMode = if (layerMode == MapLayerMode.Trail) MapLayerMode.Satellite else MapLayerMode.Trail
                }) {
                    Icon(Icons.Rounded.Layers, null, tint = Paper, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(5.dp))
                    Text(if (layerMode == MapLayerMode.Trail) "Satellite" else "Trail", color = Paper)
                }
                IconButton(onClick = { packsOpen = true }) {
                    Icon(Icons.Rounded.Download, "Offline map packs", tint = Paper)
                }
                IconButton(onClick = onRefresh, enabled = !loading) {
                    if (loading) CircularProgressIndicator(Modifier.size(20.dp), color = Paper, strokeWidth = 2.dp)
                    else Icon(Icons.Rounded.Refresh, "Refresh map", tint = Paper)
                }
            }
            MapRouteLegend(
                selectedTrailIds = selectedTrailIds,
                modifier = Modifier.padding(top = 5.dp),
            )
            if (layerMode == MapLayerMode.Satellite) {
                Text(
                    "IMAGERY © ESRI · MAXAR · EARTHSTAR · GIS COMMUNITY",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFFB7C8B5),
                    modifier = Modifier.padding(top = 3.dp),
                )
            }
        }

        if (loading && sightings.isEmpty()) {
            Column(
                Modifier.align(Alignment.Center).background(Paper, RoundedCornerShape(4.dp)).padding(22.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                CircularProgressIndicator(color = Moss, strokeWidth = 2.dp)
                Text("Plotting field records…", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 12.dp))
            }
        }

        AnimatedVisibility(
            visible = selected != null,
            modifier = Modifier.align(Alignment.BottomCenter).padding(start = 12.dp, end = 12.dp, bottom = 92.dp),
            enter = slideInVertically { it } + fadeIn(),
            exit = slideOutVertically { it } + fadeOut(),
        ) {
            selected?.let { sighting ->
                SightingInspector(
                    sighting = sighting,
                    openingPhoto = openingPhotoId == sighting.id,
                    onDismiss = { selected = null },
                    onOpenHike = { sighting.hikeId?.let(onOpenHike) },
                    onOpenPhoto = { onOpenPhoto(sighting) },
                )
            }
        }
    }

    if (packsOpen) {
        OfflineMapPacksSheet(
            viewport = viewport,
            layerMode = layerMode,
            onDismiss = { packsOpen = false },
        )
    }
}

@Composable
private fun OfflineMapPacksSheet(
    viewport: MapViewport?,
    layerMode: MapLayerMode,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val manager = remember { OfflineMapPacks(context) }
    var packs by remember { mutableStateOf<List<OfflineMapPack>>(emptyList()) }
    var downloading by remember { mutableStateOf<OfflineMapPack?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    fun refresh() {
        manager.list(onResult = { packs = it }, onError = { error = it })
    }
    LaunchedEffect(Unit) { refresh() }

    val satelliteStyle = BuildConfig.SATELLITE_OFFLINE_STYLE_URL
    val styleUrl = if (layerMode == MapLayerMode.Trail) BuildConfig.TRAIL_MAP_STYLE_URL else satelliteStyle
    val layerLabel = if (layerMode == MapLayerMode.Trail) "Trail" else "Satellite"

    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Paper) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 34.dp),
        ) {
            Text("FIELD MAPS", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text("Keep this area offline", style = MaterialTheme.typography.headlineMedium, color = Ink)
            Text(
                "Save the map area currently on screen for use without a connection.",
                style = MaterialTheme.typography.bodyMedium,
                color = InkMuted,
                modifier = Modifier.padding(top = 5.dp),
            )
            if (layerMode == MapLayerMode.Satellite && satelliteStyle.isBlank()) {
                Text(
                    "Satellite maps can be viewed online, but they aren't available to download yet.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color(0xFF8F3D32),
                    modifier = Modifier.padding(top = 14.dp),
                )
            }
            Button(
                onClick = {
                    val area = viewport ?: return@Button
                    error = null
                    manager.download(
                        name = "$layerLabel field pack · ${LocalDate.now()}",
                        layer = layerLabel.lowercase(Locale.US),
                        styleUrl = styleUrl,
                        bounds = area.bounds,
                        minZoom = (area.zoom - 2).coerceAtLeast(6.0),
                        maxZoom = (area.zoom + 3).coerceIn(10.0, 15.0),
                        pixelRatio = context.resources.displayMetrics.density.coerceAtMost(2f),
                        onProgress = { downloading = it },
                        onComplete = { downloading = null; refresh() },
                        onError = { downloading = null; error = it },
                    )
                },
                enabled = viewport != null && styleUrl.isNotBlank() && downloading == null,
                modifier = Modifier.fillMaxWidth().padding(top = 18.dp).height(52.dp),
            ) {
                Icon(Icons.Rounded.Download, null)
                Spacer(Modifier.width(8.dp))
                Text("Download $layerLabel view")
            }
            downloading?.let { pack ->
                Text("Downloading ${pack.name}", style = MaterialTheme.typography.titleSmall, color = Ink, modifier = Modifier.padding(top = 14.dp))
                LinearProgressIndicator(
                    progress = { pack.progress },
                    modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
                    color = Trail,
                )
                Text(formatBytes(pack.bytes), style = MaterialTheme.typography.bodySmall, color = InkMuted, modifier = Modifier.padding(top = 4.dp))
            }
            error?.let {
                Text(it, style = MaterialTheme.typography.bodyMedium, color = Color(0xFF8F3D32), modifier = Modifier.padding(top = 12.dp))
            }
            if (packs.isNotEmpty()) {
                Text("SAVED ON THIS PHONE", style = MaterialTheme.typography.labelSmall, color = InkMuted, modifier = Modifier.padding(top = 24.dp, bottom = 5.dp))
                packs.forEach { pack ->
                    Row(
                        Modifier.fillMaxWidth().padding(vertical = 9.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(pack.name, style = MaterialTheme.typography.titleSmall, color = Ink)
                            Text(
                                "${if (pack.complete) "Ready offline" else "Paused"} · ${formatBytes(pack.bytes)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = InkMuted,
                            )
                        }
                        IconButton(onClick = {
                            manager.delete(pack.id, onComplete = ::refresh, onError = { error = it })
                        }) {
                            Icon(Icons.Rounded.DeleteOutline, "Delete map pack", tint = InkMuted)
                        }
                    }
                }
            }
            OutlinedButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) {
                Text("Done")
            }
        }
    }
}

@Composable
private fun SightingInspector(
    sighting: Sighting,
    openingPhoto: Boolean,
    onDismiss: () -> Unit,
    onOpenHike: () -> Unit,
    onOpenPhoto: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().background(Paper, RoundedCornerShape(8.dp)).padding(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(94.dp)
                .background(Moss)
                .clickable(enabled = !openingPhoto, onClick = onOpenPhoto),
            contentAlignment = Alignment.Center,
        ) {
            AsyncImage(
                sighting.thumbnailUrl.ifBlank { sighting.url },
                "Open ${sighting.speciesName.ifBlank { sighting.caption.ifBlank { "field photograph" } }}",
                Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop,
            )
            if (openingPhoto) {
                Box(Modifier.fillMaxSize().background(Color(0x99183A2D)))
                CircularProgressIndicator(Modifier.size(24.dp), color = Paper, strokeWidth = 2.dp)
            }
        }
        Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
            Text(
                sighting.speciesName.ifBlank { "Field photograph" },
                style = MaterialTheme.typography.titleMedium,
                color = Ink,
                maxLines = 2,
            )
            Text(sighting.hikeTitle, style = MaterialTheme.typography.bodyMedium, color = InkMuted, maxLines = 1)
            Text(formatMapDate(sighting.takenAt ?: sighting.hikeDate), style = MaterialTheme.typography.labelMedium, color = TrailText)
            if (sighting.hikeId != null) {
                Button(
                    onClick = onOpenHike,
                    enabled = !openingPhoto,
                    modifier = Modifier.padding(top = 7.dp).height(38.dp),
                ) {
                    Icon(Icons.Rounded.Route, null, Modifier.size(17.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Open journal")
                }
            }
        }
        IconButton(onClick = onDismiss, modifier = Modifier.align(Alignment.Top)) {
            Icon(Icons.Rounded.Close, "Close", tint = InkMuted)
        }
    }
}

@Composable
internal fun HikeJournalMap(
    sightings: List<Sighting>,
    selectedSighting: Sighting?,
    layerMode: MapLayerMode,
    onSelect: (Sighting) -> Unit,
    onViewportChanged: (MapViewport) -> Unit,
    modifier: Modifier = Modifier,
    routeSegments: List<List<RoutePoint>> = emptyList(),
    focusedSightingId: String? = null,
    currentPoint: RoutePoint? = null,
    followCurrentPoint: Boolean = false,
    selectedTrailIds: Set<String>,
) {
    val context = LocalContext.current
    val controller = remember { NativeMapController() }
    val showTrailOverlays = selectedTrailIds.isNotEmpty()
    var trailOverlays by remember { mutableStateOf<FeatureCollection?>(null) }
    var trailOverlayIndex by remember { mutableStateOf<FloridaTrailSegmentIndex?>(null) }
    var classifiedRoutes by remember(routeSegments) {
        mutableStateOf(classifyFloridaTrailOverlap(routeSegments, null))
    }
    LaunchedEffect(selectedTrailIds) {
        if (showTrailOverlays) {
            val data = NationalScenicTrailOverlayData.load(context, selectedTrailIds)
            val index = withContext(Dispatchers.Default) {
                data?.let { FloridaTrailSegmentIndex(it.trailOverlaySegments()) }
            }
            trailOverlays = data
            trailOverlayIndex = index
        } else {
            trailOverlays = null
            trailOverlayIndex = null
        }
    }
    LaunchedEffect(routeSegments, showTrailOverlays, trailOverlayIndex) {
        classifiedRoutes = withContext(Dispatchers.Default) {
            classifyFloridaTrailOverlap(
                routes = routeSegments,
                trailIndex = trailOverlayIndex.takeIf { showTrailOverlays },
            )
        }
    }
    controller.tapRadiusPx = 24f * context.resources.displayMetrics.density
    controller.onSelect = onSelect
    controller.onViewportChanged = onViewportChanged
    controller.sightingsById = sightings.associateBy { it.id }
    controller.selectedSighting = selectedSighting
    controller.focusedSightingId = focusedSightingId
    val mapView = remember {
        MapLibre.getInstance(context)
        val options = MapLibreMapOptions.createFromAttributes(context).textureMode(true)
        MapView(context, options).apply { onCreate(Bundle()) }
    }

    DisposableEffect(mapView) {
        mapView.onStart()
        mapView.onResume()
        onDispose {
            mapView.onPause()
            mapView.onStop()
            mapView.onDestroy()
        }
    }

    AndroidView(
        factory = {
            mapView.apply {
                getMapAsync { map ->
                    controller.attach(
                        map = map,
                        sightings = sightings,
                        routeSegments = classifiedRoutes,
                        floridaTrail = trailOverlays,
                        showFloridaTrail = showTrailOverlays,
                        currentPoint = currentPoint,
                    )
                }
            }
        },
        update = {
            controller.updateLayer(
                nextLayerMode = layerMode,
                nextShowFloridaTrail = showTrailOverlays,
                sightings = sightings,
                routeSegments = classifiedRoutes,
                floridaTrail = trailOverlays,
                currentPoint = currentPoint,
            )
            controller.updateMapData(sightings, classifiedRoutes, trailOverlays)
            controller.updateSelectedSighting(selectedSighting)
            controller.updateCurrentPoint(currentPoint, followCurrentPoint)
        },
        modifier = modifier,
    )
}

private class NativeMapController {
    var onSelect: (Sighting) -> Unit = {}
    var sightingsById: Map<String, Sighting> = emptyMap()
    var onViewportChanged: (MapViewport) -> Unit = {}
    var selectedSighting: Sighting? = null
    var focusedSightingId: String? = null
    var currentPoint: RoutePoint? = null
    var followCurrentPoint: Boolean = false
    var tapRadiusPx: Float = 24f
    private var map: MapLibreMap? = null
    private var fitted = false
    private var layerMode = MapLayerMode.Satellite
    private var showFloridaTrail = true
    private var clickListenerAttached = false
    private var lastFollowedPoint: RoutePoint? = null
    private var renderedSightings: List<Sighting>? = null
    private var renderedRouteSegments: List<ClassifiedRouteSegment>? = null
    private var renderedFloridaTrail: FeatureCollection? = null

    fun attach(
        map: MapLibreMap,
        sightings: List<Sighting>,
        routeSegments: List<ClassifiedRouteSegment>,
        floridaTrail: FeatureCollection?,
        showFloridaTrail: Boolean,
        currentPoint: RoutePoint?,
    ) {
        this.map = map
        this.showFloridaTrail = showFloridaTrail
        if (!clickListenerAttached) {
            clickListenerAttached = true
            map.addOnMapClickListener { latLng ->
                val point = map.projection.toScreenLocation(latLng)
                val features = map.queryRenderedFeatures(
                    RectF(
                        point.x - tapRadiusPx,
                        point.y - tapRadiusPx,
                        point.x + tapRadiusPx,
                        point.y + tapRadiusPx,
                    ),
                    LAYER_ID,
                )
                val id = features.firstOrNull()?.getStringProperty("sighting_id")
                sightingsById[id]?.let(onSelect)
                id != null
            }
            map.addOnCameraIdleListener {
                onViewportChanged(MapViewport(map.projection.visibleRegion.latLngBounds, map.cameraPosition.zoom))
            }
        }
        loadStyle(
            map = map,
            nextLayerMode = layerMode,
            sightings = sightings,
            routeSegments = routeSegments,
            floridaTrail = floridaTrail,
            showFloridaTrail = showFloridaTrail,
            currentPoint = currentPoint,
        )
    }

    fun updateLayer(
        nextLayerMode: MapLayerMode,
        nextShowFloridaTrail: Boolean,
        sightings: List<Sighting>,
        routeSegments: List<ClassifiedRouteSegment>,
        floridaTrail: FeatureCollection?,
        currentPoint: RoutePoint?,
    ) {
        if (nextLayerMode == layerMode && nextShowFloridaTrail == showFloridaTrail) return
        layerMode = nextLayerMode
        showFloridaTrail = nextShowFloridaTrail
        map?.let {
            loadStyle(
                map = it,
                nextLayerMode = nextLayerMode,
                sightings = sightings,
                routeSegments = routeSegments,
                floridaTrail = floridaTrail,
                showFloridaTrail = nextShowFloridaTrail,
                currentPoint = currentPoint,
            )
        }
    }

    private fun loadStyle(
        map: MapLibreMap,
        nextLayerMode: MapLayerMode,
        sightings: List<Sighting>,
        routeSegments: List<ClassifiedRouteSegment>,
        floridaTrail: FeatureCollection?,
        showFloridaTrail: Boolean,
        currentPoint: RoutePoint?,
    ) {
        val builder = if (nextLayerMode == MapLayerMode.Satellite) {
            Style.Builder().fromJson(SATELLITE_STYLE)
        } else {
            Style.Builder().fromUri(BuildConfig.TRAIL_MAP_STYLE_URL)
        }
        map.setStyle(builder) { style ->
            if (showFloridaTrail) {
                style.addSource(
                    GeoJsonSource(
                        FLORIDA_TRAIL_SOURCE_ID,
                        floridaTrail ?: FeatureCollection.fromFeatures(emptyList<Feature>()),
                    ),
                )
            }
            style.addSource(GeoJsonSource(ROUTE_SOURCE_ID, routeFeatureCollection(routeSegments)))
            style.addSource(GeoJsonSource(CURRENT_POSITION_SOURCE_ID, pointFeatureCollection(currentPoint)))
            val source = GeoJsonSource(SOURCE_ID, featureCollection(sightings))
            style.addSource(source)
            style.addSource(
                GeoJsonSource(
                    SELECTED_SOURCE_ID,
                    featureCollection(selectedSighting?.let(::listOf) ?: emptyList()),
                ),
            )
            if (showFloridaTrail) {
                style.addLayer(
                    LineLayer(FLORIDA_TRAIL_HALO_LAYER_ID, FLORIDA_TRAIL_SOURCE_ID).withProperties(
                        lineColor("#4D2B17"),
                        lineWidth(5.5f),
                        lineOpacity(0.58f),
                    ),
                )
                style.addLayer(
                    LineLayer(FLORIDA_TRAIL_LAYER_ID, FLORIDA_TRAIL_SOURCE_ID).withProperties(
                        lineColor(FLORIDA_TRAIL_COLOR),
                        lineWidth(3.5f),
                        lineOpacity(0.94f),
                    ),
                )
            }
            style.addLayer(
                LineLayer(ROUTE_HALO_LAYER_ID, ROUTE_SOURCE_ID).withProperties(
                    lineColor("#263228"),
                    lineWidth(8f),
                    lineOpacity(0.72f),
                ),
            )
            style.addLayer(
                LineLayer(ROUTE_LAYER_ID, ROUTE_SOURCE_ID).withProperties(
                    lineColor(HIKE_ROUTE_COLOR),
                    lineWidth(5f),
                    lineOpacity(0.98f),
                ),
            )
            if (showFloridaTrail) {
                style.addLayer(
                    LineLayer(ROUTE_OVERLAP_LAYER_ID, ROUTE_SOURCE_ID)
                        .withFilter(Expression.eq(Expression.get("overlap"), true))
                        .withProperties(
                            lineColor(ROUTE_OVERLAP_COLOR),
                            lineWidth(5.6f),
                            lineOpacity(1f),
                        ),
                )
            }
            style.addLayer(
                CircleLayer(CURRENT_POSITION_HALO_LAYER_ID, CURRENT_POSITION_SOURCE_ID).withProperties(
                    circleColor("#FFFCF3"),
                    circleRadius(12f),
                    circleOpacity(0.74f),
                ),
            )
            style.addLayer(
                CircleLayer(CURRENT_POSITION_LAYER_ID, CURRENT_POSITION_SOURCE_ID).withProperties(
                    circleColor("#2587D8"),
                    circleRadius(7f),
                    circleOpacity(1f),
                    circleStrokeColor("#183A2D"),
                    circleStrokeWidth(1.5f),
                ),
            )
            style.addLayer(
                CircleLayer(LAYER_ID, SOURCE_ID).withProperties(
                    circleColor(PHOTO_POINT_COLOR),
                    circleRadius(4.5f),
                    circleOpacity(0.88f),
                    circleStrokeColor("#123B4A"),
                    circleStrokeWidth(1.4f),
                ),
            )
            style.addLayer(
                CircleLayer(SELECTED_LAYER_ID, SELECTED_SOURCE_ID).withProperties(
                    circleColor("#F8FAFC"),
                    circleRadius(7.5f),
                    circleOpacity(1f),
                    circleStrokeColor(HIKE_ROUTE_COLOR),
                    circleStrokeWidth(2.4f),
                ),
            )
            renderedSightings = sightings
            renderedRouteSegments = routeSegments
            renderedFloridaTrail = floridaTrail
            updateMapData(sightings, routeSegments, floridaTrail)
            updateSelectedSighting(selectedSighting)
            updateCurrentPoint(currentPoint, followCurrentPoint, force = true)
        }
    }

    fun updateMapData(
        sightings: List<Sighting>,
        routeSegments: List<ClassifiedRouteSegment>,
        floridaTrail: FeatureCollection?,
    ) {
        val currentMap = map ?: return
        currentMap.getStyle { style ->
            if (sightings != renderedSightings) {
                style.getSourceAs<GeoJsonSource>(SOURCE_ID)?.setGeoJson(featureCollection(sightings))
                renderedSightings = sightings
            }
            if (routeSegments != renderedRouteSegments) {
                style.getSourceAs<GeoJsonSource>(ROUTE_SOURCE_ID)?.setGeoJson(
                    routeFeatureCollection(routeSegments),
                )
                renderedRouteSegments = routeSegments
            }
            if (showFloridaTrail && floridaTrail !== renderedFloridaTrail) {
                style.getSourceAs<GeoJsonSource>(FLORIDA_TRAIL_SOURCE_ID)?.setGeoJson(
                    floridaTrail ?: FeatureCollection.fromFeatures(emptyList<Feature>()),
                )
                renderedFloridaTrail = floridaTrail
            }
            if (!fitted && !followCurrentPoint && (sightings.isNotEmpty() || routeSegments.isNotEmpty())) {
                fitted = true
                fitMap(currentMap, sightings, routeSegments)
            }
        }
    }

    fun updateCurrentPoint(point: RoutePoint?, follow: Boolean, force: Boolean = false) {
        val pointChanged = point != currentPoint
        val followJustEnabled = follow && !followCurrentPoint
        currentPoint = point
        followCurrentPoint = follow
        if (pointChanged || force) {
            map?.getStyle { style ->
                style.getSourceAs<GeoJsonSource>(CURRENT_POSITION_SOURCE_ID)?.setGeoJson(
                    pointFeatureCollection(point),
                )
            }
        }
        val currentMap = map ?: return
        if (!follow || point == null || (!force && !followJustEnabled && !pointChanged)) return
        lastFollowedPoint = point
        currentMap.animateCamera(
            CameraUpdateFactory.newCameraPosition(
                CameraPosition.Builder()
                    .target(LatLng(point.latitude, point.longitude))
                    .zoom(currentMap.cameraPosition.zoom.coerceAtLeast(15.0))
                    .build(),
            ),
            if (force) 700 else 450,
        )
    }

    fun updateSelectedSighting(sighting: Sighting?) {
        map?.getStyle { style ->
            style.getSourceAs<GeoJsonSource>(SELECTED_SOURCE_ID)?.setGeoJson(
                featureCollection(sighting?.let(::listOf) ?: emptyList()),
            )
        }
    }

    private fun fitMap(
        map: MapLibreMap,
        sightings: List<Sighting>,
        routeSegments: List<ClassifiedRouteSegment>,
    ) {
        sightings.firstOrNull { it.id == focusedSightingId }?.let { focused ->
            map.animateCamera(
                CameraUpdateFactory.newCameraPosition(
                    CameraPosition.Builder()
                        .target(LatLng(focused.latitude, focused.longitude))
                        .zoom(15.0)
                        .build(),
                ),
                900,
            )
            return
        }
        val points = buildList {
            sightings.forEach { add(LatLng(it.latitude, it.longitude)) }
            routeSegments.flatMap(ClassifiedRouteSegment::points).forEach {
                add(LatLng(it.latitude, it.longitude))
            }
        }
        if (points.size == 1) {
            map.animateCamera(
                CameraUpdateFactory.newCameraPosition(
                    CameraPosition.Builder()
                        .target(points.single())
                        .zoom(12.0)
                        .build(),
                ),
                900,
            )
            return
        }
        val bounds = LatLngBounds.Builder().apply {
            points.forEach(::include)
        }.build()
        map.animateCamera(CameraUpdateFactory.newLatLngBounds(bounds, 90), 1000)
    }

    private fun featureCollection(sightings: List<Sighting>): FeatureCollection {
        val features = sightings.map { sighting ->
            Feature.fromGeometry(Point.fromLngLat(sighting.longitude, sighting.latitude)).apply {
                addStringProperty("sighting_id", sighting.id)
            }
        }
        return FeatureCollection.fromFeatures(features)
    }

    private fun routeFeatureCollection(
        routeSegments: List<ClassifiedRouteSegment>,
    ): FeatureCollection {
        val features = routeSegments
            .filter { it.points.size >= 2 }
            .map { segment ->
                Feature.fromGeometry(
                    LineString.fromLngLats(
                        segment.points.map { point ->
                            Point.fromLngLat(point.longitude, point.latitude)
                        },
                    ),
                ).apply {
                    addBooleanProperty("overlap", segment.overlapsFloridaTrail)
                }
            }
        return FeatureCollection.fromFeatures(features)
    }

    private fun pointFeatureCollection(point: RoutePoint?): FeatureCollection =
        FeatureCollection.fromFeatures(
            point?.let {
                listOf(Feature.fromGeometry(Point.fromLngLat(it.longitude, it.latitude)))
            }.orEmpty(),
        )
}

@Composable
internal fun MapRouteLegend(
    selectedTrailIds: Set<String>,
    modifier: Modifier = Modifier,
    compact: Boolean = false,
) {
    Row(
        modifier,
        horizontalArrangement = Arrangement.spacedBy(if (compact) 9.dp else 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (selectedTrailIds.isNotEmpty()) {
            val selected = NationalScenicTrailOverlays.filter { it.id in selectedTrailIds }
            val trailLabel = if (selected.size == 1) {
                selected.single().shortName
            } else {
                "${selected.size} TRAILS"
            }
            RouteLegendItem(Color(0xFFF47A32), trailLabel)
        }
        RouteLegendItem(Color(0xFF22D3EE), if (compact) "YOU" else "YOUR ROUTE")
        if (selectedTrailIds.isNotEmpty()) {
            RouteLegendItem(Color(0xFFFF4D8D), "SHARED")
        }
    }
}

@Composable
private fun RouteLegendItem(color: Color, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.width(18.dp).height(3.dp).background(color))
        Spacer(Modifier.width(5.dp))
        Text(label, style = MaterialTheme.typography.labelSmall, color = Color(0xFFB7C8B5))
    }
}

private fun formatBytes(bytes: Long): String = when {
    bytes >= 1024L * 1024L -> String.format(Locale.US, "%.1f MB", bytes / (1024.0 * 1024.0))
    bytes >= 1024L -> String.format(Locale.US, "%.0f KB", bytes / 1024.0)
    else -> "$bytes B"
}

private fun formatMapDate(raw: String?): String {
    if (raw.isNullOrBlank()) return "Field record"
    return try {
        LocalDate.parse(raw.take(10)).format(DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US))
    } catch (_: Exception) {
        raw.take(10)
    }
}
