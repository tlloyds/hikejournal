package com.hikejournal.app.ui

import android.graphics.Bitmap
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.UriHandler
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.unit.Density
import androidx.test.platform.app.InstrumentationRegistry
import com.hikejournal.app.data.EdibilityReference
import com.hikejournal.app.data.FoodUsePreferences
import com.hikejournal.app.data.FoodUseSource
import com.hikejournal.app.data.FoodUseStatus
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.SpeciesLabel
import com.hikejournal.app.data.ToxicityStatus
import com.hikejournal.app.ui.theme.HikeJournalTheme
import java.io.File
import java.time.Instant
import java.util.UUID
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class EdibilitySectionTest {
    @get:Rule val compose = createComposeRule()
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val reference = EdibilityReference(
        taxonId = 42,
        scientificName = "Example taxon",
        rank = "species",
        datasetVersion = "fixture-v2",
        foodUse = FoodUseStatus.Documented,
        toxicity = ToxicityStatus.Unknown,
        evidenceConflict = false,
        hasDocumentedFoodUse = true,
        documentedParts = emptyList(),
        foodUseNotes = null,
        toxicityNotes = null,
        sources = listOf(
            FoodUseSource(
                "Fixture checklist", "2", "https://example.test/food", "Example Author",
                "Example Publisher", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/",
                "Matched by HikeJournal.",
            ),
        ),
        expiresAt = Instant.MAX,
        reviewed = false,
    )

    private fun tag(reference: EdibilityReference, commonName: String, primary: Boolean) =
        SpeciesLabel(
            commonName, reference.scientificName, "confirmed", primary, reference.taxonId,
            observationId = "observation-${reference.taxonId}",
            iconicTaxonName = "Plantae",
            edibility = reference,
        )

    @Test
    fun detailShowsChecklistLimitAndClickableAttribution() {
        var opened = ""
        compose.setContent {
            HikeJournalTheme {
                CompositionLocalProvider(LocalUriHandler provides object : UriHandler {
                    override fun openUri(uri: String) { opened = uri }
                }) {
                    EdibilitySection(reference)
                }
            }
        }
        compose.onNodeWithText(EdibilitySectionTitle).assertIsDisplayed()
        compose.onNodeWithText("Educational species reference only.", substring = true).assertIsDisplayed()
        compose.onNodeWithText("The record does not establish specific parts", substring = true).assertIsDisplayed()
        compose.onNodeWithText("Toxicity not assessed by available sources").assertIsDisplayed()
        compose.onNodeWithText("Fixture checklist · Version 2").performClick()
        assertEquals("https://example.test/food", opened)
        compose.onNodeWithText("Example Author · Example Publisher").assertIsDisplayed()
    }

    @Test
    fun noReferenceUsesNeutralCopy() {
        compose.setContent { HikeJournalTheme { EdibilitySection(null) } }
        compose.onNodeWithText("No reference data available").assertIsDisplayed()
        compose.onNodeWithText("Documented human food use").assertDoesNotExist()
    }

    @Test
    fun photoIndicatorsRespectToggleBindToIndividualTagsAndInvalidateOpenReference() {
        val enabled = mutableStateOf(false)
        val first = tag(reference, "Fixture plant", primary = true)
        val warning = tag(
            reference.copy(
                taxonId = 43,
                scientificName = "Example hazard",
                toxicity = ToxicityStatus.DocumentedConcern,
                toxicityNotes = "Synthetic warning",
            ),
            "Fixture hazard",
            primary = false,
        )
        val photo = Photo(
            id = UUID.randomUUID().toString(),
            hikeId = null,
            url = "",
            caption = "",
            takenAt = null,
            createdAt = null,
            latitude = null,
            longitude = null,
            width = null,
            height = null,
            contentType = "image/jpeg",
            processingStatus = "ready",
            species = listOf(first, warning),
            edibilityReadStartedAt = 1,
        )
        compose.setContent {
            HikeJournalTheme {
                val density = LocalDensity.current
                CompositionLocalProvider(LocalDensity provides Density(density.density, 1.8f)) {
                    Column(Modifier.fillMaxSize().background(Color(0xFF18221C)).statusBarsPadding()) {
                        PhotoFoodUseReferences(photo, show = enabled.value)
                    }
                }
            }
        }
        compose.onNodeWithText("Fixture plant · Food uses").assertDoesNotExist()
        compose.runOnIdle { enabled.value = true }
        compose.onNodeWithText("Fixture plant · Food uses").assertIsDisplayed()
        compose.onNodeWithText("Fixture hazard · Toxicity concerns").assertIsDisplayed().performClick()
        compose.onNodeWithText("Example hazard").assertIsDisplayed()
        captureEvidence()
        compose.onNodeWithText("Synthetic warning").performScrollTo().assertIsDisplayed()
        compose.runOnIdle { FoodUsePreferences(context).invalidatePhotoIdentity(photo.id) }
        compose.onNodeWithText(EdibilitySectionTitle).assertDoesNotExist()
        compose.onNodeWithText("Fixture plant · Food uses").assertDoesNotExist()
    }

    @Test
    fun newestDatasetRefreshWinsAndWithdrawalClearsReference() {
        val preferences = FoodUsePreferences(context)
        val settings = context.getSharedPreferences("hikejournal_sync", 0)
        val previousTime = settings.getLong("food_use_dataset_read_started_at", 0)
        val previousVersion = preferences.datasetVersion()
        val now = maxOf(System.currentTimeMillis(), previousTime + 3)
        try {
            preferences.recordDatasetVersion("fixture-v2", now)
            preferences.recordDatasetVersion("fixture-v1", now - 1)
            assertEquals("fixture-v2", preferences.datasetVersion())
            preferences.recordDatasetVersion(null, now + 1)
            preferences.recordDatasetVersion("fixture-v2", now)
            assertEquals("", preferences.datasetVersion())
        } finally {
            val editor = settings.edit().putLong("food_use_dataset_read_started_at", previousTime)
            if (previousVersion == null) editor.remove("food_use_dataset_version")
            else editor.putString("food_use_dataset_version", previousVersion)
            editor.commit()
        }
    }

    private fun captureEvidence() {
        if (InstrumentationRegistry.getArguments().getString("edibilityScreenshot") != "true") return
        compose.waitForIdle()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        instrumentation.waitForIdleSync()
        val screenshot = instrumentation.uiAutomation.takeScreenshot()
        File(context.filesDir, "edibility-reference.png").outputStream().use {
            screenshot.compress(Bitmap.CompressFormat.PNG, 100, it)
        }
        screenshot.recycle()
    }

    @Test
    fun photoPreferenceDefaultsOffAndPersists() {
        val settings = context.getSharedPreferences("hikejournal_food_use", 0)
        val stored = settings.contains("show_photo_indicators")
        val original = settings.getBoolean("show_photo_indicators", false)
        try {
            settings.edit().remove("show_photo_indicators").commit()
            val preferences = FoodUsePreferences(context)
            assertFalse(preferences.showPhotoIndicators)
            preferences.showPhotoIndicators = true
            assertTrue(FoodUsePreferences(context).showPhotoIndicators)
            preferences.showPhotoIndicators = false
            assertFalse(FoodUsePreferences(context).showPhotoIndicators)
        } finally {
            val editor = settings.edit()
            if (stored) editor.putBoolean("show_photo_indicators", original) else editor.remove("show_photo_indicators")
            editor.commit()
        }
    }
}
