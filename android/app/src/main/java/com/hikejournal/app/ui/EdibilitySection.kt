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
import androidx.compose.foundation.layout.PaddingValues
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
import com.hikejournal.app.data.FoodUseSource
import com.hikejournal.app.data.FoodUseStatus
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.PlantPartEvidence
import com.hikejournal.app.data.PlantPartEvidenceKind
import com.hikejournal.app.data.ToxicityStatus
import com.hikejournal.app.data.foodUseTags
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.TrailText

internal const val EdibilitySectionTitle = "Edibility & uses"

@Composable
internal fun FoodUseIndicator.fieldGuideColor(): Color = when (this) {
    FoodUseIndicator.Toxicity, FoodUseIndicator.ToxicParts, FoodUseIndicator.NotEdible -> MaterialTheme.colorScheme.error
    FoodUseIndicator.Edible, FoodUseIndicator.FoodUses -> Moss
    else -> TrailText
}

private val FoodUseIndicator.symbol
    get() = if (warning && this != FoodUseIndicator.Conditional) Icons.Rounded.WarningAmber
    else Icons.AutoMirrored.Rounded.MenuBook

@Composable
internal fun EdibilitySection(
    reference: EdibilityReference?,
    modifier: Modifier = Modifier,
    taxonRank: String? = null,
    referencesByTaxon: List<EdibilityReference> = emptyList(),
    expired: Boolean = false,
) {
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            EdibilitySectionTitle,
            style = MaterialTheme.typography.labelMedium,
            color = TrailText,
            modifier = Modifier.semantics { heading() },
        )
        when {
            referencesByTaxon.isNotEmpty() -> {
                ReferenceText("Your sightings include more than one identification. Here’s what we know about each.")
                referencesByTaxon.forEach { scoped ->
                    Text(
                        scoped.scientificName,
                        style = MaterialTheme.typography.titleMedium,
                        color = Ink,
                        modifier = Modifier.padding(top = 8.dp).semantics { heading() },
                    )
                    EdibilityEvidence(scoped)
                    FoodUseSources(scoped)
                }
            }
            reference != null -> {
                EdibilityEvidence(reference)
                FoodUseSources(reference)
            }
            expired -> {
                EvidenceHeading("Reference needs a refresh")
                ReferenceText("Refresh this page online to see the latest evidence.")
            }
            taxonRank in AboveSpeciesRanks -> {
                EvidenceHeading("Species ID needed")
                ReferenceText("This sighting names a group. Food use can vary from one species to another.")
            }
            else -> {
                EvidenceHeading("Edibility unknown")
                ReferenceText("We don’t have an edibility reference for this species yet.")
            }
        }
    }
}

@Composable
private fun EdibilityEvidence(reference: EdibilityReference) {
    val scoped = reference.partEvidence
    val hasScopedHazard = scoped.any { it.kind == PlantPartEvidenceKind.Toxic || it.kind == PlantPartEvidenceKind.Caution }
    val hasUnscopedHazard = reference.toxicity == ToxicityStatus.DocumentedConcern && !reference.checklistPoisonUse
    scoped.sortedBy { it.kind.displayOrder }.forEach { PartEvidenceRow(it) }
    if (hasUnscopedHazard && !hasScopedHazard) {
        EvidenceHeading("Toxicity reported", TrailText)
        reference.toxicityNotes?.let { ReferenceText(it) }
    }
    when {
        reference.evidenceConflict || reference.foodUse == FoodUseStatus.Disputed ->
            ReferenceText("Sources disagree about food use.")
        reference.hasDocumentedFoodUse && scoped.none { it.kind.isFood } -> {
            if (reference.documentedParts.isEmpty() && (scoped.isNotEmpty() || hasUnscopedHazard)) {
                ReferenceText("A checklist mentions food use, but gives no edible part or conditions.")
            } else {
                EvidenceHeading(
                    if (reference.foodUse == FoodUseStatus.Conditional) "Edible with conditions" else "Used as food",
                    Moss,
                )
                ReferenceText(if (reference.documentedParts.isEmpty()) {
                    "People have used this species as food. The source doesn’t say which parts or how."
                } else {
                    "Parts used as food · ${reference.documentedParts.joinToString()}"
                })
            }
            reference.foodUseNotes?.let { ReferenceText(it) }
        }
        scoped.isEmpty() && reference.indicator == null -> {
            EvidenceHeading("Edibility unknown")
            ReferenceText(if (reference.crossReferences.isNotEmpty()) {
                "Sources & notes has reference records for this species."
            } else {
                "We don’t have a food-use record for this species yet."
            })
        }
    }
    if (reference.traditionalUses.isNotEmpty()) {
        HorizontalDivider(color = Line)
        EvidenceHeading("Traditional uses")
        reference.traditionalUses.forEach { use ->
            Column {
                ReferenceText(use.note)
                EvidenceSourceLink(use.source)
            }
        }
    }
}

