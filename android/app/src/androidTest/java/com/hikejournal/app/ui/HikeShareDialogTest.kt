package com.hikejournal.app.ui

import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.hasScrollToIndexAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performScrollToNode
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.Photo
import com.hikejournal.app.ui.theme.HikeJournalTheme
import org.junit.Rule
import org.junit.Test

class HikeShareDialogTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun changingKeepsakeUpdatesLimitTrimsSelectionAndPreventsEmptyShare() {
        composeRule.setContent {
            HikeJournalTheme {
                HikeShareDialog(hike = hike(), onDismiss = {})
            }
        }
        composeRule.onNodeWithText("Share 1 image").assertIsEnabled()
        composeRule.onNodeWithText("No keepsake").performClick()
        composeRule.onNodeWithText("Share 0 images").assertIsNotEnabled()
        composeRule.onNodeWithText("Select all").performScrollTo().performClick()
        composeRule.onNodeWithText("20/20").assertExists()
        composeRule.onNodeWithText("Share 20 images").assertIsEnabled()

        composeRule.onNodeWithText("Keepsake last").performScrollTo().performClick()
        composeRule.onNode(hasScrollToIndexAction()).performScrollToNode(hasText("19/19"))
        composeRule.onNodeWithText("19/19").assertExists()
        composeRule.onNodeWithText("Share 20 images").assertIsEnabled()
        composeRule.onNodeWithText("Clear").performClick()
        composeRule.onNodeWithText("Share 1 image").assertIsEnabled()

        composeRule.onNode(hasScrollToIndexAction()).performScrollToNode(hasText("Keepsake first"))
        composeRule.onNodeWithText("Keepsake first").performClick()
        composeRule.onNodeWithText("Share 1 image").assertIsEnabled()
    }

    private fun hike() = Hike(
        id = "share-test", title = "Pine Loop", hikeDate = "2026-10-22", distanceMiles = 3.2,
        locationName = "Pine Woods", notes = "", isArchived = false, coverUrl = "",
        photoCount = 24, speciesCount = 0,
        photos = List(24) { index ->
            Photo(id = "photo-$index", hikeId = "share-test", url = "file:///share-test-$index.jpg",
                caption = "Photo $index", takenAt = null, createdAt = null, latitude = null,
                longitude = null, width = null, height = null, contentType = "image/jpeg",
                processingStatus = "ready", species = emptyList())
        },
    )
}
