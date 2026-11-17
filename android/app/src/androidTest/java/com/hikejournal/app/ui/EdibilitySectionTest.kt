package com.hikejournal.app.ui

import android.graphics.Bitmap
import android.os.SystemClock
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.UriHandler
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.hasScrollToIndexAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performScrollToIndex
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.unit.Density
import androidx.test.platform.app.InstrumentationRegistry
import com.hikejournal.app.data.EcologyStatus
import com.hikejournal.app.data.EdibilityReference
import com.hikejournal.app.data.FoodUsePreferences
import com.hikejournal.app.data.FoodUseSource
import com.hikejournal.app.data.FoodUseStatus
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.PlantPartEvidence
import com.hikejournal.app.data.PlantPartEvidenceKind
import com.hikejournal.app.data.SpeciesLabel
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.data.ToxicityStatus
import com.hikejournal.app.data.TraditionalUse
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
                    Column(Modifier.verticalScroll(rememberScrollState())) {
                        EdibilitySection(reference.copy(
                            toxicity = ToxicityStatus.DocumentedConcern,
                            checklistPoisonUse = true,
                        ))
                    }
                }
            }
        }
        compose.onNodeWithText(EdibilitySectionTitle).assertIsDisplayed()
        compose.onNodeWithText("Food use reported").assertIsDisplayed()
        compose.onNodeWithText("Educational species reference only.", substring = true).assertDoesNotExist()
        compose.onNodeWithText("The source doesn’t specify which parts are used or under what conditions.").assertIsDisplayed()
        compose.onNodeWithText("Toxicity reported").assertDoesNotExist()
        compose.onNodeWithText("The checklist records a use as a poison.", substring = true).assertDoesNotExist()
        compose.onNodeWithText("Fixture checklist · Version 2").assertDoesNotExist()
        compose.onNodeWithText("Sources & notes").performClick()
        compose.onNodeWithText("The checklist records a use as a poison.", substring = true).performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Fixture checklist · Version 2").performScrollTo().performClick()
        assertEquals("https://example.test/food", opened)
        compose.onNodeWithText("Example Author · Example Publisher").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Sources & notes").performScrollTo().performClick()
        compose.onNodeWithText("Fixture checklist · Version 2").assertDoesNotExist()
    }

    @Test
    fun noReferenceUsesNeutralCopy() {
        compose.setContent { HikeJournalTheme { EdibilitySection(null) } }
        compose.onNodeWithText("Edibility unknown").assertIsDisplayed()
        compose.onNodeWithText("Food use reported").assertDoesNotExist()
    }

    @Test
    fun expiredReferenceAsksForARefresh() {
        compose.setContent { HikeJournalTheme { EdibilitySection(null, expired = true) } }
        compose.onNodeWithText("Reference needs a refresh").assertIsDisplayed()
        compose.onNodeWithText("Edibility unknown").assertDoesNotExist()
    }

    @Test
    fun plantPartsLeadWithHazardsAndLinkToTheirOwnEvidence() {
        val first = reference.sources.single()
        val second = first.copy(title = "Flower source", publisher = "Flower publisher", url = "https://example.test/flowers")
        val scoped = reference.copy(
            toxicity = ToxicityStatus.DocumentedConcern,
            sources = listOf(first, second),
            partEvidence = listOf(
                PlantPartEvidence("Flowers", PlantPartEvidenceKind.Edible, "Documented in preserves.", second),
                PlantPartEvidence("Leaves", PlantPartEvidenceKind.Toxic, "Toxic when swallowed.", first),
            ),
        )
        var opened = ""
        compose.setContent {
            HikeJournalTheme {
                CompositionLocalProvider(LocalUriHandler provides object : UriHandler {
                    override fun openUri(uri: String) { opened = uri }
                }) {
                    Column(Modifier.verticalScroll(rememberScrollState())) { EdibilitySection(scoped) }
                }
            }
        }
        val hazard = compose.onNodeWithText("Leaves · Toxic").assertIsDisplayed()
        val edible = compose.onNodeWithText("Flowers · Edible").assertIsDisplayed()
        assertTrue(hazard.getUnclippedBoundsInRoot().top < edible.getUnclippedBoundsInRoot().top)
        compose.onNodeWithText("Human food use is also documented.").assertDoesNotExist()
        compose.onNodeWithText("Flower publisher").performClick()
        assertEquals(second.url, opened)
        captureEvidence("part-evidence.png")
    }

    @Test
    fun genusOnlyIdentificationExplainsMissingEvidence() {
        compose.setContent { HikeJournalTheme { EdibilitySection(null, taxonRank = "genus") } }
        compose.onNodeWithText("Species ID needed").assertIsDisplayed()
        compose.onNodeWithText("This sighting names a group. Food use can vary from one species to another.").assertIsDisplayed()
    }

    @Test
    fun airPotatoWarningPrecedesFoodUseAndSpeciesOverview() {
        val airPotato = reference.copy(
            scientificName = "Dioscorea bulbifera",
            toxicity = ToxicityStatus.DocumentedConcern,
            partEvidence = listOf(
                PlantPartEvidence("Aerial bulbils", PlantPartEvidenceKind.Toxic, "Florida plants can contain toxins.", reference.sources.single()),
            ),
        )
        showSpecies(
            "Air potato", airPotato, "non_native",
            "A climbing vine that forms aerial bulbils.",
        )

        val warning = compose.onNodeWithText("Aerial bulbils · Toxic").assertIsDisplayed()
        val foodUse = compose.onNodeWithText("Food use reported").assertIsDisplayed()
        assertTrue(warning.getUnclippedBoundsInRoot().top < foodUse.getUnclippedBoundsInRoot().top)
        compose.onNodeWithText("Used as food").assertDoesNotExist()
        compose.onAllNodesWithText("Air potato").assertCountEquals(1)
        captureEvidence("air-potato-field-guide.png")
        compose.onNode(hasScrollToIndexAction()).performScrollToNode(hasText("About this species"))
        compose.onNodeWithText("About this species").assertIsDisplayed()
        compose.onNodeWithText("Fixture checklist · Version 2").assertDoesNotExist()
    }

    @Test
    fun beautyberryShowsFoodUseAndEvidenceLimitsBeforeNaturalHistory() {
        val source = reference.sources.single()
        val beautyberry = reference.copy(
            scientificName = "Callicarpa americana",
            partEvidence = listOf(PlantPartEvidence("Berries", PlantPartEvidenceKind.Edible, null, source)),
            traditionalUses = listOf(TraditionalUse("The leaves have a history of use as an insect repellent.", source)),
        )
        showSpecies(
            "American beautyberry", beautyberry, "native",
            "A native shrub with dense clusters of purple fruit.",
        )

        compose.onNodeWithText("Berries · Edible").assertIsDisplayed()
        compose.onNodeWithText("Traditional uses").assertIsDisplayed()
        compose.onNodeWithText("The leaves have a history of use as an insect repellent.").assertIsDisplayed()
        compose.onNodeWithText("Toxicity reported").assertDoesNotExist()
        compose.onAllNodesWithText("American beautyberry").assertCountEquals(1)
        captureEvidence("beautyberry-field-guide.png")
        compose.onNode(hasScrollToIndexAction()).performScrollToNode(hasText("Field records"))
        compose.onNodeWithText("Field records").assertIsDisplayed()
        compose.onNodeWithText("1 encounter across 1 outing").assertIsDisplayed()
    }

    @Test
    fun comparisonKeepsColumnsAlignedAndNamesVisibleWhenReading() {
        val first = speciesRecord(
            "American beautyberry",
            reference.copy(scientificName = "Callicarpa americana", partEvidence = listOf(
                PlantPartEvidence("Berries", PlantPartEvidenceKind.Edible, null, reference.sources.single()),
            )),
            "native",
            "First plant description. ".repeat(70).trim(),
        )
        val exact = reference.copy(taxonId = 43, scientificName = "Dioscorea bulbifera", partEvidence = listOf(
            PlantPartEvidence("Aerial bulbils", PlantPartEvidenceKind.Toxic, null, reference.sources.single()),
        ))
        val second = speciesRecord("Air potato", exact, "invasive", "").copy(
            edibility = null,
            edibilityByTaxon = listOf(exact),
            scientificName = "Dioscorea",
            coverUrl = InstrumentationRegistry.getArguments().getString("comparisonSecondCoverFixture").orEmpty(),
            encounterCount = 2,
        )
        var returned = false
        compose.setContent {
            HikeJournalTheme {
                SpeciesComparisonDialog(first, second, reference.datasetVersion) { returned = true }
            }
        }

        val firstStatus = compose.onNodeWithText("Native here").assertIsDisplayed().getUnclippedBoundsInRoot()
        val secondStatus = compose.onNodeWithText("Invasive here").assertIsDisplayed().getUnclippedBoundsInRoot()
        assertEquals(firstStatus.top, secondStatus.top)
        assertTrue(firstStatus.right < secondStatus.left)
        val fruit = compose.onNodeWithText("Berries · Edible").assertIsDisplayed().getUnclippedBoundsInRoot()
        val hazard = compose.onNodeWithText("Aerial bulbils · Toxic").assertIsDisplayed().getUnclippedBoundsInRoot()
        val scopedName = compose.onNodeWithText(exact.scientificName).assertIsDisplayed().getUnclippedBoundsInRoot()
        assertTrue(fruit.right < hazard.left)
        assertTrue(scopedName.top < hazard.top)
        compose.onNodeWithText("First plant description.", substring = true).assertDoesNotExist()
        captureEvidence("species-comparison.png")

        val list = compose.onNode(hasScrollToIndexAction())
        list.performScrollToNode(hasText("Wikipedia descriptions"))
        compose.onNodeWithText("Wikipedia descriptions").performClick()
        list.performScrollToIndex(5)
        compose.onNodeWithText("First plant description.", substring = true).assertIsDisplayed()
        compose.onNodeWithText(first.commonName).assertIsDisplayed()
        compose.onNodeWithText(second.commonName).assertIsDisplayed()
        compose.onNodeWithContentDescription("Back to species selection").performClick()
        assertTrue(returned)
    }

    @Test
    fun conflictingFoodClaimsStayQualified() {
        val disputed = reference.copy(
            foodUse = FoodUseStatus.Disputed,
            partEvidence = listOf(PlantPartEvidence("Berries", PlantPartEvidenceKind.Edible, null, reference.sources.single())),
        )
        compose.setContent { HikeJournalTheme { EdibilitySection(disputed) } }
        val conflict = compose.onNodeWithText("Sources disagree about food use").assertIsDisplayed()
        val claim = compose.onNodeWithText("Berries · Reported edible").assertIsDisplayed()
        assertTrue(conflict.getUnclippedBoundsInRoot().top < claim.getUnclippedBoundsInRoot().top)
    }

    private fun speciesRecord(name: String, report: EdibilityReference, ecology: String, overview: String) =
        SpeciesRecord(
            key = "taxon:${report.taxonId}",
            taxonId = report.taxonId,
            commonName = name,
            scientificName = report.scientificName,
            rank = report.rank,
            iconicTaxonName = "Plantae",
            wikipediaUrl = "",
            wikipediaSummary = overview,
            encounterCount = 1,
            hikeCount = 1,
            hikeIds = emptyList(),
            hikeEncounterCounts = emptyMap(),
            hikeCoverUrls = emptyMap(),
            hikeLatestSeen = emptyMap(),
            latestSeen = null,
            coverUrl = InstrumentationRegistry.getArguments().getString("edibilityCoverFixture").orEmpty(),
            ecology = EcologyStatus(label = ecology),
            edibility = report,
            edibilityReferenceEnabled = true,
            edibilityDatasetVersion = report.datasetVersion,
        )

    private fun showSpecies(name: String, report: EdibilityReference, ecology: String, overview: String) {
        val species = speciesRecord(name, report, ecology, overview)
        compose.setContent {
            HikeJournalTheme { SpeciesDetailScreen(species, listOf(species), "Plants", false, {}, {}, {}) }
        }
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
        compose.onNodeWithText("Fixture plant · Used as food").assertDoesNotExist()
        compose.runOnIdle { enabled.value = true }
        compose.onNodeWithText("Fixture plant · Used as food").assertIsDisplayed()
        compose.onNodeWithText("Fixture hazard · Caution").assertIsDisplayed().performClick()
        compose.onNodeWithText("Example hazard").assertIsDisplayed()
        captureEvidence()
        compose.onNodeWithText("Synthetic warning").performScrollTo().assertIsDisplayed()
        compose.runOnIdle { FoodUsePreferences(context).invalidatePhotoIdentity(photo.id) }
        compose.onNodeWithText(EdibilitySectionTitle).assertDoesNotExist()
        compose.onNodeWithText("Fixture plant · Used as food").assertDoesNotExist()
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

    private fun captureEvidence(name: String = "edibility-reference.png") {
        if (InstrumentationRegistry.getArguments().getString("edibilityScreenshot") != "true") return
        compose.waitForIdle()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        instrumentation.waitForIdleSync()
        SystemClock.sleep(350)
        val screenshot = instrumentation.uiAutomation.takeScreenshot()
        File(context.filesDir, name).outputStream().use {
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
