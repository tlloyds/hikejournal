package com.hikejournal.app.ui

import android.content.Context
import androidx.compose.material3.Text
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.platform.app.InstrumentationRegistry
import com.hikejournal.app.data.IdentificationSafetyPreferences
import com.hikejournal.app.ui.theme.HikeJournalTheme
import java.util.UUID
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class IdentificationSafetyTest {
    @get:Rule val composeRule = createComposeRule()
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val preferenceName = "safety-test-${UUID.randomUUID()}"
    private val defaults = context.getSharedPreferences(preferenceName, Context.MODE_PRIVATE)

    @After fun cleanUp() { context.deleteSharedPreferences(preferenceName) }

    @Test
    fun appContentRequiresExplicitAcknowledgmentAndPersistsAcrossInstances() {
        val preferences = IdentificationSafetyPreferences(defaults)
        composeRule.setContent {
            HikeJournalTheme {
                IdentificationSafetyGate(preferences) { Text("Journal is available") }
            }
        }
        composeRule.onNodeWithText("Journal is available").assertDoesNotExist()
        composeRule.onNodeWithText("Acknowledge and continue").assertIsNotEnabled()
        composeRule.onNodeWithText(IdentificationSafetyNotice.Consumption).performScrollTo().assertExists()
        composeRule.onNodeWithText(IdentificationSafetyNotice.Acknowledgment).performScrollTo().performClick()
        composeRule.onNodeWithText("Acknowledge and continue").assertIsEnabled().performClick()
        composeRule.onNodeWithText("Journal is available").assertExists()
        assertTrue(IdentificationSafetyPreferences(defaults).hasAcknowledged)
    }

    @Test
    fun materialNoticeUpdateRequiresAcknowledgmentAgain() {
        IdentificationSafetyPreferences(defaults).acknowledge()
        val updated = IdentificationSafetyPreferences(defaults, requiredNoticeVersion = 2)
        assertFalse(updated.hasAcknowledged)
        updated.acknowledge()
        assertTrue(IdentificationSafetyPreferences(defaults, requiredNoticeVersion = 2).hasAcknowledged)
    }

    @Test
    fun settingsCopyDoesNotRecordAcknowledgmentOrShowTheConsentControls() {
        var closed = false
        composeRule.setContent {
            HikeJournalTheme { IdentificationSafetyScreen(onClose = { closed = true }) }
        }
        composeRule.onNodeWithText("Acknowledge and continue").assertDoesNotExist()
        composeRule.onNodeWithText(IdentificationSafetyNotice.Acknowledgment).assertDoesNotExist()
        composeRule.onNodeWithText("Done").performClick()
        assertTrue(closed)
        assertFalse(IdentificationSafetyPreferences(defaults).hasAcknowledged)
    }
}
