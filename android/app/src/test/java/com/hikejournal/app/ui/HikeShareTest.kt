package com.hikejournal.app.ui

import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.RoutePoint
import java.time.ZoneOffset
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HikeShareTest {
    @Test
    fun `social carousel reserves one item for the trail card`() {
        val photos = List(24) { index -> photo("photo-$index") }

        assertEquals(19, socialSharePhotos(photos).size)
        assertEquals(20, socialSharePhotos(photos).size + 1)
    }

    @Test
    fun `videos are not offered as hike photos`() {
        val photos = listOf(
            photo("image"),
            photo("video", contentType = "video/mp4"),
            photo("missing").copy(url = ""),
        )

        assertEquals(listOf("image"), socialSharePhotos(photos).map(Photo::id))
    }

    @Test
    fun `route projection fits its drawing plane and preserves direction`() {
        val projected = projectShareRoute(
            routeSegments = listOf(
                listOf(
                    RoutePoint(28.0, -82.0),
                    RoutePoint(28.2, -81.8),
                    RoutePoint(28.1, -81.7),
                )
            ),
            width = 900f,
            height = 500f,
            padding = 40f,
        ).single()

        assertTrue(projected.all { it.x in 40f..860f && it.y in 40f..460f })
        assertTrue(projected.first().x < projected.last().x)
        assertTrue(projected[1].y < projected.first().y)
    }

    @Test
    fun `share details use route start time distance and active duration`() {
        val hike = hike().copy(
            routeStartedAt = "2026-07-20T15:22:00Z",
            distanceMiles = 8.01,
            durationSeconds = 11_475,
        )

        assertEquals("Monday, July 20 · 3:22 PM", hikeShareDateTime(hike, ZoneOffset.UTC))
        assertEquals("8.01", hikeShareDistance(hike))
        assertEquals("3:11:15", hikeShareDuration(hike.durationSeconds))
    }

    private fun hike() = Hike(
        id = "hike-1",
        title = "Pine Loop",
        hikeDate = "2026-07-20",
        distanceMiles = 3.2,
        locationName = "Pine Woods",
        notes = "",
        isArchived = false,
        coverUrl = "",
        photoCount = 0,
        speciesCount = 0,
    )

    private fun photo(id: String, contentType: String = "image/jpeg") = Photo(
        id = id,
        hikeId = "hike-1",
        url = "https://images.example/$id.jpg",
        caption = "",
        takenAt = null,
        createdAt = null,
        latitude = null,
        longitude = null,
        width = null,
        height = null,
        contentType = contentType,
        processingStatus = "ready",
        species = emptyList(),
    )
}
