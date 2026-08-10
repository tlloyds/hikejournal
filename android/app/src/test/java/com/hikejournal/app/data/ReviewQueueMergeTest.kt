package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class ReviewQueueMergeTest {
    @Test
    fun `server snapshot is completed by every pending local review upload`() {
        val serverItems = (1..16).map(::reviewItem)
        val pendingItems = (17..35).map(::reviewItem)

        val merged = mergeReviewQueueItems(serverItems, pendingItems)

        assertEquals(35, merged.size)
        assertEquals((1..35).map { "photo-$it" }, merged.map(ReviewItem::id))
    }

    @Test
    fun `a photo visible on the server is not duplicated by its finishing upload`() {
        val merged = mergeReviewQueueItems(
            serverItems = listOf(reviewItem(1, syncState = "synced")),
            pendingLocalItems = listOf(reviewItem(1, syncState = "syncing")),
        )

        assertEquals(1, merged.size)
        assertEquals("synced", merged.single().photo.syncState)
    }

    private fun reviewItem(index: Int, syncState: String = "synced"): ReviewItem {
        val id = "photo-$index"
        return ReviewItem(
            id = id,
            photo = Photo(
                id = id,
                hikeId = "hike-1",
                url = if (syncState == "synced") "https://example.test/$id.jpg" else "file:///tmp/$id.jpg",
                caption = "",
                takenAt = null,
                createdAt = null,
                latitude = null,
                longitude = null,
                width = null,
                height = null,
                contentType = "image/jpeg",
                processingStatus = "in_review",
                syncState = syncState,
                species = emptyList(),
            ),
            hikeId = "hike-1",
            hikeTitle = "Test hike",
            hikeDate = "2026-08-10",
            locationName = "",
            state = "waiting",
            observationId = null,
            candidates = emptyList(),
        )
    }
}
