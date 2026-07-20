@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.hikejournal.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.KeyboardArrowDown
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.hikejournal.app.data.Hike
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.Trail
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
fun HikeFilterControl(
    hikes: List<Hike>,
    selectedHikeId: String?,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val selectedHike = hikes.firstOrNull { it.id == selectedHikeId }
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(Parchment)
            .clickable(onClick = onClick)
            .padding(horizontal = 20.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Rounded.Tune, null, tint = Trail, modifier = Modifier.size(20.dp))
        Column(Modifier.weight(1f).padding(start = 12.dp)) {
            Text("FILTER BY OUTING", style = MaterialTheme.typography.labelSmall, color = Trail)
            Text(
                selectedHike?.title ?: "All hikes",
                style = MaterialTheme.typography.titleMedium,
                color = Ink,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Text(
            if (selectedHike == null) "${hikes.size}" else formatFilterDate(selectedHike.hikeDate),
            style = MaterialTheme.typography.labelMedium,
            color = InkMuted,
        )
        Spacer(Modifier.width(4.dp))
        Icon(Icons.Rounded.KeyboardArrowDown, "Choose a hike", tint = Moss)
    }
    HorizontalDivider(color = Line)
}

@Composable
fun HikeFilterSheet(
    hikes: List<Hike>,
    selectedHikeId: String?,
    onSelect: (String?) -> Unit,
    onDismiss: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    val filtered = remember(hikes, query) {
        hikes
            .filter {
                query.isBlank() ||
                    it.title.contains(query, ignoreCase = true) ||
                    it.locationName.contains(query, ignoreCase = true) ||
                    it.hikeDate.contains(query, ignoreCase = true)
            }
            .sortedWith(compareByDescending<Hike> { it.hikeDate }.thenBy { it.title.lowercase(Locale.US) })
    }

    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Paper) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding()) {
            Column(Modifier.padding(horizontal = 20.dp)) {
                Text("OUTING SCOPE", style = MaterialTheme.typography.labelSmall, color = Trail)
                Text("Choose a hike", style = MaterialTheme.typography.headlineLarge, color = Ink)
                Text(
                    "Species and publishing records will stay within this outing.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 4.dp),
                )
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
                    placeholder = { Text("Search title, place, or date") },
                    leadingIcon = { Icon(Icons.Rounded.Search, null) },
                    singleLine = true,
                )
            }
            LazyColumn(Modifier.fillMaxWidth().heightIn(max = 450.dp).padding(top = 10.dp)) {
                item(key = "all-hikes") {
                    HikeFilterRow(
                        title = "All hikes",
                        detail = "Every available field record",
                        selected = selectedHikeId == null,
                        onClick = { onSelect(null) },
                    )
                }
                items(filtered, key = { it.id }) { hike ->
                    HikeFilterRow(
                        title = hike.title,
                        detail = listOf(formatFilterDate(hike.hikeDate), hike.locationName)
                            .filter { it.isNotBlank() }
                            .joinToString(" · "),
                        selected = selectedHikeId == hike.id,
                        onClick = { onSelect(hike.id) },
                    )
                }
                if (filtered.isEmpty()) {
                    item {
                        Text(
                            "No outings match that search.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = InkMuted,
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 28.dp),
                        )
                    }
                }
                item { Spacer(Modifier.height(14.dp)) }
            }
        }
    }
}

@Composable
private fun HikeFilterRow(
    title: String,
    detail: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 20.dp, vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = Ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(detail, style = MaterialTheme.typography.bodyMedium, color = InkMuted, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        AnimatedVisibility(visible = selected, enter = fadeIn(), exit = fadeOut()) {
            Icon(Icons.Rounded.Check, "Selected", tint = Moss, modifier = Modifier.size(22.dp))
        }
    }
    HorizontalDivider(color = Line, modifier = Modifier.padding(start = 20.dp))
}

private fun formatFilterDate(raw: String): String = runCatching {
    LocalDate.parse(raw.take(10)).format(DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US))
}.getOrDefault(raw)
