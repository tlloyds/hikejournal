package com.hikejournal.app.ui

import com.hikejournal.app.data.Encounter
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.SpeciesRecord
import org.junit.Assert.assertEquals
import org.junit.Test

class SpeciesShareTest {
    @Test fun `species photos include encounters across outings without duplicates or videos`() {
        val first = photo("first", "outing-a")
        val second = photo("second", "outing-b")
        val record = species(listOf(first, second, first,
            photo("video").copy(contentType = "VIDEO/MP4"), photo("blank").copy(url = "  ")))
        assertEquals(listOf(first, second), speciesSharePhotos(record))
    }

    @Test fun `selected photos retain tap order and cannot include another species photo`() {
        val photos = List(24) { photo("photo-$it") }
        val selected = listOf("other-species", "photo-9", "photo-2", "photo-9", "missing")
        assertEquals(listOf(photos[9], photos[2]),
            selectedSpeciesSharePhotos(species(photos), selected, HikeShareKeepsake.FIRST))
    }

    @Test fun `keepsakes reserve one carousel slot and photos only allows twenty`() {
        val photos = List(24) { photo("photo-$it") }
        HikeShareKeepsake.entries.forEach { mode ->
            val selected = selectedSpeciesSharePhotos(species(photos), photos.reversed().map(Photo::id), mode)
            assertEquals(photos.reversed().take(if (mode.includesKeepsake) 19 else 20), selected)
        }
    }

    @Test fun `keepsake uses first selected photo and falls back to encounter then cover`() {
        val photos = listOf(photo("first"), photo("second"))
        assertEquals(photos[1].url, speciesShareImageUrl(species(photos), listOf(photos[1])))
        assertEquals(photos[0].url, speciesShareImageUrl(species(photos), emptyList()))
        assertEquals("cover.jpg", speciesShareImageUrl(species(emptyList()), emptyList()))
    }

    private fun species(photos: List<Photo>) = SpeciesRecord("pine-lily", 1, "Pine Lily", "Lilium catesbaei",
        "species", "Plantae", "", "", photos.size, 2, emptyList(), emptyMap(), emptyMap(), emptyMap(),
        null, "cover.jpg", photos.map { Encounter(it, it.hikeId, "Pine walk", "2026-11-12", "Pine woods", "2026-11-12") })

    private fun photo(id: String, hikeId: String = "outing") = Photo(id, hikeId, "https://example.com/$id.jpg",
        "", null, null, null, null, null, null, "image/jpeg", "ready", species = emptyList())
}
