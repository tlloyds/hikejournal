package com.hikejournal.app.ui

import android.graphics.Bitmap
import android.os.SystemClock
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.hasScrollToIndexAction
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.hasAnyAncestor
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.isDialog
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performScrollToNode
import androidx.test.platform.app.InstrumentationRegistry
import com.hikejournal.app.data.Encounter
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.ui.theme.HikeJournalTheme
import java.io.File
import org.junit.Rule
import org.junit.Test

class SpeciesShareDialogTest {
    @get:Rule val rule = createComposeRule()
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val imageUrl: String by lazy {
        val file = File(context.cacheDir, "species-share-fixture.jpg")
        instrumentation.context.assets.open("design/hike.jpg").use { source -> file.outputStream().use { source.copyTo(it) } }
        file.toURI().toString()
    }

    @Test fun speciesDetailOpensSharePickerAndCloseReturnsToSameSpecies() {
        val record = species(3)
        rule.setContent { HikeJournalTheme { SpeciesDetailScreen(record, listOf(record), null, false, {}, {}, {}) } }
        rule.onNodeWithContentDescription("Share species").assertIsDisplayed().performClick()
        rule.onNodeWithText("Share Swamp smartweed").assertIsDisplayed()
        capture("species-share-screen.png")
        rule.onNodeWithText("Share 1 image").assertIsEnabled().assertIsDisplayed()
        rule.waitUntil(5_000) { rule.onAllNodes(hasContentDescription("Field guide keepsake for Swamp smartweed")).fetchSemanticsNodes().isNotEmpty() }
        capture("species-share-screen.png")
        rule.onNode(hasScrollToIndexAction() and hasAnyAncestor(isDialog()))
            .performScrollToNode(hasContentDescription("Swamp smartweed photo 2"))
        rule.onNodeWithContentDescription("Swamp smartweed photo 2").performClick()
        rule.onNodeWithContentDescription("Swamp smartweed photo 2").assertIsSelected()
        rule.onNodeWithText("Share Swamp smartweed").assertIsDisplayed()
        rule.onNodeWithText("Share 2 images").assertIsEnabled()
        capture("species-share-photo-selection.png")
        rule.onNodeWithContentDescription("Close species share").performClick()
        rule.onNodeWithContentDescription("Share species").assertIsDisplayed()
    }

    @Test fun noKeepsakeRequiresPhotosAndSwitchingBackTrimsToNineteen() {
        rule.setContent { HikeJournalTheme { SpeciesShareDialog(species(24), {}) } }
        rule.onNodeWithText("No keepsake").performClick()
        rule.onNodeWithText("Share 0 images").assertIsNotEnabled()
        rule.onNodeWithText("Select all").performScrollTo().performClick()
        rule.onNodeWithText("20/20 selected").assertExists()
        rule.onNodeWithText("Keepsake last").performScrollTo().performClick()
        rule.onNode(hasScrollToIndexAction()).performScrollToNode(hasText("19/19 selected"))
        rule.onNodeWithText("Share 20 images").assertIsEnabled()
        rule.onNodeWithText("Clear").performClick()
        rule.onNodeWithText("Share 1 image").assertIsEnabled()
        rule.onNodeWithText("No keepsake").performScrollTo().performClick()
        rule.onNodeWithText("Share 0 images").assertIsNotEnabled()
    }

    @Test fun speciesWithoutEncounterPhotosCanShareOnlyAKeepsake() {
        rule.setContent { HikeJournalTheme { SpeciesShareDialog(species(0), {}) } }
        rule.onNodeWithText("Share 1 image").assertIsEnabled()
        rule.onNodeWithText("No keepsake").performClick()
        rule.onNodeWithText("Share 0 images").assertIsNotEnabled()
        rule.onNodeWithText("Select all").assertDoesNotExist()
    }

    private fun capture(name: String) {
        rule.waitForIdle()
        instrumentation.waitForIdleSync()
        SystemClock.sleep(800)
        val directory = File(context.filesDir, "species-share-evidence").apply { mkdirs() }
        val bitmap = instrumentation.uiAutomation.takeScreenshot()
        File(directory, name).outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
    }

    private fun species(count: Int): SpeciesRecord {
        val photos = List(count) { index -> Photo("photo-$index", "outing-${index % 2}", imageUrl, "", null,
            null, null, null, 800, 800, "image/jpeg", "ready", species = emptyList()) }
        return SpeciesRecord("swamp-smartweed", 1, "Swamp smartweed", "Persicaria hydropiperoides", "species", "Plantae", "", "",
            count, 2, emptyList(), emptyMap(), emptyMap(), emptyMap(), null, imageUrl,
            photos.map { Encounter(it, it.hikeId, "Pine walk", "2026-11-12", "Pine woods", "2026-11-12") })
    }
}
