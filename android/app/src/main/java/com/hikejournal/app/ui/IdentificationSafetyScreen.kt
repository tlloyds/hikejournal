@file:OptIn(androidx.compose.ui.text.ExperimentalTextApi::class)

package com.hikejournal.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
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
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.hikejournal.app.R
import com.hikejournal.app.data.IdentificationSafetyPreferences
import com.hikejournal.app.ui.theme.Moss

// The bundled variable font defaults to ExtraLight. Select real weight-axis values
// rather than labelling the same default face with several different weights.
private val SafetyBodyFamily = FontFamily(
    Font(R.font.source_sans_3, weight = FontWeight.Medium,
        variationSettings = FontVariation.Settings(FontVariation.weight(500))),
    Font(R.font.source_sans_3, weight = FontWeight.SemiBold,
        variationSettings = FontVariation.Settings(FontVariation.weight(600))),
)
private val SafetyDisplayFamily = FontFamily(
    Font(R.font.cormorant_garamond, weight = FontWeight.SemiBold,
        variationSettings = FontVariation.Settings(FontVariation.weight(600))),
)
private val SafetyInk = Color(0xFF101A14)
private val SafetyLink = Color(0xFF164D33)
private val SafetySurface = Color(0xFFFFFFFF)
private val SafetySurfaceEnd = Color(0xFFF4F6F0)

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
    val bodyStyle = MaterialTheme.typography.bodyLarge.copy(
        fontFamily = SafetyBodyFamily, fontWeight = FontWeight.Medium,
        fontSize = 18.sp, lineHeight = 28.sp,
    )
    val labelStyle = bodyStyle.copy(fontWeight = FontWeight.SemiBold, fontSize = 17.sp, lineHeight = 25.sp)
    val buttonColors = ButtonDefaults.buttonColors(
        containerColor = Moss, contentColor = Color.White,
        disabledContainerColor = Color(0xFFD9E0D7), disabledContentColor = Color(0xFF344237),
    )
    Column(
        Modifier.fillMaxSize()
            .background(Brush.verticalGradient(listOf(SafetySurface, SafetySurfaceEnd)))
            .statusBarsPadding().navigationBarsPadding(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Column(
            Modifier.weight(1f).widthIn(max = 640.dp).fillMaxWidth()
                .verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            Text("HikeJournal", style = MaterialTheme.typography.headlineLarge.copy(
                fontFamily = SafetyDisplayFamily, fontWeight = FontWeight.SemiBold,
                fontSize = 40.sp, lineHeight = 46.sp,
            ), color = Moss)
            Text(IdentificationSafetyNotice.Title, style = MaterialTheme.typography.headlineMedium.copy(
                fontFamily = SafetyDisplayFamily, fontWeight = FontWeight.SemiBold,
            ), color = SafetyInk, modifier = Modifier.semantics { heading() })
            Text(IdentificationSafetyNotice.Affiliation, style = bodyStyle, color = SafetyInk)
            Text(IdentificationSafetyNotice.Accuracy, style = bodyStyle, color = SafetyInk)
            Text(IdentificationSafetyNotice.Verification, style = bodyStyle, color = SafetyInk)
            Text(IdentificationSafetyNotice.Consumption, style = bodyStyle.copy(fontWeight = FontWeight.SemiBold), color = SafetyInk)
            Text(IdentificationSafetyNotice.Purpose, style = bodyStyle, color = SafetyInk)
            TextButton(onClick = { uriHandler.openUri(IdentificationSafetyNotice.GuidanceURL) }) {
                Text("About iNaturalist suggestions", style = labelStyle, color = SafetyLink,
                    textDecoration = TextDecoration.Underline)
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
                    Checkbox(checked = understood, onCheckedChange = null,
                        colors = CheckboxDefaults.colors(checkedColor = Moss,
                            uncheckedColor = SafetyInk, checkmarkColor = Color.White))
                    Text(IdentificationSafetyNotice.Acknowledgment, style = bodyStyle,
                        color = SafetyInk, modifier = Modifier.padding(start = 12.dp))
                }
            }
        }
        if (onAcknowledge != null) {
            Button(onClick = onAcknowledge, enabled = understood, colors = buttonColors,
                modifier = Modifier.widthIn(max = 640.dp).fillMaxWidth()
                    .padding(horizontal = 24.dp, vertical = 12.dp).heightIn(min = 56.dp)) {
                Text("Acknowledge and continue", style = labelStyle)
            }
        } else if (onClose != null) {
            Button(onClick = onClose, colors = buttonColors,
                modifier = Modifier.widthIn(max = 640.dp).fillMaxWidth()
                    .padding(horizontal = 24.dp, vertical = 12.dp).heightIn(min = 56.dp)) {
                Text("Done", style = labelStyle)
            }
        }
    }
}

@Composable
internal fun IdentificationSafetyReminder(modifier: Modifier = Modifier, color: Color = SafetyInk) {
    Text(IdentificationSafetyNotice.Reminder, style = MaterialTheme.typography.bodyMedium.copy(
        fontFamily = SafetyBodyFamily, fontWeight = FontWeight.Medium,
        fontSize = 15.sp, lineHeight = 23.sp,
    ), color = color, modifier = modifier)
}
