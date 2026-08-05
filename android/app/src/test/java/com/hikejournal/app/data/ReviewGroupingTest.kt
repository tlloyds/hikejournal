package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ReviewGroupingTest {
    @Test
    fun `nearby photos from one outing become one proposed group`() {
        val groups = buildReviewPhotoGroups(
            listOf(
                reviewItem("a", "2026-08-05T10:00:00Z", 28.60000, -81.10000),
                reviewItem("b", "2026-08-05T10:01:00Z", 28.60005, -81.10000),
                reviewItem("far", "2026-08-05T10:01:00Z", 28.60100, -81.10000),
                reviewItem("other-hike", "2026-08-05T10:01:00Z", 28.60001, -81.10000, hikeId = "hike-2"),
            ),
        )

        assertEquals(listOf(2, 1, 1), groups.map { it.items.size })
        assertEquals(listOf("a", "b"), groups.first().photoIds)
        assertTrue(groups.first().maxDistanceMeters in 0.0..12.0)
    }

    @Test
    fun `splitting one photo keeps the rest grouped`() {
        val proposed = buildReviewPhotoGroups(
            listOf(
                reviewItem("a", "2026-08-05T10:00:00Z", 28.60000, -81.10000),
                reviewItem("b", "2026-08-05T10:01:00Z", 28.60005, -81.10000),
                reviewItem("c", "2026-08-05T10:01:30Z", 28.60006, -81.10000),
            ),
        )

        val split = splitReviewPhotoGroups(proposed, setOf("b"))

        assertEquals(listOf(2, 1), split.map { it.items.size })
        assertEquals(listOf("a", "c"), split.first().photoIds)
        assertEquals(listOf("b"), split.last().photoIds)
    }

    private fun reviewItem(
        id: String,
        takenAt: String,
        latitude: Double,
        longitude: Double,
        hikeId: String? = "hike-1",
    ): ReviewItem = ReviewItem(
        id = id,
        photo = Photo(
            id = id,
            hikeId = hikeId,
            url = "https://example.test/$id.jpg",
            caption = "",
            takenAt = takenAt,
            createdAt = null,
            latitude = latitude,
            longitude = longitude,
            width = null,
            height = null,
            contentType = "image/jpeg",
            processingStatus = "in_review",
            species = emptyList(),
        ),
        hikeId = hikeId,
        hikeTitle = "Test outing",
        hikeDate = "2026-08-05",
        locationName = "",
        state = "waiting",
        observationId = null,
        candidates = emptyList(),
    )
}
