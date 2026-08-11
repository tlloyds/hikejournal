package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class HikeArchiveCoverMergeTest {
    @Test
    fun `empty detail cover cannot erase the cached archive cover`() {
        val archive = hike(coverUrl = "https://img/selected.jpg", coverPhotoId = "photo-1")
        val detail = hike(coverUrl = "", coverPhotoId = null)

        val merged = mergeCachedHikeDetail(archive, detail)

        assertEquals("https://img/selected.jpg", merged.coverUrl)
        assertEquals("photo-1", merged.coverPhotoId)
    }

    @Test
    fun `fresh archive restores only the matching detailed cover`() {
        val detail = hike(coverUrl = "https://img/selected.jpg", coverPhotoId = "photo-1")

        assertEquals(
            "https://img/selected.jpg",
            restoreMatchingCachedCover(
                archive = hike(coverUrl = "", coverPhotoId = "photo-1"),
                detail = detail,
            ).coverUrl,
        )
        assertEquals(
            "",
            restoreMatchingCachedCover(
                archive = hike(coverUrl = "", coverPhotoId = "photo-2"),
                detail = detail,
            ).coverUrl,
        )
    }

    private fun hike(coverUrl: String, coverPhotoId: String?) = Hike(
        id = "hike-1",
        title = "Pine Loop",
        hikeDate = "2026-08-10",
        distanceMiles = 2.0,
        locationName = "Pine Preserve",
        notes = "",
        isArchived = false,
        coverUrl = coverUrl,
        coverPhotoId = coverPhotoId,
        photoCount = 1,
        speciesCount = 1,
    )
}
