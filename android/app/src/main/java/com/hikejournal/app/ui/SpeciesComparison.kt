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
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
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
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.SubcomposeAsyncImage
import coil.request.ImageRequest
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.data.isVideo
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.TrailText
import kotlinx.coroutines.CancellationException

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
    loadSpecies: suspend (String, Boolean) -> SpeciesRecord,
    onBack: () -> Unit,
) {
    Dialog(
        onDismissRequest = onBack,
        properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false),
    ) {
        val firstGallery = rememberComparisonGallery(first, loadSpecies)
        val secondGallery = rememberComparisonGallery(second, loadSpecies)
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
                        ComparisonPhotoGallery(first, firstGallery, left)
                        ComparisonPhotoGallery(second, secondGallery, right)
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

private data class ComparisonImage(val url: String, val thumbnailUrl: String)

private data class ComparisonGallery(
    val photos: List<ComparisonImage>,
    val loading: Boolean = false,
    val retry: (() -> Unit)? = null,
)

private fun SpeciesRecord.comparisonImages(): List<ComparisonImage> {
    if (encounters.isEmpty()) {
        return listOfNotNull(ComparisonImage(coverUrl, coverThumbnailUrl).takeIf {
            it.url.isNotBlank() || it.thumbnailUrl.isNotBlank()
        })
    }
    return encounters.map { it.photo }
        .filter { !it.isVideo && (it.url.isNotBlank() || it.thumbnailUrl.isNotBlank()) }
        .distinctBy { it.id }
        .map { ComparisonImage(it.url, it.thumbnailUrl) }
}

@Composable
private fun rememberComparisonGallery(
    record: SpeciesRecord,
    loadSpecies: suspend (String, Boolean) -> SpeciesRecord,
): ComparisonGallery {
    val preview = remember(record) { record.comparisonImages() }
    var attempt by remember(record.key) { mutableIntStateOf(0) }
    val gallery by produceState(ComparisonGallery(preview, loading = true), record.key, attempt) {
        value = ComparisonGallery(preview, loading = true)
        try {
            val detail = loadSpecies(record.key, attempt > 0)
            value = ComparisonGallery(detail.comparisonImages())
        } catch (error: CancellationException) {
            throw error
        } catch (_: Exception) {
            value = ComparisonGallery(preview, retry = { attempt++ })
        }
    }
    return gallery
}

@Composable
private fun ComparisonPhotoGallery(record: SpeciesRecord, gallery: ComparisonGallery, modifier: Modifier) {
    val photos = gallery.photos
    val pager = rememberPagerState { photos.size }
    val photoNumber = (pager.currentPage + 1).coerceAtMost(photos.size)
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        val frame = Modifier.fillMaxWidth().aspectRatio(4f / 3f)
        if (photos.isEmpty()) {
            ComparisonPhoto(null, record.commonName, frame)
        } else {
            HorizontalPager(
                state = pager,
                modifier = frame.semantics {
                    contentDescription = "Photos of ${record.commonName}"
                    stateDescription = "Photo $photoNumber of ${photos.size}"
                },
                userScrollEnabled = photos.size > 1,
            ) { index ->
                ComparisonPhoto(photos[index], record.commonName, Modifier.fillMaxSize())
            }
        }
        val retry = gallery.retry
        when {
            retry != null -> {
                TextButton(onClick = retry, modifier = Modifier.semantics {
                    contentDescription = "Retry photos of ${record.commonName}"
                }) { Text("Retry photos", style = MaterialTheme.typography.labelSmall) }
            }
            gallery.loading -> {
                Text("Loading photos…", Modifier.padding(top = 6.dp), style = MaterialTheme.typography.labelSmall, color = InkMuted)
            }
            photos.size > 1 -> {
                Text("$photoNumber / ${photos.size}", Modifier.padding(top = 6.dp), style = MaterialTheme.typography.labelSmall, color = InkMuted)
            }
        }
    }
}

@Composable
private fun ComparisonPhoto(photo: ComparisonImage?, speciesName: String, modifier: Modifier) {
    var useThumbnail by remember(photo) { mutableStateOf(photo?.url.isNullOrBlank()) }
    val url = if (useThumbnail) photo?.thumbnailUrl else photo?.url
    SubcomposeAsyncImage(
        model = ImageRequest.Builder(LocalContext.current)
            .data(url?.takeIf { it.isNotBlank() })
            .crossfade(true)
            .build(),
        contentDescription = "Field photo of $speciesName",
        modifier = modifier.background(MaterialTheme.colorScheme.surfaceVariant),
        contentScale = ContentScale.Fit,
        onError = {
            if (photo != null && photo.thumbnailUrl.isNotBlank() && photo.thumbnailUrl != url) {
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
        Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 5.dp)
            .semantics { heading() },
        style = MaterialTheme.typography.labelMedium,
        color = TrailText,
        textAlign = TextAlign.Center,
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
    Box(
        Modifier.fillMaxWidth()
            .clickable(role = Role.Button) { expanded = !expanded }
            .semantics { stateDescription = if (expanded) "Expanded" else "Collapsed" }
            .heightIn(min = 48.dp).padding(horizontal = 16.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            "Wikipedia descriptions",
            Modifier.fillMaxWidth().padding(horizontal = 32.dp),
            style = MaterialTheme.typography.labelLarge,
            color = Moss,
            textAlign = TextAlign.Center,
        )
        Icon(Icons.Rounded.ExpandMore, null, Modifier.align(Alignment.CenterEnd).rotate(rotation), tint = Moss)
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