@Composable
private fun EvidenceHeading(label: String, color: Color = Ink) {
    Text(label, style = MaterialTheme.typography.titleMedium, color = color,
        modifier = Modifier.semantics { heading() })
}

private val AboveSpeciesRanks = setOf(
    "genus", "subgenus", "section", "subsection", "complex", "tribe", "subfamily",
    "family", "superfamily", "order", "class", "phylum", "kingdom",
)

private val PlantPartEvidenceKind.isFood: Boolean
    get() = this == PlantPartEvidenceKind.Edible || this == PlantPartEvidenceKind.Conditional

private val PlantPartEvidenceKind.displayOrder: Int
    get() = when (this) {
        PlantPartEvidenceKind.Toxic -> 0
        PlantPartEvidenceKind.NotEdible -> 1
        PlantPartEvidenceKind.Caution -> 2
        PlantPartEvidenceKind.Conditional -> 3
        PlantPartEvidenceKind.Edible -> 4
    }

@Composable
private fun PartEvidenceRow(evidence: PlantPartEvidence) {
    val (status, color) = when (evidence.kind) {
        PlantPartEvidenceKind.Edible -> "Edible" to Moss
        PlantPartEvidenceKind.Conditional -> "Edible with conditions" to TrailText
        PlantPartEvidenceKind.NotEdible -> "Not edible" to MaterialTheme.colorScheme.error
        PlantPartEvidenceKind.Toxic -> "Toxic" to MaterialTheme.colorScheme.error
        PlantPartEvidenceKind.Caution -> "Caution" to TrailText
    }
    Column(Modifier.fillMaxWidth()) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(
                if (evidence.kind.isFood) Icons.AutoMirrored.Rounded.MenuBook
                else Icons.Rounded.WarningAmber,
                contentDescription = null,
                modifier = Modifier.size(20.dp),
                tint = color,
            )
            Text(
                "${evidence.part} · $status",
                style = MaterialTheme.typography.titleMedium,
                color = color,
                modifier = Modifier.semantics { heading() },
            )
        }
        evidence.note?.let { ReferenceText(it) }
        EvidenceSourceLink(evidence.source)
    }
}

@Composable
private fun EvidenceSourceLink(source: FoodUseSource) {
    val uriHandler = LocalUriHandler.current
    TextButton(onClick = { uriHandler.openUri(source.url) }, contentPadding = PaddingValues(0.dp)) {
        Text(source.publisher.ifBlank { source.title }, style = MaterialTheme.typography.labelMedium)
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
            "Sources & notes",
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
            if (reference.checklistPoisonUse) {
                ReferenceText("The checklist records a use as a poison. It doesn’t specify the plant part or how it was used.")
            }
            reference.sources.forEach { source ->
                TextButton(onClick = { uriHandler.openUri(source.url) }) {
                    val version = if (source.version.all(Char::isDigit)) "Version ${source.version}" else source.version
                    Text("${source.title} · $version", color = Moss)
                }
                ReferenceText(listOf(source.attribution, source.publisher).filter(String::isNotBlank).distinct().joinToString(" · "))
                reference.crossReferences.filter { it.source == source }.forEach { record ->
                    ReferenceText(record.summary)
                    record.locator?.let { ReferenceText(it) }
                }
                if (source.licenseUrl != null) {
                    TextButton(onClick = { uriHandler.openUri(source.licenseUrl) }) {
                        Text(source.license, color = Moss)
                    }
                } else {
                    ReferenceText(source.license)
                }
                if (source.modifications.isNotBlank()) ReferenceText(source.modifications)
                reference.traditionalUses.filter { it.source == source }.mapNotNull { it.citation }.distinct()
                    .forEach { ReferenceText(it) }
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
                    label = reference.indicatorLabel ?: indicator.label,
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
            title = { Text(tag.commonName.ifBlank { tag.scientificName }, color = Ink) },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    if (tag.commonName.isNotBlank() && tag.commonName != tag.scientificName) {
                        Text(tag.scientificName, style = MaterialTheme.typography.bodyMedium, color = InkMuted)
                    }
                    EdibilitySection(reference, Modifier.padding(top = 12.dp))
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
