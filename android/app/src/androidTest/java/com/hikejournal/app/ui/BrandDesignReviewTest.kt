package com.hikejournal.app.ui

import android.view.View
import android.view.ViewGroup
import android.os.SystemClock
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.geometry.LatLng
import java.util.concurrent.atomic.AtomicReference
import android.graphics.Bitmap
import android.content.ContentValues
import android.os.Environment
import android.provider.MediaStore
import androidx.compose.ui.test.hasScrollToIndexAction
import androidx.compose.ui.test.performScrollToIndex
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.isDisplayed
import androidx.lifecycle.Lifecycle
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.width
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.text.TextLayoutResult
import androidx.test.platform.app.InstrumentationRegistry
import com.hikejournal.app.AppState
import com.hikejournal.app.data.*
import com.hikejournal.app.ui.theme.HikeJournalTheme
import com.hikejournal.app.ui.theme.Parchment
import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Rule
import org.junit.Test

/** Exercise the actual composables with local fixtures; no account or production writes. */
class BrandDesignReviewTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val imageUrl: String by lazy {
        val file = File(context.cacheDir, "brand-design-hike.jpg")
        instrumentation.context.assets.open("design/hike.jpg").use { source -> file.outputStream().use { source.copyTo(it) } }
        file.toURI().toString()
    }
    private val hike get() = Hike("design-hike", "Bronson Pine Walk", "2026-11-10", 5.7,
        locationName = "Charles H. Bronson State Forest", notes = "A quiet morning on the trail.",
        isArchived = false, coverUrl = imageUrl, photoCount = 16, speciesCount = 8)
    private val photo get() = Photo("design-photo", hike.id, imageUrl.removePrefix("file:"), "Along the pine trail", "2026-11-10", null,
        28.65, -81.02, 800, 800, "image/jpeg", "complete", species = emptyList())
    private val species get() = SpeciesRecord("smartweed", 1, "Swamp smartweed", "Persicaria hydropiperoides",
        "species", "Plantae", "", "", 4, 2, listOf(hike.id), emptyMap(), emptyMap(), emptyMap(),
        "2026-11-10", imageUrl)
    private val review get() = ReviewItem("design-review", photo, hike.id, hike.title, hike.hikeDate,
        hike.locationName, "pending", null, emptyList())

    @Composable private fun Frame(destination: TopDestination, content: @Composable () -> Unit) {
        HikeJournalTheme {
            Box(Modifier.fillMaxSize().background(Parchment)) {
                content()
                TopNavigation(destination, {}, Modifier.align(Alignment.BottomCenter),
                    onAdd = if (destination == TopDestination.Archive) ({}) else null)
            }
        }
    }
    private fun capture(name: String) {
        rule.waitForIdle()
        // Let Coil's local-file request and Android's native window reach the display.
        instrumentation.waitForIdleSync()
        SystemClock.sleep(800)
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, "$name.png")
            put(MediaStore.MediaColumns.MIME_TYPE, "image/png")
            put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/HikeJournal-design-review")
        }
        val uri = context.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)!!
        instrumentation.uiAutomation.takeScreenshot().let { bitmap ->
            context.contentResolver.openOutputStream(uri)!!.use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
            bitmap.recycle()
        }
    }

    private fun assertHeadingFits(text: String) {
        rule.onAllNodesWithText(text)[0].assertIsDisplayed().performSemanticsAction(SemanticsActions.GetTextLayoutResult) { action ->
            val results = mutableListOf<TextLayoutResult>()
            action(results)
            val layout = results.single()
            assertFalse("Heading clipped: $text, size=${layout.size}, width=${layout.didOverflowWidth}, height=${layout.didOverflowHeight}, right=${layout.getLineRight(0)}", layout.hasVisualOverflow)
        }
    }

    @Test fun hikesHeaderSearchAndNavigation() {
        rule.setContent { Frame(TopDestination.Archive) {
            LibraryScreen(AppState(hikes = listOf(hike, hike.copy(id = "older", title = "Hidden Pond")), isLoading = false),
                null, {}, {}, {}, {}, {}, {}, {}, {}, {}, {})
        } }
        assertHeadingFits("HikeJournal")
        rule.onNodeWithContentDescription("Add hike or everyday sighting").assertIsDisplayed()
        capture("01-hikes")
    }

    @Test fun fieldGuideAndTabs() {
        rule.setContent { Frame(TopDestination.Species) {
            SpeciesIndexScreen(listOf(species), listOf(hike), emptyList(), null, emptyList(), null, null, null, null,
                loading = false, discoveryLoading = false, savingQuest = false, offline = false, discoveryNotice = null,
                questMapLoading = false, questMapNotice = null, onRefresh = {}, onRefreshDiscovery = {}, onOpenDiscovery = {},
                onLoadNearby = { _, _, _, _, _, _, _ -> }, onSaveQuest = { _, _, _, _ -> }, onSaveQuestFocus = { _, _ -> },
                onRenameQuest = { _, _ -> }, onArchiveQuest = {}, onDeleteQuest = {}, onOpenNearbyMap = { _, _ -> },
                onOpenQuestMap = { _, _ -> }, onRefreshQuestMap = {}, onCloseQuestMap = {}, onInitialAreaConsumed = {},
                collectionPreferences = SpeciesCollectionPreferences(), onCollectionPreferencesChange = {}, onOpenSpecies = { _, _, _ -> })
        } }
        assertHeadingFits("Field Guide")
        capture("02-field-guide")
        rule.onNodeWithText("FIELD QUESTS").performClick()
        rule.onNodeWithText("Field Quests").assertIsDisplayed()
    }

    @Test fun reviewActionsAndSafetyFooter() {
        rule.setContent { Frame(TopDestination.Review) {
            SpeciesReviewScreen(listOf(review), false, null, null, false, null, true, false,
                {}, { _, _, _ -> }, {}, {}, {}, {}, {}, {})
        } }
        assertHeadingFits("Species Review")
        rule.onNodeWithText("Batch ID").assertIsDisplayed()
        capture("03-review-header")
        rule.onNodeWithText("Identify this sighting").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("Skip for now").performScrollTo()
        capture("04-review-actions")
        rule.onNode(hasScrollToIndexAction()).performScrollToIndex(2)
        rule.onNodeWithText(IdentificationSafetyNotice.Reminder).assertIsDisplayed()
        capture("14-review-footer")
    }

    @Test fun publishTabsAndPublicConfirmation() {
        var submitted = false
        val item = PublishItem("publish", photo, hike.id, hike.title, hike.hikeDate, hike.locationName, 1,
            species.commonName, species.scientificName, "ready", null, "", null, false, listOf("publish"), 1)
        rule.setContent { Frame(TopDestination.Publish) {
            PublishingScreen(PublishQueue(true, 1, 0, 0, listOf(item)), listOf(hike), false, null, false, null, null, false,
                {}, { _, _ -> submitted = true }, { _, _ -> }, {}, {}, {})
        } }
        assertHeadingFits("Publish")
        capture("05-publish-header")
        rule.onNodeWithText("Publish now").performScrollTo()
        rule.onNodeWithText("Publish now").assertIsDisplayed().performClick()
        capture("06-publish-confirmation")
        rule.waitUntil(5_000) { rule.onNodeWithText("Publish publicly").isDisplayed() }
        rule.onNodeWithText("Publish publicly").assertIsDisplayed()
        assertFalse("Opening confirmation must not publish", submitted)
        capture("06-publish-confirmation")
    }

    @Test fun trailMedalSheetHasNoCloseAction() {
        rule.setContent { HikeJournalTheme {
            BadgesScreen(AppState(hikes = listOf(hike), species = listOf(species), isLoading = false), false, {}, {})
        } }
        assertHeadingFits("Trail Medals")
        rule.onNodeWithText("0 of 36 earned · Lifetime progress").assertDoesNotExist()
        capture("07-medals")
        rule.onNodeWithText("First Footfall").performClick()
        rule.onNodeWithText("Close").assertDoesNotExist()
        capture("08-medal-sheet")
    }

    @Test fun speciesAndPlaceWordmarks() {
        rule.setContent { HikeJournalTheme {
            SpeciesDetailScreen(species, listOf(species), null, false, {}, {}, {})
        } }
        assertHeadingFits("HikeJournal")
        capture("09-species-detail")
    }

    @Test fun placeProfileWordmark() {
        rule.setContent { HikeJournalTheme {
            PlaceProfileScreen(null, true, hike.locationName, imageUrl, false, "1 of 5", 7, false,
                {}, {}, {}, {}, {}, null, null)
        } }
        assertHeadingFits("HikeJournal")
        rule.onNodeWithText("PLACE PROFILE · 1 of 5").assertIsDisplayed()
        capture("10-place-profile")
    }

    @Test fun compactDiscoveryCelebration() {
        rule.setContent { HikeJournalTheme {
            FieldCelebrationDialog(FieldCelebration("discovery", CelebrationKind.Discovery,
                "NEW TO YOUR FIELD GUIDE", "Swamp smartweed", "Your first confirmed plant record is now part of your living archive.",
                listOf(imageUrl), listOf(CelebrationHighlight("676", "species logged"), CelebrationHighlight("Plants", "life group")),
                "BADGE PROGRESS", "676 species in your Field Guide"), {})
        } }
        rule.onNodeWithText("Continue").assertIsDisplayed()
        capture("11-discovery")
    }
    @Test fun sightingsMapRendersImageryAndPhotoInspector() {
        val location = LatLng(28.65, -81.02)
        val sighting = Sighting("map-photo", hike.id, hike.title, hike.hikeDate, hike.locationName,
            imageUrl, "Flower beside the trail", "2026-11-10", location.latitude, location.longitude,
            "Swamp smartweed", species.scientificName, true, thumbnailUrl = "file:/missing-thumbnail.jpg")
        rule.setContent { Frame(TopDestination.Map) {
            SightingsMapScreen(listOf(sighting), emptyList(), 1,
                MapBounds(-81.025, 28.645, -81.015, 28.655), emptySet(), false, null, {},
                { _, _, _, _, _ -> }, {}, {})
        } }
        val map = AtomicReference<MapLibreMap>()
        rule.runOnIdle {
            findMapView(rule.activity.window.decorView)!!.getMapAsync { loaded ->
                loaded.getStyle { map.set(loaded) }
            }
        }
        rule.waitUntil(15_000) { map.get() != null }
        rule.waitUntil(10_000) { map.get().cameraPosition.zoom > 10 }
        SystemClock.sleep(4000)
        capture("12-sightings-map")
        rule.activityRule.scenario.moveToState(Lifecycle.State.CREATED)
        rule.activityRule.scenario.moveToState(Lifecycle.State.RESUMED)
        rule.waitForIdle()
        var x = 0
        var y = 0
        rule.runOnIdle {
            val view = findMapView(rule.activity.window.decorView)!!
            val offset = IntArray(2)
            view.getLocationOnScreen(offset)
            val point = map.get().projection.toScreenLocation(location)
            x = point.x.toInt() + offset[0]
            y = point.y.toInt() + offset[1]
        }
        capture("map-after-resume")
        instrumentation.uiAutomation.executeShellCommand("input tap $x $y").use {
            java.io.FileInputStream(it.fileDescriptor).use { input -> input.readBytes() }
        }
        rule.waitForIdle()
        rule.waitUntil(5_000) { rule.onNodeWithText("Swamp smartweed").isDisplayed() }
        rule.onNodeWithText("Swamp smartweed").assertIsDisplayed()
        capture("13-map-photo")
    }

    @Test fun reviewTitleFitsCompactPhoneWidth() {
        rule.setContent { HikeJournalTheme {
            Box(Modifier.width(320.dp)) {
                BrandScreenHeader("Species Review", "1 to decide · 1 need ID", actions = {
                    androidx.compose.material3.TextButton(onClick = {}) { androidx.compose.material3.Text("Batch ID") }
                    androidx.compose.material3.IconButton(onClick = {}) { androidx.compose.material3.Text("R") }
                })
            }
        } }
        assertHeadingFits("Species Review")
    }

    @Test fun googleSignInUsesBrandHeaderAndKeepsAction() {
        var signInRequested = false
        rule.setContent { HikeJournalTheme {
            GoogleSetupGate(false, null, { signInRequested = true })
        } }
        assertHeadingFits("HikeJournal")
        capture("15-google-sign-in")
        rule.onAllNodesWithText("Sign in with Google")[1].assertIsDisplayed().performClick()
        org.junit.Assert.assertTrue(signInRequested)
    }

    @Test fun stateSetupUsesBrandAndRequiresSelection() {
        var chosenState: String? = null
        rule.setContent { HikeJournalTheme { LocationLibrarySetupGate { chosenState = it } } }
        assertHeadingFits("HikeJournal")
        rule.onNodeWithText("Load places").assertIsNotEnabled()
        rule.onNodeWithText("State").performClick()
        rule.onNodeWithText("Florida").performScrollTo().performClick()
        rule.onNodeWithText("Load places").assertIsEnabled()
        capture("16-state-setup")
        rule.onNodeWithText("Load places").performClick()
        org.junit.Assert.assertEquals("FL", chosenState)
    }

    @Test fun firstRunGuideUsesBrandHeader() {
        rule.setContent { HikeJournalTheme { GettingStartedScreen({}, {}) } }
        assertHeadingFits("HikeJournal")
        rule.onNodeWithText("Next").assertIsDisplayed()
        capture("17-getting-started")
    }

    @Test fun safetyEntryUsesBrandHeaderAndVisibleAction() {
        rule.setContent { HikeJournalTheme { IdentificationSafetyScreen(onAcknowledge = {}) } }
        assertHeadingFits("HikeJournal")
        rule.onNodeWithText("Acknowledge and continue").assertIsDisplayed()
        capture("18-safety-entry")
    }

    private fun findMapView(view: View): MapView? {
        if (view is MapView) return view
        if (view is ViewGroup) for (index in 0 until view.childCount) {
            findMapView(view.getChildAt(index))?.let { return it }
        }
        return null
    }

}
