@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.hikejournal.app.ui

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.RectF
import android.os.Bundle
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.rounded.Layers
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import coil.compose.AsyncImage
import com.hikejournal.app.data.DiscoveryTaxon
import com.hikejournal.app.data.FieldQuest
import com.hikejournal.app.data.QuestSighting
import com.hikejournal.app.data.QuestSightingsMap
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
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.FillLayer
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.PropertyFactory.circleColor
import org.maplibre.android.style.layers.PropertyFactory.circleOpacity
import org.maplibre.android.style.layers.PropertyFactory.circleRadius
import org.maplibre.android.style.layers.PropertyFactory.circleStrokeColor
import org.maplibre.android.style.layers.PropertyFactory.circleStrokeWidth
import org.maplibre.android.style.layers.PropertyFactory.fillColor
import org.maplibre.android.style.layers.PropertyFactory.fillOpacity
import org.maplibre.android.style.layers.PropertyFactory.lineColor
import org.maplibre.android.style.layers.PropertyFactory.lineDasharray
import org.maplibre.android.style.layers.PropertyFactory.lineOpacity
import org.maplibre.android.style.layers.PropertyFactory.lineWidth
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.Point
import org.maplibre.geojson.Polygon
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.cos

private const val QUEST_MAP_STYLE = "https://demotiles.maplibre.org/style.json"
private const val QUEST_AREA_SOURCE = "field-quest-search-area"
private const val QUEST_AREA_FILL = "field-quest-search-area-fill"
private const val QUEST_AREA_LINE = "field-quest-search-area-line"
private const val QUEST_PUBLIC_SOURCE = "field-quest-public-sightings"
private const val QUEST_PUBLIC_LAYER = "field-quest-public-sightings-circles"
private const val QUEST_OBSCURED_SOURCE = "field-quest-obscured-sightings"
private const val QUEST_OBSCURED_LAYER = "field-quest-obscured-sightings-circles"
private const val QUEST_SELECTED_SOURCE = "field-quest-selected-sighting"
private const val QUEST_SELECTED_LAYER = "field-quest-selected-sighting-circle"
private const val QUEST_USER_SOURCE = "field-quest-user-location"
private const val QUEST_USER_LAYER = "field-quest-user-location-circle"
private val QUEST_SATELLITE_STYLE = """
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

private enum class QuestMapLayerMode { Trail, Satellite }

private data class QuestMapArea(
    val latitude: Double,
    val longitude: Double,
    val radiusKm: Int,
)

private data class QuestUserLocation(
    val latitude: Double,
    val longitude: Double,
)

@Composable
fun QuestSightingsMapScreen(
    quest: FieldQuest,
    taxon: DiscoveryTaxon,
    mapData: QuestSightingsMap?,
    loading: Boolean,
    notice: String?,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
) {
    var selected by remember { mutableStateOf<QuestSighting?>(null) }
    var layerMode by remember { mutableStateOf(QuestMapLayerMode.Satellite) }
    var userLocation by remember { mutableStateOf<QuestUserLocation?>(null) }
    var locationNotice by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    fun requestLocationFix() {
        requestOneShotLocation(
            context = context,
            onLocation = { location ->
                userLocation = QuestUserLocation(location.latitude, location.longitude)
                locationNotice = null
            },
            onUnavailable = {
                locationNotice = "Current location is unavailable. Check GPS and try refresh."
            },
        )
    }
    val locationPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { result ->
        if (result.values.any { it }) {
            requestLocationFix()
        } else {
            locationNotice = "Location is off. Sightings still map normally."
        }
    }
    fun refreshUserLocation() {
        val hasPermission =
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) ==
                PackageManager.PERMISSION_GRANTED ||
                ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) ==
                PackageManager.PERMISSION_GRANTED
        if (hasPermission) {
            requestLocationFix()
        } else {
            locationPermission.launch(
                arrayOf(
                    Manifest.permission.ACCESS_COARSE_LOCATION,
                    Manifest.permission.ACCESS_FINE_LOCATION,
                ),
            )
        }
    }
    LaunchedEffect(Unit) {
        refreshUserLocation()
    }
    val area = mapData?.let {
        QuestMapArea(it.latitude, it.longitude, it.radiusKm)
    } ?: if (quest.latitude != null && quest.longitude != null) {
        QuestMapArea(quest.latitude, quest.longitude, quest.radiusKm)
    } else {
        null
    }
    val sightings = mapData?.sightings.orEmpty()
    val obscuredCount = sightings.count { it.obscured }
    val publicCount = sightings.size - obscuredCount

    Box(Modifier.fillMaxSize().background(Moss)) {
        QuestNativeMap(
            sightings = sightings,
            selectedSighting = selected,
            area = area,
            userLocation = userLocation,
            layerMode = layerMode,
            onSelect = { selected = it },
            modifier = Modifier.fillMaxSize(),
        )

        Column(
            Modifier
                .fillMaxWidth()
                .background(Color(0xF2183A2D))
                .statusBarsPadding()
                .padding(start = 8.dp, end = 8.dp, top = 8.dp, bottom = 11.dp),
        ) {
            Row(verticalAlignment = Alignment.Top) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back to species", tint = Paper)
                }
                Column(Modifier.weight(1f).padding(top = 3.dp)) {
                    Text(
                        if (quest.id.isBlank()) {
                            "NEARBY SPECIES · INATURALIST"
                        } else {
                            "FIELD QUEST · INATURALIST"
                        },
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFFB7C8B5),
                    )
                    Text(
                        taxon.commonName,
                        style = MaterialTheme.typography.headlineMedium,
                        color = Paper,
                        maxLines = 2,
                    )
                    Text(
                        taxon.scientificName,
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color(0xFFB7C8B5),
                        maxLines = 1,
                    )
                }
                IconButton(
                    onClick = {
                        layerMode = if (layerMode == QuestMapLayerMode.Trail) {
                            QuestMapLayerMode.Satellite
                        } else {
                            QuestMapLayerMode.Trail
                        }
                    },
                ) {
                    Icon(Icons.Rounded.Layers, "Change map layer", tint = Paper)
                }
                IconButton(
                    onClick = {
                        onRefresh()
                        refreshUserLocation()
                    },
                    enabled = !loading,
                ) {
                    if (loading) {
                        CircularProgressIndicator(Modifier.size(20.dp), color = Paper, strokeWidth = 2.dp)
                    } else {
                        Icon(Icons.Rounded.Refresh, "Refresh sightings", tint = Paper)
                    }
                }
            }
            Row(
                Modifier.fillMaxWidth().padding(start = 48.dp, end = 8.dp, top = 5.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    mapData?.let { "${it.mappedCount} OF ${it.totalResults} SIGHTINGS MAPPED" }
                        ?: "GATHERING SIGHTINGS…",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFFB7C8B5),
                )
                if (mapData != null) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (userLocation != null) {
                            Box(
                                Modifier.size(8.dp).background(Color(0xFF2587D8), CircleShape),
                            )
                            Text(
                                "YOU · ",
                                style = MaterialTheme.typography.labelSmall,
                                color = Color(0xFF9BCBF2),
                                modifier = Modifier.padding(start = 4.dp),
                            )
                        }
                        Text(
                            if (obscuredCount > 0) "$publicCount exact · $obscuredCount approx"
                            else "$publicCount reports",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFFB7C8B5),
                        )
                    }
                }
            }
            if (layerMode == QuestMapLayerMode.Satellite) {
                Text(
                    "IMAGERY © ESRI · MAXAR · EARTHSTAR · GIS COMMUNITY",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFFB7C8B5),
                    modifier = Modifier.padding(start = 48.dp, top = 3.dp),
                )
            }
        }

        if (loading && mapData == null) {
            Column(
                Modifier
                    .align(Alignment.Center)
                    .background(Paper, RoundedCornerShape(5.dp))
                    .padding(horizontal = 24.dp, vertical = 20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                CircularProgressIndicator(color = Trail, strokeWidth = 2.dp)
                Text(
                    "Plotting nearby reports…",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
        } else if (mapData != null && sightings.isEmpty()) {
            Column(
                Modifier
                    .align(Alignment.Center)
                    .background(Paper, RoundedCornerShape(5.dp))
                    .padding(horizontal = 24.dp, vertical = 20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text("No public coordinates", style = MaterialTheme.typography.titleLarge, color = Ink)
                Text(
                    "iNaturalist has no mappable reports for this quest window.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
        }

        val guidance = notice ?: locationNotice ?: mapData?.sourceGuidance
        if (selected == null && !guidance.isNullOrBlank() && !(loading && mapData == null)) {
            Text(
                guidance,
                style = MaterialTheme.typography.labelSmall,
                color = Paper,
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .background(Color(0xD9183A2D))
                    .padding(horizontal = 18.dp, vertical = 12.dp),
            )
        }

        AnimatedVisibility(
            visible = selected != null,
            modifier = Modifier.align(Alignment.BottomCenter).padding(12.dp),
            enter = slideInVertically { it } + fadeIn(),
            exit = slideOutVertically { it } + fadeOut(),
        ) {
            selected?.let { sighting ->
                QuestSightingInspector(
                    sighting = sighting,
                    speciesName = taxon.commonName,
                    onDismiss = { selected = null },
                )
            }
        }
    }
}

@Composable
private fun QuestSightingInspector(
    sighting: QuestSighting,
    speciesName: String,
    onDismiss: () -> Unit,
) {
    val uriHandler = LocalUriHandler.current
    Row(
        Modifier.fillMaxWidth().background(Paper, RoundedCornerShape(8.dp)).padding(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (sighting.photoUrl.isNotBlank()) {
            AsyncImage(
                model = sighting.photoUrl,
                contentDescription = speciesName,
                modifier = Modifier.size(94.dp).background(Moss),
                contentScale = ContentScale.Crop,
            )
        } else {
            Box(
                Modifier.size(94.dp).background(Color(0xFFD6D2C2)),
                contentAlignment = Alignment.Center,
            ) {
                Text("iNaturalist", style = MaterialTheme.typography.labelSmall, color = InkMuted)
            }
        }
        Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
            Text(speciesName, style = MaterialTheme.typography.titleMedium, color = Ink, maxLines = 2)
            Text(
                listOf(
                    sighting.observer.takeIf { it.isNotBlank() }?.let { "@$it" },
                    formatQuestMapDate(sighting.observedOn),
                ).filterNotNull().joinToString(" · "),
                style = MaterialTheme.typography.bodyMedium,
                color = InkMuted,
                maxLines = 1,
            )
            Text(
                if (sighting.obscured) {
                    "Approximate location · obscured by iNaturalist"
                } else {
                    sighting.positionalAccuracyMeters?.let { "Reported accuracy · $it m" }
                        ?: "Public reported location"
                },
                style = MaterialTheme.typography.labelSmall,
                color = if (sighting.obscured) TrailText else Moss,
                maxLines = 2,
            )
            if (sighting.uri.isNotBlank()) {
                Button(
                    onClick = { uriHandler.openUri(sighting.uri) },
                    modifier = Modifier.padding(top = 7.dp).height(38.dp),
                ) {
                    Text("Open observation")
                    Spacer(Modifier.width(5.dp))
                    Icon(Icons.AutoMirrored.Rounded.OpenInNew, null, Modifier.size(16.dp))
                }
            }
        }
        TextButton(onClick = onDismiss, modifier = Modifier.align(Alignment.Top)) {
            Text("Close")
        }
    }
}

@Composable
private fun QuestNativeMap(
    sightings: List<QuestSighting>,
    selectedSighting: QuestSighting?,
    area: QuestMapArea?,
    userLocation: QuestUserLocation?,
    layerMode: QuestMapLayerMode,
    onSelect: (QuestSighting) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val controller = remember { QuestNativeMapController() }
    controller.tapRadiusPx = 24f * context.resources.displayMetrics.density
    controller.onSelect = onSelect
    controller.sightingsById = sightings.associateBy { it.id }
    controller.selectedSighting = selectedSighting
    controller.area = area
    controller.userLocation = userLocation
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
                getMapAsync { map -> controller.attach(map, sightings, area, userLocation) }
            }
        },
        update = {
            controller.updateLayer(layerMode, sightings, area, userLocation)
            controller.updateSightings(sightings, area)
            controller.updateSelectedSighting(selectedSighting)
            controller.updateUserLocation(userLocation)
        },
        modifier = modifier,
    )
}

private class QuestNativeMapController {
    var onSelect: (QuestSighting) -> Unit = {}
    var sightingsById: Map<String, QuestSighting> = emptyMap()
    var selectedSighting: QuestSighting? = null
    var area: QuestMapArea? = null
    var userLocation: QuestUserLocation? = null
    var tapRadiusPx: Float = 24f
    private var map: MapLibreMap? = null
    private var fitted = false
    private var layerMode = QuestMapLayerMode.Satellite
    private var clickListenerAttached = false

    fun attach(
        map: MapLibreMap,
        sightings: List<QuestSighting>,
        area: QuestMapArea?,
        userLocation: QuestUserLocation?,
    ) {
        this.map = map
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
                    QUEST_SELECTED_LAYER,
                    QUEST_PUBLIC_LAYER,
                    QUEST_OBSCURED_LAYER,
                )
                val id = features.firstOrNull()?.getStringProperty("sighting_id")
                sightingsById[id]?.let(onSelect)
                id != null
            }
        }
        loadStyle(map, layerMode, sightings, area, userLocation)
    }

    fun updateLayer(
        nextLayerMode: QuestMapLayerMode,
        sightings: List<QuestSighting>,
        area: QuestMapArea?,
        userLocation: QuestUserLocation?,
    ) {
        if (nextLayerMode == layerMode) return
        layerMode = nextLayerMode
        map?.let { loadStyle(it, nextLayerMode, sightings, area, userLocation) }
    }

    private fun loadStyle(
        map: MapLibreMap,
        nextLayerMode: QuestMapLayerMode,
        sightings: List<QuestSighting>,
        area: QuestMapArea?,
        userLocation: QuestUserLocation?,
    ) {
        val builder = if (nextLayerMode == QuestMapLayerMode.Satellite) {
            Style.Builder().fromJson(QUEST_SATELLITE_STYLE)
        } else {
            Style.Builder().fromUri(QUEST_MAP_STYLE)
        }
        map.setStyle(builder) { style ->
            style.addSource(GeoJsonSource(QUEST_AREA_SOURCE, areaFeatureCollection(area)))
            style.addSource(
                GeoJsonSource(
                    QUEST_PUBLIC_SOURCE,
                    sightingsFeatureCollection(sightings.filterNot { it.obscured }),
                ),
            )
            style.addSource(
                GeoJsonSource(
                    QUEST_OBSCURED_SOURCE,
                    sightingsFeatureCollection(sightings.filter { it.obscured }),
                ),
            )
            style.addSource(
                GeoJsonSource(
                    QUEST_SELECTED_SOURCE,
                    sightingsFeatureCollection(selectedSighting?.let(::listOf) ?: emptyList()),
                ),
            )
            style.addSource(
                GeoJsonSource(
                    QUEST_USER_SOURCE,
                    userLocationFeatureCollection(userLocation),
                ),
            )
            style.addLayer(
                FillLayer(QUEST_AREA_FILL, QUEST_AREA_SOURCE).withProperties(
                    fillColor("#D17D42"),
                    fillOpacity(0.08f),
                ),
            )
            style.addLayer(
                LineLayer(QUEST_AREA_LINE, QUEST_AREA_SOURCE).withProperties(
                    lineColor("#B2673A"),
                    lineWidth(1.5f),
                    lineOpacity(0.9f),
                    lineDasharray(arrayOf(3f, 2f)),
                ),
            )
            style.addLayer(
                CircleLayer(QUEST_PUBLIC_LAYER, QUEST_PUBLIC_SOURCE).withProperties(
                    circleColor("#D17D42"),
                    circleRadius(5f),
                    circleOpacity(0.92f),
                    circleStrokeColor("#F4F0E5"),
                    circleStrokeWidth(1.4f),
                ),
            )
            style.addLayer(
                CircleLayer(QUEST_OBSCURED_LAYER, QUEST_OBSCURED_SOURCE).withProperties(
                    circleColor("#E5B766"),
                    circleRadius(6f),
                    circleOpacity(0.88f),
                    circleStrokeColor("#664A22"),
                    circleStrokeWidth(1.5f),
                ),
            )
            style.addLayer(
                CircleLayer(QUEST_SELECTED_LAYER, QUEST_SELECTED_SOURCE).withProperties(
                    circleColor("#F4F0E5"),
                    circleRadius(8f),
                    circleOpacity(1f),
                    circleStrokeColor("#183A2D"),
                    circleStrokeWidth(2.2f),
                ),
            )
            style.addLayer(
                CircleLayer(QUEST_USER_LAYER, QUEST_USER_SOURCE).withProperties(
                    circleColor("#2587D8"),
                    circleRadius(8f),
                    circleOpacity(1f),
                    circleStrokeColor("#F4F0E5"),
                    circleStrokeWidth(3f),
                ),
            )
            updateSightings(sightings, area)
            updateSelectedSighting(selectedSighting)
            updateUserLocation(userLocation)
        }
    }

    fun updateSightings(sightings: List<QuestSighting>, area: QuestMapArea?) {
        val currentMap = map ?: return
        currentMap.getStyle { style ->
            style.getSourceAs<GeoJsonSource>(QUEST_AREA_SOURCE)?.setGeoJson(areaFeatureCollection(area))
            style.getSourceAs<GeoJsonSource>(QUEST_PUBLIC_SOURCE)?.setGeoJson(
                sightingsFeatureCollection(sightings.filterNot { it.obscured }),
            )
            style.getSourceAs<GeoJsonSource>(QUEST_OBSCURED_SOURCE)?.setGeoJson(
                sightingsFeatureCollection(sightings.filter { it.obscured }),
            )
            if (!fitted && (sightings.isNotEmpty() || area != null)) {
                fitted = true
                fitMap(currentMap, sightings, area)
            }
        }
    }

    fun updateSelectedSighting(sighting: QuestSighting?) {
        map?.getStyle { style ->
            style.getSourceAs<GeoJsonSource>(QUEST_SELECTED_SOURCE)?.setGeoJson(
                sightingsFeatureCollection(sighting?.let(::listOf) ?: emptyList()),
            )
        }
    }

    fun updateUserLocation(location: QuestUserLocation?) {
        map?.getStyle { style ->
            style.getSourceAs<GeoJsonSource>(QUEST_USER_SOURCE)?.setGeoJson(
                userLocationFeatureCollection(location),
            )
        }
    }

    private fun fitMap(
        map: MapLibreMap,
        sightings: List<QuestSighting>,
        area: QuestMapArea?,
    ) {
        if (sightings.size == 1 && area == null) {
            map.animateCamera(
                CameraUpdateFactory.newCameraPosition(
                    CameraPosition.Builder()
                        .target(LatLng(sightings[0].latitude, sightings[0].longitude))
                        .zoom(13.0)
                        .build(),
                ),
                900,
            )
            return
        }
        val bounds = LatLngBounds.Builder().apply {
            sightings.forEach { include(LatLng(it.latitude, it.longitude)) }
            area?.let {
                val latitudeDelta = it.radiusKm / 111.32
                val longitudeDelta = it.radiusKm / (111.32 * cos(Math.toRadians(it.latitude)))
                include(LatLng(it.latitude - latitudeDelta, it.longitude - longitudeDelta))
                include(LatLng(it.latitude + latitudeDelta, it.longitude + longitudeDelta))
            }
        }.build()
        map.animateCamera(CameraUpdateFactory.newLatLngBounds(bounds, 110), 1000)
    }
}

private fun sightingsFeatureCollection(sightings: List<QuestSighting>): FeatureCollection =
    FeatureCollection.fromFeatures(
        sightings.map { sighting ->
            Feature.fromGeometry(Point.fromLngLat(sighting.longitude, sighting.latitude)).apply {
                addStringProperty("sighting_id", sighting.id)
            }
        },
    )

private fun userLocationFeatureCollection(location: QuestUserLocation?): FeatureCollection =
    FeatureCollection.fromFeatures(
        location?.let {
            listOf(Feature.fromGeometry(Point.fromLngLat(it.longitude, it.latitude)))
        } ?: emptyList(),
    )

private fun areaFeatureCollection(area: QuestMapArea?): FeatureCollection {
    if (area == null) return FeatureCollection.fromFeatures(emptyList())
    val latitudeRadians = Math.toRadians(area.latitude)
    val points = (0..72).map { index ->
        val angle = Math.toRadians(index * 5.0)
        val latitude = area.latitude + (area.radiusKm / 111.32) * cos(angle)
        val longitude = area.longitude +
            (area.radiusKm / (111.32 * cos(latitudeRadians))) * kotlin.math.sin(angle)
        Point.fromLngLat(longitude, latitude)
    }
    return FeatureCollection.fromFeatures(
        listOf(Feature.fromGeometry(Polygon.fromLngLats(listOf(points)))),
    )
}

private fun formatQuestMapDate(raw: String): String {
    if (raw.isBlank()) return "Date not reported"
    return try {
        LocalDate.parse(raw.take(10)).format(DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US))
    } catch (_: Exception) {
        raw.take(10)
    }
}
