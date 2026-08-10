package com.hikejournal.app

import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.WeatherSnapshot
import com.hikejournal.app.data.expectedPhotoPageOffsets
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class JournalLoadProgressTest {
    @Test
    fun `known photo count schedules bounded pages concurrently`() {
        assertEquals(listOf(0, 100, 200), expectedPhotoPageOffsets(256))
        assertEquals(emptyList<Int>(), expectedPhotoPageOffsets(null))
        assertEquals(emptyList<Int>(), expectedPhotoPageOffsets(0))
    }

    @Test
    fun `lightweight header adds weather without discarding archive summary`() {
        val summary = hike(photoCount = 120, coverUrl = "https://images.example/cover.jpg")
        val header = hike(
            photoCount = 0,
            weather = WeatherSnapshot(
                provider = "open-meteo",
                providerDataset = "archive",
                algorithmVersion = "route-centroid-interval-v1",
                intervalStartedAt = null,
                intervalEndedAt = null,
                temperatureMinC = 22.0,
                temperatureMeanC = 25.0,
                temperatureMaxC = 28.0,
                apparentTemperatureMeanC = null,
                precipitationTotalMm = 0.0,
                relativeHumidityMeanPercent = null,
                cloudCoverMeanPercent = null,
                windSpeedMeanKph = null,
                conditionLabel = "Clear",
            ),
        )

        val merged = mergeHikeLoadProgress(summary, header)

        assertEquals(120, merged.photoCount)
        assertEquals("https://images.example/cover.jpg", merged.coverUrl)
        assertNotNull(merged.weather)
        assertEquals("Clear", merged.weather?.conditionLabel)
    }

    @Test
    fun `first photo page becomes visible while total count is preserved`() {
        val summary = hike(photoCount = 120)
        val firstPage = hike(
            photoCount = 100,
            photos = List(100) { index -> photo("photo-$index") },
        )

        val merged = mergeHikeLoadProgress(summary, firstPage)

        assertEquals(120, merged.photoCount)
        assertEquals(100, merged.photos.size)
    }

    private fun hike(
        photoCount: Int,
        coverUrl: String = "",
        photos: List<Photo> = emptyList(),
        weather: WeatherSnapshot? = null,
    ) = Hike(
        id = "hike-1",
        title = "Pine Loop",
        hikeDate = "2026-08-09",
        distanceMiles = 3.2,
        locationName = "Pine Woods",
        notes = "",
        isArchived = false,
        coverUrl = coverUrl,
        photoCount = photoCount,
        speciesCount = 12,
        photos = photos,
        weather = weather,
    )

    private fun photo(id: String) = Photo(
        id = id,
        hikeId = "hike-1",
        url = "https://images.example/$id.jpg",
        caption = "",
        takenAt = null,
        createdAt = null,
        latitude = null,
        longitude = null,
        width = null,
        height = null,
        contentType = "image/jpeg",
        processingStatus = "ready",
        species = emptyList(),
    )
}
