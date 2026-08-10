package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class CelebrationsTest {
    @Test
    fun `batch reveal distinguishes possible new species from confirmed records`() {
        val known = listOf(species(1, "Known bird", "Aves"))
        val status = batchStatus(
            reviewItem("one", 1, "Known bird", "Aves"),
            reviewItem("two", 2, "New fern", "Plantae"),
            reviewItem("three", 3, "New jay", "Aves"),
        )

        val celebration = buildReviewBatchCelebration(status, known)

        assertEquals("2 possible new species", celebration?.title)
        assertEquals("2", celebration?.highlights?.last()?.value)
        assertEquals(3, celebration?.imageUrls?.size)
    }

    @Test
    fun `twenty fifth species unlocks field guide badge`() {
        val existing = List(24) { index -> species(index.toLong(), "Plant $index", "Plantae") }
        val celebration = buildConfirmedSpeciesCelebration(
            candidate = ReviewCandidate(100, "New fern", "Example fern", 0.9, "Plantae"),
            photo = photo("new", "2026-08-10"),
            observedOn = "2026-08-10",
            existingSpecies = existing,
        )

        assertEquals("New fern", celebration?.title)
        assertEquals("Curious Naturalist", celebration?.badgeTitle)
        assertEquals("25", celebration?.highlights?.first()?.value)
    }

    @Test
    fun `return after sixty days gets rediscovery moment`() {
        val known = species(1, "Scrub-jay", "Aves").copy(latestSeen = "2026-06-01")

        val celebration = buildConfirmedSpeciesCelebration(
            candidate = ReviewCandidate(1, "Scrub-jay", "Aphelocoma example", 0.9, "Aves"),
            photo = photo("return", "2026-08-10"),
            observedOn = "2026-08-10",
            existingSpecies = listOf(known),
        )

        assertNotNull(celebration)
        assertEquals("WELCOME BACK", celebration?.eyebrow)
        assertEquals("70", celebration?.highlights?.first()?.value)

        assertNull(
            buildConfirmedSpeciesCelebration(
                candidate = ReviewCandidate(1, "Scrub-jay", "Aphelocoma example", 0.9, "Aves"),
                photo = photo("soon", "2026-06-20"),
                observedOn = "2026-06-20",
                existingSpecies = listOf(known),
            )
        )
    }

    @Test
    fun `fiftieth hike earns milestone celebration`() {
        val previous = List(49) { index -> hike("hike-$index") }
        val fiftieth = hike("hike-50").copy(title = "Pine Ridge")

        val celebration = buildHikeMilestoneCelebration(previous, listOf(fiftieth) + previous, fiftieth)

        assertEquals("50th hike logged!", celebration?.title)
        assertEquals("Half-Century Hiker", celebration?.badgeTitle)
    }

    private fun photo(id: String, date: String) = Photo(
        id = id,
        hikeId = "hike-1",
        url = "https://example.test/$id.jpg",
        caption = "",
        takenAt = date,
        createdAt = date,
        latitude = null,
        longitude = null,
        width = null,
        height = null,
        contentType = "image/jpeg",
        processingStatus = "in_review",
        species = emptyList(),
    )

    private fun species(taxonId: Long, name: String, iconicTaxonName: String) = SpeciesRecord(
        key = "taxon:$taxonId",
        taxonId = taxonId,
        commonName = name,
        scientificName = "Example $taxonId",
        rank = "species",
        iconicTaxonName = iconicTaxonName,
        wikipediaUrl = "",
        wikipediaSummary = "",
        encounterCount = 1,
        hikeCount = 1,
        hikeIds = listOf("hike-1"),
        hikeEncounterCounts = emptyMap(),
        hikeCoverUrls = emptyMap(),
        hikeLatestSeen = emptyMap(),
        latestSeen = "2026-06-01",
        coverUrl = "",
    )

    private fun reviewItem(id: String, taxonId: Long, name: String, group: String) = ReviewItem(
        id = id,
        photo = photo(id, "2026-08-10"),
        hikeId = "hike-1",
        hikeTitle = "Trail",
        hikeDate = "2026-08-10",
        locationName = "Preserve",
        state = "pending",
        observationId = "observation-$id",
        candidates = listOf(ReviewCandidate(taxonId, name, "Example $taxonId", 0.9, group)),
    )

    private fun batchStatus(vararg items: ReviewItem) = ReviewBatchStatus(
        jobId = "job-1",
        state = "completed",
        totalPhotos = items.size,
        processedCount = items.size,
        processedPhotoIds = items.map { it.id },
        currentPhotoNumber = items.size,
        currentPhotoId = null,
        totalGroups = items.size,
        currentGroup = items.size,
        groupedCount = 0,
        individualCount = items.size,
        warnings = emptyList(),
        error = null,
        items = items.toList(),
    )

    private fun hike(id: String) = Hike(
        id = id,
        title = "Trail $id",
        hikeDate = "2026-08-10",
        distanceMiles = 2.0,
        locationName = "Preserve",
        notes = "",
        isArchived = false,
        coverUrl = "",
        photoCount = 0,
        speciesCount = 0,
    )
}
