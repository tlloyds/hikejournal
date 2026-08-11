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

    @Test
    fun `large review plans are split at the companion group limit without reordering`() {
        val groups = (1..121).map { index -> listOf("photo-$index") }

        val chunks = chunkReviewBatchGroups(groups)

        assertEquals(listOf(50, 50, 21), chunks.map(List<List<String>>::size))
        assertEquals(groups, chunks.flatten())
    }

    @Test
    fun `chunk status is reported against the complete review plan`() {
        val request = SpeciesReviewBatchRequest(
            requestId = "request-1",
            groups = (1..121).map { index -> listOf("photo-$index") },
        )
        val checkpoint = SpeciesReviewBatchCheckpoint(
            chunkIndex = 1,
            processedCount = 49,
            individualCount = 49,
            warning = "One earlier photo was skipped.",
        )
        val chunkStatus = ReviewBatchStatus(
            jobId = "job-2",
            state = "running",
            totalPhotos = 50,
            processedCount = 10,
            processedPhotoIds = emptyList(),
            currentPhotoNumber = 11,
            currentPhotoId = "photo-61",
            totalGroups = 50,
            currentGroup = 11,
            groupedCount = 0,
            individualCount = 10,
            warnings = emptyList(),
            error = null,
            items = emptyList(),
        )

        val overall = SpeciesReviewBatchWork.aggregateStatus(request, checkpoint, chunkStatus)

        assertEquals(121, overall.totalPhotos)
        assertEquals(59, overall.processedCount)
        assertEquals(61, overall.currentPhotoNumber)
        assertEquals(121, overall.totalGroups)
        assertEquals(61, overall.currentGroup)
        assertEquals(59, overall.individualCount)
        assertEquals(listOf("One earlier photo was skipped."), overall.warnings)
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
