package com.hikejournal.app.ui

import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.Photo
import org.junit.Assert.assertEquals
import org.junit.Test

class HikeMapScreenTest {
    @Test
    fun `map keeps only geotagged photos and includes an external focused photo`() {
        val mapped = photo("mapped", 28.1, -82.1)
        val unmapped = photo("unmapped", null, null)
        val focused = photo("focused", 28.2, -82.2)
        val hike = Hike(
            id = "hike-1",
            title = "Pine Loop",
            hikeDate = "2026-07-29",
            distanceMiles = 3.2,
            locationName = "Scrub Preserve",
            notes = "",
            isArchived = false,
            coverUrl = "",
            photoCount = 2,
            speciesCount = 0,
            photos = listOf(mapped, unmapped),
        )

        val sightings = hikeMapSightings(hike, focused)

        assertEquals(listOf("mapped", "focused"), sightings.map { it.id })
        assertEquals("1 ROUTE · 1 GEOTAGGED PHOTO", hikeMapSummary(1, 1))
    }

    private fun photo(
        id: String,
        latitude: Double?,
        longitude: Double?,
    ) = Photo(
        id = id,
        hikeId = "hike-1",
        url = "https://example.test/$id.jpg",
        caption = "",
        takenAt = null,
        createdAt = null,
        latitude = latitude,
        longitude = longitude,
        width = 1200,
        height = 800,
        contentType = "image/jpeg",
        processingStatus = "ready",
        species = emptyList(),
    )
}
