package com.hikejournal.app.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.test.platform.app.InstrumentationRegistry
import com.hikejournal.app.data.Encounter
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.SpeciesRecord
import java.io.File
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SpeciesSharePreparationTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Test fun exportsSelectionOrderLimitsCaptionAndReadableKeepsakesForEveryMode() = runBlocking {
        val photos = List(24) { index ->
            val file = File(context.cacheDir, "species-source-$index.jpg").apply { writeText("photo-$index") }
            photo("photo-$index", file.toURI().toString())
        }
        val selected = photos.reversed().map(Photo::id)
        for (mode in HikeShareKeepsake.entries) {
            val prepared = prepareSpeciesShare(context, species(photos), selected, mode)
            assertEquals(20, prepared.uris.size)
            val photoUris = when (mode) {
                HikeShareKeepsake.FIRST -> prepared.uris.drop(1)
                HikeShareKeepsake.LAST -> prepared.uris.dropLast(1)
                HikeShareKeepsake.NONE -> prepared.uris
            }
            assertEquals(selected.take(mode.maximumPhotos), photoUris.map { uri ->
                context.contentResolver.openInputStream(uri)!!.bufferedReader().use { it.readText() }
            })
            if (mode.includesKeepsake) {
                val cardUri = if (mode == HikeShareKeepsake.FIRST) prepared.uris.first() else prepared.uris.last()
                val card = context.contentResolver.openInputStream(cardUri).use { BitmapFactory.decodeStream(it) }
                assertEquals(1080, card.width)
                assertEquals(1350, card.height)
                card.recycle()
            }
            assertTrue(prepared.caption.contains("Pine Lily (Lilium catesbaei)"))
            assertTrue(prepared.caption.contains("24 encounters across 2 outings"))
            assertEquals(0, prepared.omittedPhotoCount)
        }
    }

    @Test fun partialFailuresKeepOrderAndIndependentSharesKeepTheirAttachments() = runBlocking {
        val first = File(context.cacheDir, "species-good-first.jpg").apply { writeText("first original") }
        val last = File(context.cacheDir, "species-good-last.jpg").apply { writeText("last original") }
        val photos = listOf(photo("first", first.toURI().toString()), photo("missing", "file:///missing-species.jpg"),
            photo("last", last.toURI().toString()))
        val record = species(photos)
        val prepared = prepareSpeciesShare(context, record, photos.map(Photo::id), HikeShareKeepsake.NONE)
        assertEquals(1, prepared.omittedPhotoCount)
        assertEquals(listOf("first original", "last original"), prepared.uris.map { uri ->
            context.contentResolver.openInputStream(uri)!!.bufferedReader().use { it.readText() }
        })
        val second = prepareSpeciesShare(context, record, listOf("last"), HikeShareKeepsake.NONE)
        assertNotEquals(prepared.uris.first(), second.uris.first())
        assertEquals("first original", context.contentResolver.openInputStream(prepared.uris.first())!!.bufferedReader().use { it.readText() })
    }

    @Test fun emptyPhotoOnlySharesFailAndKeepsakeOnlySharesWork() = runBlocking {
        val record = species(listOf(photo("missing", "file:///missing-species.jpg")))
        for (selected in listOf(emptyList(), listOf("missing"), listOf("another-species"))) {
            try {
                prepareSpeciesShare(context, record, selected, HikeShareKeepsake.NONE)
                throw AssertionError("An empty share must not open the Sharesheet")
            } catch (error: IllegalStateException) {
                assertTrue(error.message.orEmpty().contains("No selected photos were available"))
            }
        }
        assertEquals(1, prepareSpeciesShare(context, record, emptyList(), HikeShareKeepsake.FIRST).uris.size)
    }

    @Test fun rendersPhotoInStandardSmallAndLongNameKeepsakes() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val image = instrumentation.context.assets.open("design/hike.jpg").use { BitmapFactory.decodeStream(it) }
        val record = species(emptyList()).copy(commonName = "Swamp smartweed", scientificName = "Persicaria hydropiperoides",
            encounterCount = 4, hikeCount = 2)
        val directory = File(context.filesDir, "species-share-evidence").apply { mkdirs() }
        listOf("species-keepsake.png" to renderSpeciesShareCard(context, record, image),
            "species-keepsake-small.png" to renderSpeciesShareCard(context, record, image, 540, 675),
            "species-keepsake-long-name.png" to renderSpeciesShareCard(context, record.copy(
                commonName = "A very long species common name that must wrap and fit inside the keepsake",
                scientificName = "A particularly long scientific species name with additional subspecies information"), image)
        ).forEach { (name, bitmap) ->
            File(directory, name).outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
            bitmap.recycle()
        }
        image.recycle()
    }

    private fun species(photos: List<Photo>) = SpeciesRecord("pine-lily", 1, "Pine Lily", "Lilium catesbaei",
        "species", "Plantae", "", "", photos.size, 2, emptyList(), emptyMap(), emptyMap(), emptyMap(),
        null, "", photos.map { Encounter(it, it.hikeId, "Pine walk", "2026-11-12", "Pine woods", "2026-11-12") })

    private fun photo(id: String, url: String) = Photo(id, "outing", url, "", null, null, null, null,
        null, null, "image/jpeg", "ready", species = emptyList())
}
