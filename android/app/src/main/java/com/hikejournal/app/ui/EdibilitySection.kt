package com.hikejournal.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.MenuBook
import androidx.compose.material.icons.rounded.ExpandMore
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
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
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.TrailText

internal const val EdibilitySectionTitle = "Edibility & Ethnobotany"
private const val Disclaimer = "Educational species reference only. This information does not confirm the identity or safety of your photographed specimen. Do not use HikeJournal to decide what to eat."

internal val FoodUseIndicator.fieldGuideLabel: String
    get() = when (this) {
        FoodUseIndicator.FoodUses -> "Edible use documented"
        FoodUseIndicator.Toxicity -> "Toxicity concern"
        else -> label
    }

@Composable
internal fun FoodUseIndicator.fieldGuideColor(): Color = when (this) {
    FoodUseIndicator.Toxicity -> MaterialTheme.colorScheme.error
    FoodUseIndicator.FoodUses -> Moss
    else -> TrailText
}

private val FoodUseIndicator.symbol
    get() = if (warning) Icons.Rounded.WarningAmber else Icons.AutoMirrored.Rounded.MenuBook

@Composable
internal fun EdibilitySection(
    reference: EdibilityReference?,
    modifier: Modifier = Modifier,
    showTitle: Boolean = true,
) {
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (showTitle) {
            Text(
                EdibilitySectionTitle,
                style = MaterialTheme.typography.labelMedium,
                color = TrailText,
                modifier = Modifier.semantics { heading() },
            )
        }
        val indicator = reference?.indicator
        val color = indicator?.fieldGuideColor() ?: Ink
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            indicator?.let {
                Icon(it.symbol, contentDescription = null, modifier = Modifier.size(22.dp), tint = color)
            }
            Text(
                indicator?.fieldGuideLabel ?: "No reference data available",
                style = MaterialTheme.typography.titleLarge,
                color = color,
                modifier = Modifier.semantics { heading() },
            )
        }

        if (reference != null) {
            if (reference.toxicity == ToxicityStatus.DocumentedConcern) {
                reference.toxicityNotes?.let { ReferenceText(it) }
                val secondaryStatus = when (reference.foodUse) {
                    FoodUseStatus.Documented -> "Human food use is also documented."
                    FoodUseStatus.Conditional -> "Conditional food use is also documented."
                    FoodUseStatus.Disputed -> "There is also conflicting evidence about food use."
                    FoodUseStatus.Unknown -> null
                }
                secondaryStatus?.let {
                    Text(it, style = MaterialTheme.typography.titleSmall, color = Ink)
                }
            }
            if (
                reference.evidenceConflict &&
                indicator != FoodUseIndicator.Conflict &&
                reference.foodUse != FoodUseStatus.Disputed
            ) {
                ReferenceText("Sources also disagree about food use.")
            }
            if (reference.documentedParts.isNotEmpty()) {
                ReferenceText("Documented parts · ${reference.documentedParts.joinToString()}")
            } else if (reference.hasDocumentedFoodUse) {
                ReferenceText("Available sources don’t specify parts or preparation.")
            }
            reference.foodUseNotes?.let { ReferenceText(it) }
            if (reference.toxicity == ToxicityStatus.Unknown) {
                ReferenceText("Toxicity not assessed by available sources")
            }
        }

        Text(
            Disclaimer,
            style = MaterialTheme.typography.bodySmall,
            color = InkMuted,
            modifier = Modifier.padding(top = 2.dp),
        )
        if (reference != null && reference.sources.isNotEmpty()) {
            FoodUseSources(reference)
        }
    }
}

@Composable
private fun FoodUseSources(reference: EdibilityReference) {
    var expanded by rememberSaveable(reference.taxonId, reference.datasetVersion) { mutableStateOf(false) }
    val rotation by animateFloatAsState(if (expanded) 180f else 0f, label = "Source disclosure")
    val uriHandler = LocalUriHandler.current

    HorizontalDivider(color = Line)
    Row(
        Modifier.fillMaxWidth()
            .clickable(
                role = Role.Button,
                onClickLabel = if (expanded) "Hide source details" else "Show source details",
            ) { expanded = !expanded }
            .semantics { stateDescription = if (expanded) "Expanded" else "Collapsed" }
            .heightIn(min = 48.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            "Sources & attribution",
            style = MaterialTheme.typography.labelLarge,
            color = Moss,
            modifier = Modifier.weight(1f),
        )
        Icon(
            Icons.Rounded.ExpandMore,
            contentDescription = null,
            tint = Moss,
            modifier = Modifier.size(22.dp).rotate(rotation),
        )
    }
    AnimatedVisibility(
        visible = expanded,
        enter = expandVertically() + fadeIn(),
        exit = shrinkVertically() + fadeOut(),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
}

@Composable
internal fun FoodUseIndicatorLabel(
    indicator: FoodUseIndicator,
    color: Color,
    speciesName: String? = null,
    label: String = indicator.label,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(indicator.symbol, contentDescription = null, modifier = Modifier.size(20.dp), tint = color)
        Text(
            if (speciesName.isNullOrBlank()) label else "$speciesName · $label",
            style = MaterialTheme.typography.bodyMedium,
            color = color,
            fontWeight = FontWeight.Medium,
        )
    }
}

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
