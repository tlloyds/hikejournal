package com.hikejournal.app.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.hikejournal.app.ui.theme.HikeJournalTheme
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class GettingStartedScreenTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun guideMovesFromOverviewToStartAction() {
        var started = false
        composeRule.setContent {
            HikeJournalTheme {
                GettingStartedScreen(
                    onDismiss = {},
                    onStartOuting = { started = true },
                )
            }
        }

        composeRule.onNodeWithText("Keep the whole outing.").assertIsDisplayed()
        composeRule.onNodeWithText("Next").performClick()
        composeRule.onNodeWithText("Let the trail tell its story.").assertIsDisplayed()

        repeat(3) {
            composeRule.onNodeWithText("Next").performClick()
        }
        composeRule.onNodeWithText("Start an outing").assertIsDisplayed()
        composeRule.onNodeWithText("Start an outing").performClick()
        assertTrue(started)
    }
}
