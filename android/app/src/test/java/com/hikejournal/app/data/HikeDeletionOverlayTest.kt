package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class HikeDeletionOverlayTest {
    @Test
    fun `deleted hike encounters are removed while other hikes remain`() {
        val filtered = species().withoutHikes(setOf("hike-a"))

        requireNotNull(filtered)
        assertEquals(1, filtered.encounterCount)
        assertEquals(1, filtered.hikeCount)
        assertEquals(listOf("hike-b"), filtered.hikeIds)
        assertEquals(mapOf("hike-b" to 1), filtered.hikeEncounterCounts)
        assertEquals("https://img/b.jpg", filtered.coverUrl)
        assertEquals("2026-07-20", filtered.latestSeen)
    }

    @Test
    fun `species disappears when its only hike is deleted`() {
        assertNull(
            species(
                encounterCount = 2,
                hikeIds = listOf("hike-a"),
                counts = mapOf("hike-a" to 2),
                covers = mapOf("hike-a" to "https://img/a.jpg"),
                latest = mapOf("hike-a" to "2026-07-21"),
            ).withoutHikes(setOf("hike-a")),
        )
    }

    @Test
    fun `remaining latest encounter compares timezone aware instants`() {
        val filtered = species(
            encounterCount = 3,
            hikeIds = listOf("deleted-hike", "local-next-day", "later-utc"),
            counts = mapOf("deleted-hike" to 1, "local-next-day" to 1, "later-utc" to 1),
            covers = mapOf(
                "deleted-hike" to "https://img/deleted.jpg",
                "local-next-day" to "https://img/local.jpg",
                "later-utc" to "https://img/utc.jpg",
            ),
            latest = mapOf(
                "deleted-hike" to "2026-08-01T00:00:00Z",
                "local-next-day" to "2026-07-30T00:30:00+02:00",
                "later-utc" to "2026-07-29T23:00:00Z",
            ),
        ).withoutHikes(setOf("deleted-hike"))

        requireNotNull(filtered)
        assertEquals("2026-07-29T23:00:00Z", filtered.latestSeen)
    }

    private fun species(
        encounterCount: Int = 3,
        hikeIds: List<String> = listOf("hike-a", "hike-b"),
        counts: Map<String, Int> = mapOf("hike-a" to 2, "hike-b" to 1),
        covers: Map<String, String> = mapOf(
            "hike-a" to "https://img/a.jpg",
            "hike-b" to "https://img/b.jpg",
        ),
        latest: Map<String, String> = mapOf(
            "hike-a" to "2026-07-21",
            "hike-b" to "2026-07-20",
        ),
    ) = SpeciesRecord(
        key = "gopher-tortoise",
        taxonId = 42,
        commonName = "Gopher Tortoise",
        scientificName = "Gopherus polyphemus",
        rank = "species",
        iconicTaxonName = "Reptilia",
        wikipediaUrl = "",
        wikipediaSummary = "",
        encounterCount = encounterCount,
        hikeCount = hikeIds.size,
        hikeIds = hikeIds,
        hikeEncounterCounts = counts,
        hikeCoverUrls = covers,
        hikeLatestSeen = latest,
        latestSeen = latest.values.maxOrNull(),
        coverUrl = covers["hike-a"].orEmpty(),
    )
}
