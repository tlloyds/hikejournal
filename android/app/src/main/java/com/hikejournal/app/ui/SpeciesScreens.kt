@file:OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)

package com.hikejournal.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.CloudOff
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.hikejournal.app.data.Encounter
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.TrailText
import com.hikejournal.app.ui.theme.FernText
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
fun SpeciesIndexScreen(
    species: List<SpeciesRecord>,
    hikes: List<Hike>,
    loading: Boolean,
    offline: Boolean,
    onRefresh: () -> Unit,
    onOpenSpecies: (String) -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var mostSeenFirst by remember { mutableStateOf(false) }
    var selectedHikeId by remember { mutableStateOf<String?>(null) }
    var filterOpen by remember { mutableStateOf(false) }
    val scopedSpecies = species.mapNotNull { record ->
        if (selectedHikeId == null) {
            record
        } else {
            record.hikeEncounterCounts[selectedHikeId]?.let { encounterCount ->
                record.copy(
                    encounterCount = encounterCount,
                    hikeCount = 1,
                    coverUrl = record.hikeCoverUrls[selectedHikeId] ?: record.coverUrl,
                )
            }
        }
    }
    val filtered = scopedSpecies
        .filter {
            query.isBlank() || it.commonName.contains(query, ignoreCase = true) ||
                it.scientificName.contains(query, ignoreCase = true)
        }
        .let { items ->
            if (mostSeenFirst) items.sortedByDescending { it.encounterCount }
            else items.sortedBy { it.commonName.lowercase(Locale.US) }
        }
    val encounterCount = scopedSpecies.sumOf { it.encounterCount }

    Box(Modifier.fillMaxSize().background(Parchment)) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 104.dp),
        ) {
        item {
            Column(
                Modifier.fillMaxWidth().background(Moss).statusBarsPadding().padding(start = 20.dp, end = 8.dp, top = 17.dp, bottom = 22.dp),
            ) {
                Row(verticalAlignment = Alignment.Top) {
                    Column(Modifier.weight(1f)) {
                        Text("HikeJournal", style = MaterialTheme.typography.headlineSmall, color = Color(0xFFB7C8B5))
                        Text("Field guide", style = MaterialTheme.typography.displayMedium, color = Paper)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("${scopedSpecies.size} SPECIES · $encounterCount ENCOUNTERS", style = MaterialTheme.typography.labelSmall, color = Color(0xFFB7C8B5))
                            if (offline) {
                                Spacer(Modifier.width(9.dp))
                                Icon(Icons.Rounded.CloudOff, null, tint = Trail, modifier = Modifier.size(15.dp))
                            }
                        }
                    }
                    IconButton(onClick = onRefresh, enabled = !loading) {
                        if (loading) CircularProgressIndicator(Modifier.size(20.dp), color = Paper, strokeWidth = 2.dp)
                        else Icon(Icons.Rounded.Refresh, "Refresh species", tint = Paper)
                    }
                }
            }
        }
        item {
            HikeFilterControl(
                hikes = hikes,
                selectedHikeId = selectedHikeId,
                onClick = { filterOpen = true },
            )
        }
        item {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 15.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Rounded.Search, null, tint = InkMuted, modifier = Modifier.size(21.dp))
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.weight(1f).padding(start = 6.dp),
                    placeholder = { Text("Search common or scientific name") },
                    singleLine = true,
                    shape = RoundedCornerShape(4.dp),
                )
            }
        }
        item {
            Row(
                Modifier.fillMaxWidth().padding(start = 20.dp, end = 12.dp, bottom = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("SPECIES INDEX", style = MaterialTheme.typography.labelSmall, color = TrailText)
                TextButton(onClick = { mostSeenFirst = !mostSeenFirst }) {
                    Text(if (mostSeenFirst) "Alphabetical" else "Most encountered")
                }
            }
        }
        if (loading && species.isEmpty()) {
            item {
                Column(Modifier.fillMaxWidth().padding(vertical = 90.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator(color = Moss, strokeWidth = 2.dp)
                    Text("Pressing the field guide…", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 14.dp))
                }
            }
        } else if (filtered.isEmpty()) {
            item {
                Column(Modifier.fillMaxWidth().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        if (selectedHikeId != null && query.isBlank()) "No confirmed species" else "No species match",
                        style = MaterialTheme.typography.headlineMedium,
                        color = Ink,
                    )
                    Text(
                        if (selectedHikeId != null && query.isBlank()) "This outing has no confirmed encounters yet." else "Try a common or scientific name.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = InkMuted,
                    )
                }
            }
        } else {
            items(filtered, key = { it.key }) { record ->
                SpeciesIndexRow(record, onOpenSpecies)
            }
        }
        }
    }

    if (filterOpen) {
        HikeFilterSheet(
            hikes = hikes,
            selectedHikeId = selectedHikeId,
            onSelect = {
                selectedHikeId = it
                filterOpen = false
            },
            onDismiss = { filterOpen = false },
        )
    }
}

