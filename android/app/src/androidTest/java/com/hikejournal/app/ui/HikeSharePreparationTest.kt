package com.hikejournal.app.ui

import androidx.test.platform.app.InstrumentationRegistry
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.Photo
import java.io.File
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HikeSharePreparationTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun exportsCorrectOrderAndPhotoLimitForEveryKeepsakeOption() = runBlocking {
        val photos = List(24) { index ->
            val file = File(context.cacheDir, "share-source-$index.jpg").apply { writeText("photo-$index") }
            photo("photo-$index", file.toURI().toString())
        }
        for (mode in HikeShareKeepsake.entries) {
            val prepared = prepareHikeShare(context, hike(), photos, satelliteMap = null, keepsake = mode)
            assertEquals(20, prepared.uris.size)
            val photoUris = when (mode) {
                HikeShareKeepsake.FIRST -> prepared.uris.drop(1)
                HikeShareKeepsake.LAST -> prepared.uris.dropLast(1)
                HikeShareKeepsake.NONE -> prepared.uris
            }
            val contents = photoUris.map { uri ->
                context.contentResolver.openInputStream(uri)!!.bufferedReader().use { it.readText() }
            }
            assertEquals(photos.take(if (mode.includesKeepsake) 19 else 20).map(Photo::id), contents)
            assertEquals(0, prepared.omittedPhotoCount)
        }
    }

    @Test
    fun missingPhotosCannotOpenAnEmptyShareWithoutAKeepsake() = runBlocking {
        try {
            prepareHikeShare(context, hike(), listOf(photo("missing", "file:///missing-share-photo.jpg")),
                satelliteMap = null, keepsake = HikeShareKeepsake.NONE)
            throw AssertionError("An empty share must fail before opening the Sharesheet")
        } catch (error: IllegalStateException) {
            assertTrue(error.message.orEmpty().contains("No selected photos were available"))
        }
    }

    private fun hike() = Hike(id = "share-test", title = "Pine Loop", hikeDate = "2026-10-22",
        distanceMiles = 3.2, locationName = "Pine Woods", notes = "", isArchived = false,
        coverUrl = "", photoCount = 24, speciesCount = 0)

    private fun photo(id: String, url: String) = Photo(id = id, hikeId = "share-test", url = url,
        caption = "", takenAt = null, createdAt = null, latitude = null, longitude = null,
        width = null, height = null, contentType = "image/jpeg", processingStatus = "ready", species = emptyList())
}
