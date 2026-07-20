@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.hikejournal.app.ui

import android.os.Bundle
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
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
import androidx.compose.material3.Switch
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
import com.hikejournal.app.data.Sighting
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapLibreMapOptions
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.PropertyFactory.circleColor
import org.maplibre.android.style.layers.PropertyFactory.circleOpacity
import org.maplibre.android.style.layers.PropertyFactory.circleRadius
import org.maplibre.android.style.layers.PropertyFactory.circleStrokeColor
import org.maplibre.android.style.layers.PropertyFactory.circleStrokeWidth
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.Point
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

private const val MAP_STYLE = "https://demotiles.maplibre.org/style.json"
private const val SOURCE_ID = "hikejournal-sightings"
private const val LAYER_ID = "hikejournal-sightings-circles"
private val SATELLITE_STYLE = """
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

private enum class MapLayerMode { Trail, Satellite }

private data class MapViewport(val bounds: LatLngBounds, val zoom: Double)

@Composable
fun SightingsMapScreen(
    sightings: List<Sighting>,
    loading: Boolean,
    onRefresh: () -> Unit,
    onOpenHike: (String) -> Unit,
) {
    var speciesOnly by remember { mutableStateOf(true) }
    var selected by remember { mutableStateOf<Sighting?>(null) }
    var layerMode by remember { mutableStateOf(MapLayerMode.Trail) }
    var viewport by remember { mutableStateOf<MapViewport?>(null) }
    var packsOpen by remember { mutableStateOf(false) }
    val visibleSightings = remember(sightings, speciesOnly) {
        if (speciesOnly) sightings.filter { it.confirmed } else sightings
    }
    LaunchedEffect(speciesOnly) {
        if (speciesOnly && selected?.confirmed == false) selected = null
    }

    Box(Modifier.fillMaxSize().background(Moss)) {
        HikeJournalMap(
            sightings = visibleSightings,
            layerMode = layerMode,
            onSelect = { selected = it },
            onViewportChanged = { viewport = it },
            modifier = Modifier.fillMaxSize(),
        )

        Column(
            Modifier.fillMaxWidth().background(Color(0xF2183A2D)).statusBarsPadding().padding(start = 20.dp, end = 8.dp, top = 12.dp, bottom = 12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("HikeJournal", style = MaterialTheme.typography.titleMedium, color = Color(0xFFB7C8B5))
                    Text("Sightings map", style = MaterialTheme.typography.headlineMedium, color = Paper)
                    Text("${visibleSightings.size} GEOTAGGED FRAMES", style = MaterialTheme.typography.labelSmall, color = Color(0xFFB7C8B5))
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
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Confirmed species only", style = MaterialTheme.typography.labelLarge, color = Paper)
                    Text("Turn off to include every geotagged photo", style = MaterialTheme.typography.bodyMedium, color = Color(0xFFB7C8B5))
                }
                Switch(checked = speciesOnly, onCheckedChange = { speciesOnly = it })
            }
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
                    onDismiss = { selected = null },
                    onOpenHike = { sighting.hikeId?.let(onOpenHike) },
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
    val styleUrl = if (layerMode == MapLayerMode.Trail) MAP_STYLE else satelliteStyle
    val layerLabel = if (layerMode == MapLayerMode.Trail) "Trail" else "Satellite"

    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Paper) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 34.dp),
        ) {
            Text("FIELD MAPS", style = MaterialTheme.typography.labelSmall, color = Trail)
            Text("Keep this area offline", style = MaterialTheme.typography.headlineMedium, color = Ink)
            Text(
                "Download the map currently on screen through zoom 15. Completed packs remain available without service.",
                style = MaterialTheme.typography.bodyMedium,
                color = InkMuted,
                modifier = Modifier.padding(top = 5.dp),
            )
            if (layerMode == MapLayerMode.Satellite && satelliteStyle.isBlank()) {
                Text(
                    "Satellite downloads are locked until an imagery provider with offline-storage rights is configured. Online satellite view still works.",
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
    onDismiss: () -> Unit,
    onOpenHike: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().background(Paper, RoundedCornerShape(8.dp)).padding(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        AsyncImage(
            sighting.url,
            sighting.speciesName.ifBlank { sighting.caption },
            Modifier.size(94.dp).background(Moss),
            contentScale = ContentScale.Crop,
        )
        Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
            Text(
                sighting.speciesName.ifBlank { "Field photograph" },
                style = MaterialTheme.typography.titleMedium,
                color = Ink,
                maxLines = 2,
            )
            Text(sighting.hikeTitle, style = MaterialTheme.typography.bodyMedium, color = InkMuted, maxLines = 1)
            Text(formatMapDate(sighting.takenAt ?: sighting.hikeDate), style = MaterialTheme.typography.labelMedium, color = Trail)
            if (sighting.hikeId != null) {
                Button(onClick = onOpenHike, modifier = Modifier.padding(top = 7.dp).height(38.dp)) {
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
private fun HikeJournalMap(
    sightings: List<Sighting>,
    layerMode: MapLayerMode,
    onSelect: (Sighting) -> Unit,
    onViewportChanged: (MapViewport) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val controller = remember { NativeMapController() }
    controller.onSelect = onSelect
    controller.onViewportChanged = onViewportChanged
    controller.sightingsById = sightings.associateBy { it.id }
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
                getMapAsync { map -> controller.attach(map, sightings) }
            }
        },
        update = {
            controller.updateLayer(layerMode, sightings)
            controller.updateSightings(sightings)
        },
        modifier = modifier,
    )
}

private class NativeMapController {
    var onSelect: (Sighting) -> Unit = {}
    var sightingsById: Map<String, Sighting> = emptyMap()
    var onViewportChanged: (MapViewport) -> Unit = {}
    private var map: MapLibreMap? = null
    private var fitted = false
    private var layerMode = MapLayerMode.Trail
    private var clickListenerAttached = false

    fun attach(map: MapLibreMap, sightings: List<Sighting>) {
        this.map = map
        if (!clickListenerAttached) {
            clickListenerAttached = true
            map.addOnMapClickListener { latLng ->
                val features = map.queryRenderedFeatures(map.projection.toScreenLocation(latLng), LAYER_ID)
                val id = features.firstOrNull()?.getStringProperty("sighting_id")
                sightingsById[id]?.let(onSelect)
                id != null
            }
            map.addOnCameraIdleListener {
                onViewportChanged(MapViewport(map.projection.visibleRegion.latLngBounds, map.cameraPosition.zoom))
            }
        }
        loadStyle(map, layerMode, sightings)
    }

    fun updateLayer(nextLayerMode: MapLayerMode, sightings: List<Sighting>) {
        if (nextLayerMode == layerMode) return
        layerMode = nextLayerMode
        map?.let { loadStyle(it, nextLayerMode, sightings) }
    }

    private fun loadStyle(map: MapLibreMap, nextLayerMode: MapLayerMode, sightings: List<Sighting>) {
        val builder = if (nextLayerMode == MapLayerMode.Satellite) {
            Style.Builder().fromJson(SATELLITE_STYLE)
        } else {
            Style.Builder().fromUri(MAP_STYLE)
        }
        map.setStyle(builder) { style ->
            val source = GeoJsonSource(SOURCE_ID, featureCollection(sightings))
            style.addSource(source)
            style.addLayer(
                CircleLayer(LAYER_ID, SOURCE_ID).withProperties(
                    circleColor("#D17D42"),
                    circleRadius(4.5f),
                    circleOpacity(0.88f),
                    circleStrokeColor("#F4F0E5"),
                    circleStrokeWidth(1.2f),
                ),
            )
            updateSightings(sightings)
        }
    }

    fun updateSightings(sightings: List<Sighting>) {
        val currentMap = map ?: return
        currentMap.getStyle { style ->
            style.getSourceAs<GeoJsonSource>(SOURCE_ID)?.setGeoJson(featureCollection(sightings))
            if (!fitted && sightings.isNotEmpty()) {
                fitted = true
                fitSightings(currentMap, sightings)
            }
        }
    }

    private fun fitSightings(map: MapLibreMap, sightings: List<Sighting>) {
        if (sightings.size == 1) {
            map.animateCamera(
                CameraUpdateFactory.newCameraPosition(
                    CameraPosition.Builder()
                        .target(LatLng(sightings[0].latitude, sightings[0].longitude))
                        .zoom(12.0)
                        .build(),
                ),
                900,
            )
            return
        }
        val bounds = LatLngBounds.Builder().apply {
            sightings.forEach { include(LatLng(it.latitude, it.longitude)) }
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
