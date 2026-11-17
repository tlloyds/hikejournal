package com.hikejournal.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyItemScope
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.ExpandMore
import androidx.compose.material.icons.rounded.Image
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.SubcomposeAsyncImage
import coil.request.ImageRequest
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.TrailText

@Composable
internal fun SpeciesComparisonControls(
    selected: List<SpeciesRecord>,
    onRemove: (String) -> Unit,
    onCancel: () -> Unit,
    onCompare: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxWidth().background(Paper)) {
        HorizontalDivider(color = Line)
        Row(
            Modifier.fillMaxWidth().padding(start = 16.dp, end = 12.dp, top = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            for (record in selected) {
                Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        record.commonName,
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.titleSmall,
                        color = Ink,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    IconButton(onClick = { onRemove(record.key) }) {
                        Icon(Icons.Rounded.Close, "Remove ${record.commonName}", tint = InkMuted)
                    }
                }
            }
            if (selected.size < 2) {
                Text(
                    if (selected.isEmpty()) "Select two species" else "Select another species",
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                )
            }
        }
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onCancel) { Text("Cancel") }
            Button(onClick = onCompare, enabled = selected.size == 2) { Text("Compare species") }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
internal fun SpeciesComparisonDialog(
    first: SpeciesRecord,
    second: SpeciesRecord,
    edibilityDataset: String?,
    onBack: () -> Unit,
) {
    Dialog(
        onDismissRequest = onBack,
        properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false),
    ) {
        Column(Modifier.fillMaxSize().background(Parchment).navigationBarsPadding()) {
            PatternedForestSurface(Modifier.fillMaxWidth()) {
                Row(
                    Modifier.fillMaxWidth().statusBarsPadding().padding(end = 16.dp, top = 4.dp, bottom = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back to species selection", tint = Paper)
                    }
                    Text("Compare species", style = MaterialTheme.typography.titleLarge, color = Paper)
                }
            }
            val pinNames = LocalConfiguration.current.screenHeightDp >= 480 && LocalDensity.current.fontScale <= 1.5f
            val names: @Composable LazyItemScope.() -> Unit = { ComparisonNames(first, second) }
            LazyColumn(
                Modifier.align(Alignment.CenterHorizontally).widthIn(max = 640.dp).fillMaxWidth(),
                contentPadding = PaddingValues(bottom = 24.dp),
            ) {
                item(key = "photos") {
                    ComparisonPair(Modifier.padding(top = 16.dp)) { left, right ->
                        ComparisonPhoto(first, left)
                        ComparisonPhoto(second, right)
                    }
                }
                if (pinNames) stickyHeader(key = "species") { names() }
                else item(key = "species", content = names)
                item(key = "local-status") {
                    ComparisonFacts("Local status") { left, right ->
                        ComparisonValue(first.ecology.displayLabel, left, ecologyStatusColor(first.ecology.label))
                        ComparisonValue(second.ecology.displayLabel, right, ecologyStatusColor(second.ecology.label))
                    }
                }
                if (first.hasPlantReferenceSection(edibilityDataset) || second.hasPlantReferenceSection(edibilityDataset)) {
                    item(key = "plant-evidence") {
                        ComparisonFacts("Edibility & safety") { left, right ->
                            ComparisonEdibility(first, edibilityDataset, left)
                            ComparisonEdibility(second, edibilityDataset, right)
                        }
                    }
                }
                item(key = "encounters") {
                    ComparisonFacts("Journal encounters") { left, right ->
                        ComparisonValue(first.encounterCount.toString(), left)
                        ComparisonValue(second.encounterCount.toString(), right)
                    }
                }
                if (first.wikipediaSummary.isNotBlank() || second.wikipediaSummary.isNotBlank()) {
                    item(key = "descriptions") {
                        ComparisonDescriptions(first, second)
                    }
                }
            }
        }
    }
}