@Composable
private fun SpeciesIndexRow(record: SpeciesRecord, onOpen: (String) -> Unit) {
    Column(Modifier.fillMaxWidth().clickable { onOpen(record.key) }) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 13.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(Modifier.size(92.dp).background(Moss)) {
                AsyncImage(
                    model = ImageRequest.Builder(LocalContext.current).data(record.coverUrl).crossfade(true).build(),
                    contentDescription = record.commonName,
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.Crop,
                )
            }
            Column(Modifier.weight(1f).padding(start = 15.dp)) {
                Text(record.commonName, style = MaterialTheme.typography.titleLarge, color = Ink, maxLines = 2, overflow = TextOverflow.Ellipsis)
                if (record.scientificName.isNotBlank()) {
                    Text(
                        record.scientificName,
                        style = MaterialTheme.typography.bodyMedium.copy(fontStyle = FontStyle.Italic),
                        color = InkMuted,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Text(
                    "${record.encounterCount} encounter${if (record.encounterCount == 1) "" else "s"} · ${record.hikeCount} outing${if (record.hikeCount == 1) "" else "s"}",
                    style = MaterialTheme.typography.labelMedium,
                    color = TrailText,
                    modifier = Modifier.padding(top = 5.dp),
                )
            }
            Text(record.encounterCount.toString().padStart(2, '0'), style = MaterialTheme.typography.headlineSmall, color = FernText)
        }
        HorizontalDivider(color = Line, modifier = Modifier.padding(start = 127.dp))
    }
}

@Composable
fun SpeciesDetailScreen(
    species: SpeciesRecord,
    loading: Boolean,
    onBack: () -> Unit,
    onOpenHike: (String) -> Unit,
) {
    LazyColumn(
        Modifier.fillMaxSize().background(Parchment),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 54.dp),
    ) {
        item { SpeciesHero(species, onBack) }
        item {
            Column(Modifier.padding(horizontal = 20.dp, vertical = 24.dp)) {
                Text("PERSONAL FIELD GUIDE", style = MaterialTheme.typography.labelSmall, color = TrailText)
                Text(species.commonName, style = MaterialTheme.typography.displayMedium, color = Ink)
                if (species.scientificName.isNotBlank()) {
                    Text(
                        species.scientificName,
                        style = MaterialTheme.typography.titleLarge.copy(fontStyle = FontStyle.Italic),
                        color = InkMuted,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
                Text(
                    "${species.encounterCount} encounter${if (species.encounterCount == 1) "" else "s"} across ${species.hikeCount} outing${if (species.hikeCount == 1) "" else "s"}",
                    style = MaterialTheme.typography.labelMedium,
                    color = TrailText,
                    modifier = Modifier.padding(top = 13.dp),
                )
                if (species.wikipediaSummary.isNotBlank()) {
                    Text(species.wikipediaSummary, style = MaterialTheme.typography.bodyLarge, color = Ink, modifier = Modifier.padding(top = 20.dp))
                } else {
                    Text(
                        "Your confirmed photographs, arranged from the most recent encounter backward.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = InkMuted,
                        modifier = Modifier.padding(top = 20.dp),
                    )
                }
            }
        }
        item {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Bottom,
            ) {
                Column {
                    Text("ENCOUNTER HISTORY", style = MaterialTheme.typography.labelSmall, color = TrailText)
                    Text("Field records", style = MaterialTheme.typography.headlineMedium, color = Ink)
                }
                if (loading) CircularProgressIndicator(Modifier.size(20.dp), color = Moss, strokeWidth = 2.dp)
            }
        }
        items(species.encounters, key = { it.photo.id }) { encounter ->
            EncounterRow(encounter, onOpenHike)
        }
    }
}

@Composable
private fun SpeciesHero(species: SpeciesRecord, onBack: () -> Unit) {
    Box(Modifier.fillMaxWidth().height(390.dp).background(Moss)) {
        AsyncImage(species.coverUrl, species.commonName, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        Box(
            Modifier.fillMaxSize().background(
                Brush.verticalGradient(listOf(Color(0x88000000), Color.Transparent, Color(0x99101B15))),
            ),
        )
        FilledIconButton(
            onClick = onBack,
            modifier = Modifier.statusBarsPadding().padding(10.dp),
            colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(containerColor = Color(0x99172820)),
        ) {
            Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back", tint = Paper)
        }
        Column(Modifier.align(Alignment.BottomStart).padding(20.dp)) {
            Text("HikeJournal", style = MaterialTheme.typography.headlineSmall, color = Color(0xFFD7DFD2))
            Text(species.commonName, style = MaterialTheme.typography.headlineLarge, color = Paper, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun EncounterRow(encounter: Encounter, onOpenHike: (String) -> Unit) {
    val clickable = encounter.hikeId != null
    Column(
        Modifier.fillMaxWidth().clickable(enabled = clickable) { encounter.hikeId?.let(onOpenHike) },
    ) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 13.dp), verticalAlignment = Alignment.CenterVertically) {
            AsyncImage(
                encounter.photo.url,
                encounter.photo.caption.ifBlank { encounter.hikeTitle },
                Modifier.width(136.dp).height(104.dp).background(Moss),
                contentScale = ContentScale.Crop,
            )
            Column(Modifier.weight(1f).padding(start = 15.dp)) {
                Text(formatSpeciesDate(encounter.observedOn).uppercase(Locale.US), style = MaterialTheme.typography.labelSmall, color = TrailText)
                Text(encounter.hikeTitle, style = MaterialTheme.typography.titleMedium, color = Ink, maxLines = 2, overflow = TextOverflow.Ellipsis)
                if (encounter.locationName.isNotBlank()) {
                    Text(encounter.locationName, style = MaterialTheme.typography.bodyMedium, color = InkMuted, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                if (encounter.photo.caption.isNotBlank()) {
                    Text(encounter.photo.caption, style = MaterialTheme.typography.bodyMedium, color = InkMuted, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
        }
        HorizontalDivider(color = Line, modifier = Modifier.padding(start = 171.dp))
    }
}

private fun formatSpeciesDate(raw: String?): String {
    if (raw.isNullOrBlank()) return "Field record"
    return try {
        LocalDate.parse(raw.take(10)).format(DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US))
    } catch (_: Exception) {
        raw.take(10)
    }
}
