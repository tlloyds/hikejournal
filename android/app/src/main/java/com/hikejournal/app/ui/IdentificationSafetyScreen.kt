package com.hikejournal.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import com.hikejournal.app.data.IdentificationSafetyPreferences
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment

internal object IdentificationSafetyNotice {
    const val Title = "Identification safety"
    const val Affiliation = "HikeJournal is an independent app. It is not an official iNaturalist app or channel, and is not affiliated with or endorsed by iNaturalist."
    const val Accuracy = "Identifications from photos, automated suggestions, community observations, and saved or confirmed labels may be incomplete or wrong. A confidence score or a confirmed label is not a guarantee."
    const val Verification = "Treat every identification as a starting point for learning. Verify it independently with a qualified local expert and reliable field references."
    const val Consumption = "Never eat, taste, prepare food or drink from, or use any wild organism based on an identification shown in HikeJournal. Do not use the app to decide whether an organism is edible, non-toxic, medicinal, or safe to touch or handle."
    const val Purpose = "HikeJournal is for nature journaling and education. It is not a foraging, medical, or safety-advice service."
    const val Acknowledgment = "I understand these limits and will not use app identifications to make consumption or safety decisions."
    const val Reminder = "IDs may be wrong, even when marked confirmed. Verify independently with a qualified expert. Never use an app ID to decide what to eat or what is safe to touch or use."
    const val GuidanceURL = "https://help.inaturalist.org/en/support/solutions/articles/151000170369-why-can-t-computer-vision-identify-my-photo-correctly-"
}

@Composable
internal fun IdentificationSafetyGate(
    preferences: IdentificationSafetyPreferences,
    content: @Composable () -> Unit,
) {
    var acknowledged by remember(preferences) { mutableStateOf(preferences.hasAcknowledged) }
    if (acknowledged) {
        content()
    } else {
        IdentificationSafetyScreen(onAcknowledge = {
            preferences.acknowledge()
            acknowledged = true
        })
    }
}

@Composable
internal fun IdentificationSafetyScreen(
    onAcknowledge: (() -> Unit)? = null,
    onClose: (() -> Unit)? = null,
) {
    var understood by rememberSaveable { mutableStateOf(false) }
    val uriHandler = LocalUriHandler.current
    Column(
        Modifier.fillMaxSize()
            .background(Brush.verticalGradient(listOf(Paper, Parchment)))
            .statusBarsPadding().navigationBarsPadding(),
    ) {
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            Text("HikeJournal", style = MaterialTheme.typography.displaySmall, color = Moss)
            Text(IdentificationSafetyNotice.Title, style = MaterialTheme.typography.headlineMedium, color = Ink)
            Text(IdentificationSafetyNotice.Affiliation, style = MaterialTheme.typography.bodyLarge, color = InkMuted)
            Text(IdentificationSafetyNotice.Accuracy, style = MaterialTheme.typography.bodyLarge, color = Ink)
            Text(IdentificationSafetyNotice.Verification, style = MaterialTheme.typography.bodyLarge, color = Ink)
            Text(IdentificationSafetyNotice.Consumption, style = MaterialTheme.typography.bodyLarge, color = Ink)
            Text(IdentificationSafetyNotice.Purpose, style = MaterialTheme.typography.bodyMedium, color = InkMuted)
            TextButton(onClick = { uriHandler.openUri(IdentificationSafetyNotice.GuidanceURL) }) {
                Text("About iNaturalist suggestions")
            }
            if (onAcknowledge != null) {
                Row(
                    Modifier.fillMaxWidth().toggleable(
                        value = understood,
                        role = Role.Checkbox,
                        onValueChange = { understood = it },
                    ).padding(vertical = 10.dp),
                    verticalAlignment = Alignment.Top,
                ) {
                    Checkbox(checked = understood, onCheckedChange = null)
                    Text(IdentificationSafetyNotice.Acknowledgment, style = MaterialTheme.typography.bodyMedium,
                        color = Ink, modifier = Modifier.padding(start = 12.dp))
                }
            }
        }
        if (onAcknowledge != null) {
            Button(onClick = onAcknowledge, enabled = understood,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 12.dp)) {
                Text("Acknowledge and continue")
            }
        } else if (onClose != null) {
            Button(onClick = onClose,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 12.dp)) {
                Text("Done")
            }
        }
    }
}

@Composable
internal fun IdentificationSafetyReminder(modifier: Modifier = Modifier, color: Color = InkMuted) {
    Text(IdentificationSafetyNotice.Reminder, style = MaterialTheme.typography.bodySmall, color = color, modifier = modifier)
}