@Composable
private fun ComparisonNames(first: SpeciesRecord, second: SpeciesRecord) {
    Column(Modifier.fillMaxWidth().background(Parchment)) {
        ComparisonPair(Modifier.padding(top = 10.dp)) { left, right ->
            ComparisonName(first.commonName, left)
            ComparisonName(second.commonName, right)
        }
        ComparisonPair(Modifier.padding(top = 3.dp, bottom = 12.dp)) { left, right ->
            val style = MaterialTheme.typography.bodySmall.copy(fontStyle = FontStyle.Italic)
            Text(first.scientificName.ifBlank { "Scientific name unavailable" }, left, style = style, color = InkMuted)
            Text(second.scientificName.ifBlank { "Scientific name unavailable" }, right, style = style, color = InkMuted)
        }
        HorizontalDivider(Modifier.padding(horizontal = 16.dp), color = Line)
    }
}

@Composable
private fun ComparisonName(name: String, modifier: Modifier) {
    Text(name, modifier.semantics { heading() }, style = MaterialTheme.typography.headlineSmall, color = Ink)
}

@Composable
private fun ComparisonPair(
    modifier: Modifier = Modifier,
    content: @Composable (Modifier, Modifier) -> Unit,
) {
    Row(
        modifier.fillMaxWidth().padding(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        content(Modifier.weight(1f), Modifier.weight(1f))
    }
}

@Composable
private fun ComparisonPhoto(record: SpeciesRecord, modifier: Modifier) {
    var useThumbnail by remember(record.coverUrl, record.coverThumbnailUrl) {
        mutableStateOf(record.coverUrl.isBlank())
    }
    val url = if (useThumbnail) record.coverThumbnailUrl else record.coverUrl
    SubcomposeAsyncImage(
        model = ImageRequest.Builder(LocalContext.current)
            .data(url.ifBlank { null })
            .crossfade(true)
            .build(),
        contentDescription = "Field photo of ${record.commonName}",
        modifier = modifier.aspectRatio(4f / 3f).background(MaterialTheme.colorScheme.surfaceVariant),
        contentScale = ContentScale.Fit,
        onError = {
            if (record.coverThumbnailUrl.isNotBlank() && record.coverThumbnailUrl != url) {
                useThumbnail = true
            }
        },
        error = {
            Column(
                Modifier.fillMaxSize().padding(8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp, Alignment.CenterVertically),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Icon(Icons.Rounded.Image, contentDescription = null, tint = InkMuted)
                Text("No photo", style = MaterialTheme.typography.bodySmall, color = InkMuted)
            }
        },
    )
}

@Composable
private fun ComparisonFacts(label: String, content: @Composable (Modifier, Modifier) -> Unit) {
    Text(
        label,
        Modifier.padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 5.dp).semantics { heading() },
        style = MaterialTheme.typography.labelMedium,
        color = TrailText,
    )
    ComparisonPair(Modifier.padding(bottom = 12.dp), content)
    HorizontalDivider(Modifier.padding(horizontal = 16.dp), color = Line)
}

@Composable
private fun ComparisonValue(value: String, modifier: Modifier = Modifier, color: Color = Ink) {
    Text(value, modifier, style = MaterialTheme.typography.bodyMedium, color = color)
}

@Composable
private fun ComparisonDescriptions(first: SpeciesRecord, second: SpeciesRecord) {
    var expanded by rememberSaveable(first.key, second.key) { mutableStateOf(false) }
    val rotation by animateFloatAsState(if (expanded) 180f else 0f, label = "Description disclosure")
    Row(
        Modifier.fillMaxWidth()
            .clickable(role = Role.Button) { expanded = !expanded }
            .semantics { stateDescription = if (expanded) "Expanded" else "Collapsed" }
            .heightIn(min = 48.dp).padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("Wikipedia descriptions", Modifier.weight(1f), style = MaterialTheme.typography.labelLarge, color = Moss)
        Icon(Icons.Rounded.ExpandMore, null, Modifier.rotate(rotation), tint = Moss)
    }
    AnimatedVisibility(
        expanded,
        enter = expandVertically() + fadeIn(),
        exit = shrinkVertically() + fadeOut(),
    ) {
        ComparisonPair { left, right ->
            ComparisonValue(first.wikipediaSummary.ifBlank { "No description available" }, left)
            ComparisonValue(second.wikipediaSummary.ifBlank { "No description available" }, right)
        }
    }
}
