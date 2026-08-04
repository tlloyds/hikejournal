package com.hikejournal.app.ui

import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.PublishItem
import org.junit.Assert.assertEquals
import org.junit.Test

class PublishingScopeTest {
    @Test
    fun `everyday scope includes legacy standalone queue items`() {
        val legacyEveryday = publishItem("everyday-legacy", null)
        val currentEveryday = publishItem("everyday-current", EVERYDAY_SIGHTINGS_HIKE_ID)
        val hikeItem = publishItem("hike-item", "hike-1")

        assertEquals(
            listOf(legacyEveryday, currentEveryday),
            publishItemsForHikeScope(
                listOf(legacyEveryday, currentEveryday, hikeItem),
                EVERYDAY_SIGHTINGS_HIKE_ID,
            ),
        )
    }

    @Test
    fun `outing scope excludes standalone queue items`() {
        val legacyEveryday = publishItem("everyday-legacy", null)
        val hikeItem = publishItem("hike-item", "hike-1")

        assertEquals(
            listOf(hikeItem),
            publishItemsForHikeScope(listOf(legacyEveryday, hikeItem), "hike-1"),
        )
    }

    private fun publishItem(id: String, hikeId: String?) = PublishItem(
        id = id,
        photo = Photo(id, hikeId, "", "", null, null, null, null, null, null, "image/jpeg", "ready", species = emptyList()),
        hikeId = hikeId,
        hikeTitle = "",
        hikeDate = "",
        locationName = "",
        taxonId = null,
        commonName = "Species",
        scientificName = "",
        state = "ready",
        inatObservationId = null,
        inatUrl = "",
        postedAt = null,
        photoAttached = null,
        relatedObservationIds = listOf(id),
        relatedPhotoCount = 1,
    )
}
