package com.hikejournal.app.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import com.hikejournal.app.data.CelebrationHighlight
import com.hikejournal.app.data.CelebrationKind
import com.hikejournal.app.data.FieldCelebration
import com.hikejournal.app.ui.theme.HikeJournalTheme
import org.junit.Rule
import org.junit.Test

class FieldCelebrationDialogTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun reviewActionIsFullyDisplayedWithoutScrolling() {
        composeRule.setContent {
            HikeJournalTheme {
                FieldCelebrationDialog(
                    celebration = FieldCelebration(
                        id = "batch:test",
                        kind = CelebrationKind.Identification,
                        eyebrow = "THE FIELD NOTES ARE IN",
                        title = "5 possible new species",
                        detail = "Review the suggestions to add confirmed finds to your Field Guide. " +
                            "4 plants · 1 insect are new possibilities in this batch. " +
                            "The 4-photo group did not reach consensus; saved individual suggestions instead.",
                        highlights = listOf(
                            CelebrationHighlight("56", "photos read"),
                            CelebrationHighlight("27", "unique IDs"),
                            CelebrationHighlight("5", "possible new"),
                        ),
                        actionLabel = "Review discoveries",
                    ),
                    onDismiss = {},
                )
            }
        }

        composeRule.waitForIdle()
        composeRule.onNodeWithText("Review discoveries").assertIsDisplayed()
    }
}
