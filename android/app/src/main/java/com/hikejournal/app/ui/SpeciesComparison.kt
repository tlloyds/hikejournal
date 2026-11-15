package com.hikejournal.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Close
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextAlign
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

@Composable
internal fun SpeciesComparisonDialog(
    first: SpeciesRecord,
    second: SpeciesRecord,
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
            LazyColumn(
                Modifier.align(Alignment.CenterHorizontally).widthIn(max = 760.dp).fillMaxWidth(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item {
                    ComparisonPair { modifier ->
                        ComparisonPhoto(first, modifier)
                        ComparisonPhoto(second, modifier)
                    }
                }
                item {
                    ComparisonPair { modifier ->
                        Text(first.commonName, modifier, style = MaterialTheme.typography.titleLarge, color = Ink)
                        Text(second.commonName, modifier, style = MaterialTheme.typography.titleLarge, color = Ink)
                    }
                }
                item {
                    ComparisonPair { modifier ->
                        val style = MaterialTheme.typography.bodyMedium.copy(fontStyle = FontStyle.Italic)
                        Text(first.scientificName.ifBlank { "Scientific name unavailable" }, modifier, style = style, color = InkMuted)
                        Text(second.scientificName.ifBlank { "Scientific name unavailable" }, modifier, style = style, color = InkMuted)
                    }
                }
                item {
                    ComparisonFacts("Local status", first.ecology.displayLabel, second.ecology.displayLabel)
                }
                item {
                    ComparisonFacts("Encounters in your collection", first.encounterCount.toString(), second.encounterCount.toString())
                }
                if (first.wikipediaSummary.isNotBlank() || second.wikipediaSummary.isNotBlank()) {
                    item {
                        ComparisonFacts(
                            "Wikipedia descriptions",
                            first.wikipediaSummary.ifBlank { "No description available" },
                            second.wikipediaSummary.ifBlank { "No description available" },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ComparisonPair(content: @Composable (Modifier) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        content(Modifier.weight(1f))
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
        contentDescription = "Cover photo of ${record.commonName}",
        modifier = modifier.aspectRatio(1f).background(Paper),
        contentScale = ContentScale.Fit,
        onError = {
            if (record.coverThumbnailUrl.isNotBlank() && record.coverThumbnailUrl != url) {
                useThumbnail = true
            }
        },
        error = {
            Box(Modifier.fillMaxSize().padding(8.dp), contentAlignment = Alignment.Center) {
                Text(
                    "Photo unavailable",
                    style = MaterialTheme.typography.bodySmall,
                    color = InkMuted,
                    textAlign = TextAlign.Center,
                )
            }
        },
    )
}

@Composable
private fun ComparisonFacts(label: String, first: String, second: String) {
    HorizontalDivider(color = Line)
    Text(
        label,
        Modifier.padding(top = 10.dp, bottom = 6.dp),
        style = MaterialTheme.typography.labelLarge,
        color = TrailText,
    )
    ComparisonPair { modifier ->
        Text(first, modifier, style = MaterialTheme.typography.bodyMedium, color = Ink)
        Text(second, modifier, style = MaterialTheme.typography.bodyMedium, color = Ink)
    }
}
