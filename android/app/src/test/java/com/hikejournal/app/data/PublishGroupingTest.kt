package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PublishGroupingTest {
    @Test
    fun `same species photos within time and distance become one proposed group`() {
        val groups = buildPublishObservationGroups(
            listOf(
                publishItem("a", "2026-08-05T10:00:00Z", 28.60000, -81.10000),
                publishItem("b", "2026-08-05T10:08:00Z", 28.60020, -81.10000),
                publishItem("late", "2026-08-05T10:16:00Z", 28.60000, -81.10000),
                publishItem("other", "2026-08-05T10:01:00Z", 28.60001, -81.10000, taxonId = 200),
            ),
        )

        assertEquals(listOf(2, 1, 1), groups.map { it.items.size })
        assertEquals(listOf("observation-a", "observation-b"), groups.first().observationIds)
        assertTrue(groups.first().maxDistanceMeters < 50.0)
    }

    @Test
    fun `splitting a proposed group produces a valid individual and grouped post`() {
        val proposed = buildPublishObservationGroups(
            listOf(
                publishItem("a", "2026-08-05T10:00:00Z", 28.60000, -81.10000),
                publishItem("b", "2026-08-05T10:01:00Z", 28.60001, -81.10000),
                publishItem("c", "2026-08-05T10:02:00Z", 28.60002, -81.10000),
            ),
        )

        val split = splitPublishObservationGroups(proposed, setOf("photo-b"))

        assertEquals(listOf(2, 1), split.map { it.items.size })
        assertEquals(listOf("observation-a", "observation-c"), split.first().observationIds)
        assertEquals(listOf("observation-b"), split.last().observationIds)
    }

    private fun publishItem(
        suffix: String,
        takenAt: String,
        latitude: Double,
        longitude: Double,
        taxonId: Long? = 100,
        hikeId: String? = "hike-1",
    ): PublishItem = PublishItem(
        id = "observation-$suffix",
        photo = Photo(
            id = "photo-$suffix",
            hikeId = hikeId,
            url = "https://example.test/$suffix.jpg",
            caption = "",
            takenAt = takenAt,
            createdAt = null,
            latitude = latitude,
            longitude = longitude,
            width = null,
            height = null,
            contentType = "image/jpeg",
            processingStatus = "ready",
            species = emptyList(),
        ),
        hikeId = hikeId,
        hikeTitle = "Test outing",
        hikeDate = "2026-08-05",
        locationName = "",
        taxonId = taxonId,
        commonName = "Test species",
        scientificName = "Species testus",
        state = "ready",
        inatObservationId = null,
        inatUrl = "",
        postedAt = null,
        photoAttached = null,
        relatedObservationIds = listOf("observation-$suffix"),
        relatedPhotoCount = 1,
    )
}
