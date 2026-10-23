package com.hikejournal.app.ui

import android.view.View
import android.view.ViewGroup
import android.graphics.RectF
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import com.hikejournal.app.data.MapBounds
import com.hikejournal.app.data.RoutePoint
import com.hikejournal.app.data.Sighting
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

class SightingsMapLoadingTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<ComponentActivity>()

    @Test
    fun lateSummaryFocusesMapAndRequestsPhotosWithoutAnyRouteOrPhotoChange() {
        val bounds = mutableStateOf<MapBounds?>(null)
        val photos = mutableStateOf(emptyList<Sighting>())
        val showsPhotos = mutableStateOf(true)
        val viewport = AtomicReference<MapViewport?>(null)
        val onViewportChanged: (MapViewport) -> Unit = { viewport.set(it) }
        composeRule.setContent {
            HikeJournalMap(
                sightings = photos.value,
                selectedSighting = null,
                layerMode = MapLayerMode.Satellite,
                onSelect = {},
                onViewportChanged = onViewportChanged,
                selectedTrailIds = emptySet(),
                showsPhotos = showsPhotos.value,
                initialBounds = bounds.value,
                waitForInitialBounds = true,
                modifier = Modifier.fillMaxSize(),
            )
        }

        val map = awaitMapStyle()
        assertNull(viewport.get())
        composeRule.runOnIdle {
            bounds.value = MapBounds(west = -81.6, south = 28.2, east = -81.1, north = 28.7)
        }

        composeRule.waitUntil(10_000) { viewport.get()?.zoom?.let { it > 5 } == true }
        assertTrue(viewport.get()!!.bounds.contains(photoLocation))

        // Simulate the viewport response and exercise the actual rendered layer,
        // including the display toggle that previously could not recover startup.
        composeRule.runOnIdle {
            photos.value = listOf(Sighting(
                id = "mapped-photo", hikeId = "hike", hikeTitle = "Pine Loop",
                hikeDate = "2026-10-23", locationName = "Pine Woods", url = "",
                caption = "", takenAt = null, latitude = photoLocation.latitude,
                longitude = photoLocation.longitude, speciesName = "", scientificName = "",
                confirmed = false,
            ))
        }
        awaitRenderedPhotoCount(map, 1)
        composeRule.runOnIdle { showsPhotos.value = false }
        awaitRenderedPhotoCount(map, 0)
        composeRule.runOnIdle { showsPhotos.value = true }
        awaitRenderedPhotoCount(map, 1)

        composeRule.runOnIdle {
            map.moveCamera(CameraUpdateFactory.newLatLngZoom(LatLng(28.6, -81.3), 12.0))
        }
        composeRule.waitUntil(10_000) { viewport.get()?.zoom?.let { it >= 12.0 } == true }
    }

    @Test
    fun finishingSummaryWithoutBoundsFitsUnchangedCachedRoutes() {
        val waiting = mutableStateOf(true)
        val viewport = AtomicReference<MapViewport?>(null)
        val onViewportChanged: (MapViewport) -> Unit = { viewport.set(it) }
        val routes = listOf(listOf(RoutePoint(28.2, -81.6), RoutePoint(28.7, -81.1)))
        composeRule.setContent {
            HikeJournalMap(
                sightings = emptyList(), selectedSighting = null,
                routeSegments = routes, layerMode = MapLayerMode.Satellite,
                onSelect = {}, onViewportChanged = onViewportChanged,
                selectedTrailIds = emptySet(), waitForInitialBounds = waiting.value,
                modifier = Modifier.fillMaxSize(),
            )
        }
        awaitMapStyle()
        assertNull(viewport.get())
        composeRule.runOnIdle { waiting.value = false }
        composeRule.waitUntil(10_000) { viewport.get()?.zoom?.let { it > 5 } == true }
        assertTrue(viewport.get()!!.bounds.contains(photoLocation))
    }

    @Test
    fun lateSummaryReplacesEarlierCachedRouteFit() {
        val bounds = mutableStateOf<MapBounds?>(null)
        val viewport = AtomicReference<MapViewport?>(null)
        val onViewportChanged: (MapViewport) -> Unit = { viewport.set(it) }
        val routes = listOf(listOf(RoutePoint(37.7, -122.5), RoutePoint(37.8, -122.4)))
        composeRule.setContent {
            HikeJournalMap(
                sightings = emptyList(), selectedSighting = null,
                routeSegments = routes, layerMode = MapLayerMode.Satellite,
                onSelect = {}, onViewportChanged = onViewportChanged,
                selectedTrailIds = emptySet(), initialBounds = bounds.value,
                modifier = Modifier.fillMaxSize(),
            )
        }
        awaitMapStyle()
        composeRule.waitUntil(10_000) { viewport.get()?.bounds?.contains(LatLng(37.75, -122.45)) == true }
        composeRule.runOnIdle {
            bounds.value = MapBounds(west = -81.6, south = 28.2, east = -81.1, north = 28.7)
        }
        composeRule.waitUntil(10_000) { viewport.get()?.bounds?.contains(photoLocation) == true }
    }

    private val photoLocation = LatLng(28.45, -81.35)

    private fun awaitMapStyle(): MapLibreMap {
        val styleReady = AtomicBoolean(false)
        val nativeMap = AtomicReference<MapLibreMap>()
        composeRule.runOnIdle {
            findMapView(composeRule.activity.window.decorView)!!.getMapAsync { map ->
                nativeMap.set(map)
                map.getStyle { styleReady.set(true) }
            }
        }
        composeRule.waitUntil(15_000) { styleReady.get() }
        return nativeMap.get()
    }

    private fun awaitRenderedPhotoCount(map: MapLibreMap, expected: Int) {
        composeRule.waitUntil(10_000) {
            var count = -1
            composeRule.runOnIdle {
                val point = map.projection.toScreenLocation(photoLocation)
                count = map.queryRenderedFeatures(
                    RectF(point.x - 24, point.y - 24, point.x + 24, point.y + 24),
                    "hikejournal-sightings-circles",
                ).size
            }
            count == expected
        }
    }

    private fun findMapView(view: View): MapView? {
        if (view is MapView) return view
        if (view is ViewGroup) {
            for (index in 0 until view.childCount) {
                findMapView(view.getChildAt(index))?.let { return it }
            }
        }
        return null
    }
}
