package com.hikejournal.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.MenuBook
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.hikejournal.app.data.EdibilityReference
import com.hikejournal.app.data.FoodUseIndicator
import com.hikejournal.app.data.FoodUsePreferences
import com.hikejournal.app.data.FoodUseStatus
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.ToxicityStatus
import com.hikejournal.app.data.foodUseTags
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment

internal const val EdibilitySectionTitle = "Edibility & Ethnobotany"
private const val Disclaimer = "Educational species reference only. This information does not confirm the identity or safety of your photographed specimen. Do not use HikeJournal to decide what to eat."

@Composable
internal fun EdibilitySection(
    reference: EdibilityReference?,
    modifier: Modifier = Modifier,
    showTitle: Boolean = true,
) {
    val uriHandler = LocalUriHandler.current
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (showTitle) {
            Text(EdibilitySectionTitle, style = MaterialTheme.typography.titleLarge, color = Ink)
        }
        Text(Disclaimer, style = MaterialTheme.typography.bodyMedium, color = Ink, fontWeight = FontWeight.Medium)
        if (reference == null) {
            Text("No reference data available", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
            return@Column
        }
        val foodUse = when (reference.foodUse) {
            FoodUseStatus.Documented -> "Documented human food use"
            FoodUseStatus.Conditional -> "Conditional food use"
            FoodUseStatus.Disputed -> if (reference.hasDocumentedFoodUse) {
                "Food-use records with conflicting evidence"
            } else {
                "Disputed food use"
            }
            FoodUseStatus.Unknown -> "No food-use record available"
        }
        Text(foodUse, style = MaterialTheme.typography.titleSmall, color = Ink)
        if (reference.foodUse == FoodUseStatus.Documented && reference.documentedParts.isEmpty()) {
            ReferenceText("This taxon is listed in a published food-plant checklist. The record does not establish specific parts or preparation.")
        }
        if (reference.documentedParts.isNotEmpty()) {
            ReferenceText("Documented parts · ${reference.documentedParts.joinToString()}")
        }
        reference.foodUseNotes?.let { ReferenceText(it) }
        if (reference.evidenceConflict) {
            FoodUseIndicatorLabel(FoodUseIndicator.Conflict, CautionText)
        }
        if (reference.toxicity == ToxicityStatus.DocumentedConcern) {
            FoodUseIndicatorLabel(FoodUseIndicator.Toxicity, CautionText)
            reference.toxicityNotes?.let { ReferenceText(it) }
        } else {
            ReferenceText("Toxicity not assessed by available sources")
        }
        reference.sources.forEach { source ->
            TextButton(onClick = { uriHandler.openUri(source.url) }) {
                Text("${source.title} · Version ${source.version}", color = Moss)
            }
            ReferenceText(listOf(source.attribution, source.publisher).filter(String::isNotBlank).joinToString(" · "))
            if (source.licenseUrl != null) {
                TextButton(onClick = { uriHandler.openUri(source.licenseUrl) }) {
                    Text(source.license, color = Moss)
                }
            } else {
                ReferenceText(source.license)
            }
            if (source.modifications.isNotBlank()) ReferenceText(source.modifications)
        }
    }
}

@Composable
internal fun FoodUseIndicatorLabel(
    indicator: FoodUseIndicator,
    color: Color,
    speciesName: String? = null,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(
            if (indicator.warning) Icons.Rounded.WarningAmber else Icons.AutoMirrored.Rounded.MenuBook,
            contentDescription = null,
            modifier = Modifier.size(20.dp),
            tint = color,
        )
        Text(
            if (speciesName.isNullOrBlank()) indicator.label else "$speciesName · ${indicator.label}",
            style = MaterialTheme.typography.bodyMedium,
            color = color,
            fontWeight = FontWeight.Medium,
        )
    }
}

private val CautionText = Color(0xFF8A4F16)

@Composable
private fun ReferenceText(value: String) {
    Text(value, style = MaterialTheme.typography.bodyMedium, color = InkMuted)
}

@Composable
internal fun PhotoFoodUseReferences(photo: Photo, show: Boolean) {
    if (!show) return
    val context = LocalContext.current
    val preferences = remember(context) { FoodUsePreferences(context) }
    var changedAt by remember(photo.id) { mutableLongStateOf(preferences.identityChangedAt(photo.id)) }
    DisposableEffect(photo.id, preferences) {
        val unsubscribe = preferences.observePhotoIdentity(photo.id) {
            changedAt = preferences.identityChangedAt(photo.id)
        }
        onDispose(unsubscribe)
    }
    val datasetVersion = rememberEdibilityDatasetVersion()
    val foodUseTags = photo.foodUseTags(show, changedAt, currentDatasetVersion = datasetVersion)
    var selectedFoodReference by remember(photo.id) { mutableStateOf<Pair<String?, Long>?>(null) }
    foodUseTags.forEach { (tag, reference) ->
        reference.indicator?.let { indicator ->
            TextButton(
                onClick = { selectedFoodReference = tag.observationId to reference.taxonId },
            ) {
                FoodUseIndicatorLabel(
                    indicator,
                    if (indicator.warning) Color(0xFFFFCC9A) else Paper,
                    speciesName = tag.commonName.ifBlank { tag.scientificName }
                        .takeUnless { tag.isPrimary && foodUseTags.size == 1 },
                )
            }
        }
    }
    val selected = foodUseTags.firstOrNull { (tag, reference) ->
        selectedFoodReference == (tag.observationId to reference.taxonId)
    }
    LaunchedEffect(selected) {
        if (selected == null) selectedFoodReference = null
    }
    selected?.let { (tag, reference) ->
        AlertDialog(
            onDismissRequest = { selectedFoodReference = null },
            title = { Text(EdibilitySectionTitle, color = Ink) },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    Text(tag.scientificName, style = MaterialTheme.typography.titleMedium, color = Ink)
                    EdibilitySection(reference, Modifier.padding(top = 12.dp), showTitle = false)
                }
            },
            containerColor = Parchment,
            confirmButton = {
                TextButton(onClick = { selectedFoodReference = null }) { Text("Done", color = Moss) }
            },
        )
    }
}


@Composable
internal fun rememberEdibilityDatasetVersion(): String? {
    val context = LocalContext.current
    val preferences = remember(context) { FoodUsePreferences(context) }
    var version by remember(preferences) { mutableStateOf(preferences.datasetVersion()) }
    DisposableEffect(preferences) {
        val unsubscribe = preferences.observeDatasetVersion { version = preferences.datasetVersion() }
        onDispose(unsubscribe)
    }
    return version
}
