@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.hikejournal.app.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Launch
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.CloudUpload
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.SkipNext
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.GROUPED_PUBLISH_MAX_PHOTOS
import com.hikejournal.app.data.PublishBatchStatus
import com.hikejournal.app.data.PublishItem
import com.hikejournal.app.data.PublishObservationGroup
import com.hikejournal.app.data.PublishOptions
import com.hikejournal.app.data.PublishQueue
import com.hikejournal.app.data.buildPublishObservationGroups
import com.hikejournal.app.data.splitPublishObservationGroups
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.Trail
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

private enum class PublishFilter(val state: String, val label: String) {
    Ready("ready", "Ready"),
    Attention("needs_attention", "Attention"),
    Posted("posted", "Posted"),
}

internal const val EVERYDAY_SIGHTINGS_HIKE_ID = "everyday"

/**
 * Standalone uploads predate the synthetic Everyday Sightings journal and do
 * not have a hike ID in cached queue responses. Keep them in that scope while
 * also accepting the explicit ID returned by current companion versions.
 */
internal fun publishItemsForHikeScope(
    items: List<PublishItem>,
    selectedHikeId: String?,
): List<PublishItem> = when (selectedHikeId) {
    null -> items
    EVERYDAY_SIGHTINGS_HIKE_ID -> items.filter {
        it.hikeId.isNullOrBlank() || it.hikeId == EVERYDAY_SIGHTINGS_HIKE_ID
    }
    else -> items.filter { it.hikeId == selectedHikeId }
}

@Composable
fun PublishingScreen(
    queue: PublishQueue,
    hikes: List<Hike>,
    loading: Boolean,
    publishingId: String?,
    batchPublishing: Boolean,
    publishBatchProgress: PublishBatchStatus?,
    notice: String?,
    offline: Boolean,
    onRefresh: () -> Unit,
    onPublish: (PublishItem, PublishOptions) -> Unit,
    onSubmitBatch: (List<List<String>>, PublishOptions) -> Unit,
    onBatchFinished: () -> Unit,
    onConnectInat: () -> Unit,
    onClearNotice: () -> Unit,
) {
    var filter by remember { mutableStateOf(PublishFilter.Ready) }
    var index by remember { mutableIntStateOf(0) }
    var horizontalDragDistance by remember { mutableFloatStateOf(0f) }
    var selectedHikeId by remember { mutableStateOf<String?>(null) }
    var filterOpen by remember { mutableStateOf(false) }
    var batchMode by remember { mutableStateOf(false) }
    val selectedHike = hikes.firstOrNull { it.id == selectedHikeId }
    val scopedItems = remember(queue.items, selectedHikeId) {
        publishItemsForHikeScope(queue.items, selectedHikeId)
    }
    val readyCount = if (selectedHikeId == null) queue.readyCount else scopedItems.count { it.state == PublishFilter.Ready.state }
    val attentionCount = if (selectedHikeId == null) queue.needsAttentionCount else scopedItems.count { it.state == PublishFilter.Attention.state }
    val postedCount = if (selectedHikeId == null) queue.postedCount else scopedItems.count { it.state == PublishFilter.Posted.state }
    val filtered = remember(scopedItems, filter) { scopedItems.filter { it.state == filter.state } }
    val signature = remember(filtered) { filtered.joinToString(",") { it.id } }
    LaunchedEffect(signature) {
        index = if (filtered.isEmpty()) 0 else index.coerceIn(0, filtered.lastIndex)
    }
    val current = filtered.getOrNull(index)
    LaunchedEffect(publishBatchProgress?.jobId, publishBatchProgress?.state, batchPublishing) {
        if (!batchPublishing && publishBatchProgress?.state in setOf("completed", "failed")) {
            onBatchFinished()
            batchMode = false
        }
    }

    Box(Modifier.fillMaxSize().background(Parchment)) {
        Column(Modifier.fillMaxSize()) {
            Column(
                Modifier.fillMaxWidth().background(Moss).statusBarsPadding().padding(start = 20.dp, end = 8.dp, top = 15.dp, bottom = 10.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("HikeJournal", style = MaterialTheme.typography.titleMedium, color = Color(0xFFB7C8B5))
                        Text("Publish", style = MaterialTheme.typography.headlineMedium, color = Paper)
                        Text(
                            "$readyCount READY · $attentionCount ATTENTION · $postedCount POSTED",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFFB7C8B5),
                        )
                    }
                    TextButton(
                        onClick = { batchMode = true },
                        enabled = readyCount > 0 && !offline && !batchPublishing && publishingId == null && queue.connected,
                        colors = ButtonDefaults.textButtonColors(contentColor = Paper),
                    ) {
                        Text("Batch post")
                    }
                    IconButton(onClick = onRefresh, enabled = !loading && publishingId == null && !batchPublishing) {
                        if (loading) CircularProgressIndicator(Modifier.size(20.dp), color = Paper, strokeWidth = 2.dp)
                        else Icon(Icons.Rounded.Refresh, "Refresh publishing queue", tint = Paper)
                    }
                }
                Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    PublishFilter.entries.forEach { option ->
                        val count = when (option) {
                            PublishFilter.Ready -> readyCount
                            PublishFilter.Attention -> attentionCount
                            PublishFilter.Posted -> postedCount
                        }
                        TextButton(
                            onClick = { filter = option; index = 0 },
                            modifier = Modifier.weight(1f).then(
                                if (filter == option) Modifier.background(Trail, RoundedCornerShape(5.dp)) else Modifier,
                            ),
                        ) {
                            Text("${option.label} · $count", color = if (filter == option) Paper else Color(0xFFB7C8B5))
                        }
                    }
                }
            }

            HikeFilterControl(
                hikes = hikes,
                selectedHikeId = selectedHikeId,
                onClick = { filterOpen = true },
            )

            if (offline) {
                Text(
                    "OFFLINE COPY · PUBLISHING PAUSED",
                    style = MaterialTheme.typography.labelSmall,
                    color = Paper,
                    modifier = Modifier.fillMaxWidth().background(Trail).padding(horizontal = 20.dp, vertical = 8.dp),
                )
            }

            when {
                batchMode -> PublishBatchPlanContent(
                    items = scopedItems.filter { it.state == PublishFilter.Ready.state },
                    submitting = batchPublishing,
                    progress = publishBatchProgress,
                    connected = queue.connected,
                    offline = offline,
                    onBack = { if (!batchPublishing) batchMode = false },
                    onSubmit = { groups, options ->
                        onSubmitBatch(groups, options)
                    },
                )
                loading && queue.items.isEmpty() -> PublishLoading()
                current == null -> PublishEmpty(
                    filter = filter,
                    hikeTitle = selectedHike?.title,
                    connected = queue.connected,
                    offline = offline,
                    onConnectInat = onConnectInat,
                    onRefresh = onRefresh,
                )
                else -> Box(
                    Modifier.weight(1f).pointerInput(signature, index) {
                        detectHorizontalDragGestures(
                            onHorizontalDrag = { _, dragAmount -> horizontalDragDistance += dragAmount },
                            onDragEnd = {
                                when {
                                    horizontalDragDistance > 72f && index > 0 -> index -= 1
                                    horizontalDragDistance < -72f && index < filtered.lastIndex -> index += 1
                                }
                                horizontalDragDistance = 0f
                            },
                            onDragCancel = { horizontalDragDistance = 0f },
                        )
                    },
                ) {
                    AnimatedContent(
                        targetState = current.id,
                        transitionSpec = {
                            (fadeIn() + slideInHorizontally { it / 8 }) togetherWith
                                (fadeOut() + slideOutHorizontally { -it / 8 })
                        },
                        label = "publish-record",
                    ) { targetId ->
                        val target = filtered.firstOrNull { it.id == targetId } ?: current
                        val targetPosition = filtered.indexOfFirst { it.id == targetId }
                            .takeIf { it >= 0 }
                            ?.plus(1)
                            ?: index + 1
                        PublishItemContent(
                            item = target,
                            position = targetPosition,
                            total = filtered.size,
                            hasNext = targetPosition < filtered.size,
                            connected = queue.connected,
                            offline = offline,
                            publishing = publishingId == target.id,
                            onNext = { if (index < filtered.lastIndex) index += 1 },
                            onPublish = { options -> onPublish(target, options) },
                            onConnectInat = onConnectInat,
                        )
                    }
                }
            }
        }

        AnimatedVisibility(
            visible = notice != null,
            modifier = Modifier.align(Alignment.BottomCenter).padding(start = 14.dp, end = 14.dp, bottom = 94.dp),
            enter = slideInVertically { it } + fadeIn(),
            exit = slideOutVertically { it } + fadeOut(),
        ) {
            notice?.let {
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(7.dp)).background(Moss).clickable(onClick = onClearNotice).padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Rounded.Check, null, tint = Paper)
                    Text(it, style = MaterialTheme.typography.bodyMedium, color = Paper, modifier = Modifier.padding(start = 10.dp))
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
                index = 0
                filterOpen = false
            },
            onDismiss = { filterOpen = false },
        )
    }
}

@Composable
private fun PublishBatchPlanContent(
    items: List<PublishItem>,
    submitting: Boolean,
    progress: PublishBatchStatus?,
    connected: Boolean,
    offline: Boolean,
    onBack: () -> Unit,
    onSubmit: (List<List<String>>, PublishOptions) -> Unit,
) {
    var selectedIds by remember(items) { mutableStateOf(items.map { it.id }.toSet()) }
    var separatePhotoIds by remember(items) { mutableStateOf(emptySet<String>()) }
    var description by remember(items) { mutableStateOf("") }
    var tags by remember(items) { mutableStateOf("") }
    var geoprivacy by remember(items) { mutableStateOf("open") }
    var captive by remember(items) { mutableStateOf(false) }
    val listState = rememberLazyListState()
    val selectedItems = items.filter { it.id in selectedIds }
    val proposedGroups = buildPublishObservationGroups(selectedItems)
    val displayGroups = proposedGroups.sortedBy { it.items.size == 1 }
    val plannedGroups = splitPublishObservationGroups(proposedGroups, separatePhotoIds)
    val groupedCount = plannedGroups.count { it.items.size > 1 }
    val individualCount = plannedGroups.count { it.items.size == 1 }
    val oversizedGroups = plannedGroups.filter { it.oversized }

    LaunchedEffect(submitting) {
        if (submitting) listState.animateScrollToItem(0)
    }

    LazyColumn(
        state = listState,
        modifier = Modifier.fillMaxSize().padding(bottom = 92.dp),
    ) {
        item {
            Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 20.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = onBack, enabled = !submitting) { Text("Back") }
                    Spacer(Modifier.width(4.dp))
                    Text("Plan grouped posts", style = MaterialTheme.typography.headlineMedium, color = Ink)
                }
                Text(
                    "Select confirmed sightings and HikeJournal will propose groups from the same species and outing within 15 minutes and 50 meters. Split any photo that deserves its own iNaturalist observation.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 5.dp),
                )
                Row(
                    Modifier.fillMaxWidth().padding(top = 14.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    OutlinedButton(
                        onClick = { selectedIds = items.map { it.id }.toSet() },
                        enabled = !submitting && selectedIds.size != items.size,
                        modifier = Modifier.weight(1f),
                    ) { Text("Select ready") }
                    OutlinedButton(
                        onClick = {
                            selectedIds = emptySet()
                            separatePhotoIds = emptySet()
                        },
                        enabled = !submitting && selectedIds.isNotEmpty(),
                        modifier = Modifier.weight(1f),
                    ) { Text("Clear") }
                }
                Text(
                    "${selectedItems.size} selected · ${plannedGroups.size} planned observation${if (plannedGroups.size == 1) "" else "s"} · $groupedCount grouped · $individualCount individual",
                    style = MaterialTheme.typography.labelMedium,
                    color = if (selectedItems.isEmpty()) InkMuted else Moss,
                    modifier = Modifier.padding(top = 15.dp),
                )
                progress?.let { batch ->
                    val total = batch.totalGroups.coerceAtLeast(1)
                    val current = when {
                        batch.state == "completed" -> total
                        batch.currentGroup > 0 -> batch.currentGroup.coerceIn(1, total)
                        else -> 0
                    }
                    val label = when (batch.state) {
                        "queued" -> "Preparing grouped posts…"
                        "running" -> "Posting observation $current of ${batch.totalGroups}…"
                        "completed" -> "Posted ${batch.postedGroupCount} of ${batch.totalGroups} observations"
                        "failed" -> "Stopped after ${batch.processedGroupCount} of ${batch.totalGroups} observations"
                        else -> "Updating posting status…"
                    }
                    Text(
                        label,
                        style = MaterialTheme.typography.labelMedium,
                        color = if (batch.state == "failed") Trail else Moss,
                        modifier = Modifier.padding(top = 14.dp),
                    )
                    LinearProgressIndicator(
                        progress = { current.toFloat() / total.toFloat() },
                        modifier = Modifier.fillMaxWidth().padding(top = 7.dp),
                        color = if (batch.state == "failed") Trail else Moss,
                    )
                    if (batch.state == "running" && batch.currentGroupPhotoCount > 0) {
                        Text(
                            "Uploading ${batch.currentGroupPhotoCount} photo${if (batch.currentGroupPhotoCount == 1) "" else "s"} for this observation",
                            style = MaterialTheme.typography.bodySmall,
                            color = InkMuted,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                    }
                }
            }
        }
        if (displayGroups.isEmpty()) {
            item {
                Text(
                    "Choose at least one confirmed sighting to build the posting plan.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = InkMuted,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 18.dp),
                )
            }
        } else {
            items(displayGroups, key = { group -> group.photoIds.joinToString("|") }) { group ->
                PublishBatchGroupSection(
                    group = group,
                    selectedIds = selectedIds,
                    separatePhotoIds = separatePhotoIds,
                    enabled = !submitting,
                    onSelectedChange = { observationId, selected ->
                        selectedIds = if (selected) selectedIds + observationId else selectedIds - observationId
                        if (!selected) {
                            val photoId = items.firstOrNull { it.id == observationId }?.photo?.id
                            if (photoId != null) separatePhotoIds = separatePhotoIds - photoId
                        }
                    },
                    onSeparateChange = { observationId, separate ->
                        separatePhotoIds = if (separate) separatePhotoIds + observationId else separatePhotoIds - observationId
                    },
                )
            }
        }
        item {
            Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 18.dp)) {
                Text(
                    "The lead photo supplies the date, location, and species. These posting options apply to every planned observation.",
                    style = MaterialTheme.typography.bodySmall,
                    color = InkMuted,
                )
                OutlinedTextField(
                    description,
                    { description = it },
                    Modifier.fillMaxWidth().padding(top = 12.dp),
                    label = { Text("Observation note") },
                    maxLines = 3,
                    enabled = !submitting,
                )
                OutlinedTextField(
                    tags,
                    { tags = it },
                    Modifier.fillMaxWidth().padding(top = 9.dp),
                    label = { Text("Tags · comma separated") },
                    singleLine = true,
                    enabled = !submitting,
                )
                Text("LOCATION SHARING", style = MaterialTheme.typography.labelSmall, color = InkMuted, modifier = Modifier.padding(top = 14.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf("open" to "Exact", "obscured" to "Obscured", "private" to "Private").forEach { option ->
                        FilterChip(
                            selected = geoprivacy == option.first,
                            onClick = { geoprivacy = option.first },
                            label = { Text(option.second, style = MaterialTheme.typography.labelSmall) },
                            modifier = Modifier.weight(1f),
                            enabled = !submitting,
                        )
                    }
                }
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Captive or cultivated", style = MaterialTheme.typography.titleSmall)
                        Text("Mark plants or animals that were not wild.", style = MaterialTheme.typography.bodySmall, color = InkMuted)
                    }
                    Switch(captive, { captive = it }, enabled = !submitting)
                }
                if (oversizedGroups.isNotEmpty()) {
                    Text(
                        "Split ${oversizedGroups.size} oversized group${if (oversizedGroups.size == 1) "" else "s"} to stay within iNaturalist's $GROUPED_PUBLISH_MAX_PHOTOS-photo limit.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Trail,
                        modifier = Modifier.padding(top = 10.dp),
                    )
                }
                Button(
                    onClick = {
                        onSubmit(
                            plannedGroups.map { it.observationIds },
                            PublishOptions(
                                observationIds = emptyList(),
                                description = description.trim(),
                                tags = tags.split(',').map(String::trim).filter(String::isNotBlank),
                                geoprivacy = geoprivacy,
                                captive = captive,
                            ),
                        )
                    },
                    enabled = plannedGroups.isNotEmpty() && oversizedGroups.isEmpty() && !submitting && !offline && connected,
                    modifier = Modifier.fillMaxWidth().padding(top = 14.dp).height(52.dp),
                ) {
                    if (submitting) CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                    else Icon(Icons.Rounded.CloudUpload, null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (submitting) "Posting observations…" else "Post ${plannedGroups.size} observation${if (plannedGroups.size == 1) "" else "s"} (${selectedItems.size} photos)")
                }
            }
        }
    }
}

@Composable
private fun PublishBatchGroupSection(
    group: PublishObservationGroup,
    selectedIds: Set<String>,
    separatePhotoIds: Set<String>,
    enabled: Boolean,
    onSelectedChange: (String, Boolean) -> Unit,
    onSeparateChange: (String, Boolean) -> Unit,
) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 10.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
            Text(
                if (group.items.size > 1) {
                    "Proposed group · ${group.items.size} photos"
                } else {
                    "Individual"
                },
                style = MaterialTheme.typography.titleMedium,
                color = Ink,
                modifier = Modifier.weight(1f),
            )
            if (group.items.size > 1) {
                Text(
                    "${formatGroupMetric(group.timeSpanMinutes, "min")} · ${formatGroupMetric(group.maxDistanceMeters, "m")}",
                    style = MaterialTheme.typography.labelMedium,
                    color = InkMuted,
                )
            }
        }
        if (group.items.size > GROUPED_PUBLISH_MAX_PHOTOS) {
            Text(
                "Split photos from this group before posting.",
                style = MaterialTheme.typography.bodySmall,
                color = Trail,
                modifier = Modifier.padding(top = 3.dp),
            )
        }
        group.items.forEach { item ->
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Checkbox(
                    checked = item.id in selectedIds,
                    onCheckedChange = { selected -> onSelectedChange(item.id, selected) },
                    enabled = enabled,
                )
                AsyncImage(
                    model = item.photo.url,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.size(58.dp).clip(RoundedCornerShape(4.dp)),
                )
                Column(Modifier.weight(1f).padding(start = 10.dp)) {
                    Text(item.commonName, style = MaterialTheme.typography.bodyMedium, color = Ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(item.hikeTitle, style = MaterialTheme.typography.bodySmall, color = InkMuted, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(item.photo.takenAt ?: item.hikeDate.ifBlank { "Time unavailable" }, style = MaterialTheme.typography.bodySmall, color = InkMuted, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                if (group.items.size > 1 && item.id in selectedIds) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Checkbox(
                            checked = item.photo.id in separatePhotoIds,
                            onCheckedChange = { separate -> onSeparateChange(item.photo.id, separate) },
                            enabled = enabled,
                        )
                        Text("Split", style = MaterialTheme.typography.labelSmall, color = InkMuted)
                    }
                }
            }
        }
    }
}

private fun formatGroupMetric(value: Double, suffix: String): String =
    if (suffix == "min") "${String.format(Locale.US, "%.0f", value)} $suffix"
    else "${String.format(Locale.US, "%.0f", value)} $suffix"

@Composable
private fun PublishItemContent(
    item: PublishItem,
    position: Int,
    total: Int,
    hasNext: Boolean,
    connected: Boolean,
    offline: Boolean,
    publishing: Boolean,
    onNext: () -> Unit,
    onPublish: (PublishOptions) -> Unit,
    onConnectInat: () -> Unit,
) {
    var confirmOpen by remember(item.id) { mutableStateOf(false) }
    var includeRelated by remember(item.id) { mutableStateOf(true) }
    var description by remember(item.id) { mutableStateOf(item.photo.caption) }
    var tags by remember(item.id) { mutableStateOf("") }
    var geoprivacy by remember(item.id) { mutableStateOf("open") }
    var captive by remember(item.id) { mutableStateOf(false) }
    val context = LocalContext.current
    LazyColumn(Modifier.fillMaxSize().padding(bottom = 84.dp)) {
        item {
            Box(Modifier.fillMaxWidth().height(390.dp).background(Moss)) {
                AsyncImage(item.photo.url, item.commonName, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                Box(
                    Modifier.fillMaxWidth().height(160.dp).align(Alignment.BottomCenter).background(
                        Brush.verticalGradient(listOf(Color.Transparent, Color(0xE0183A2D))),
                    ),
                )
                Column(Modifier.align(Alignment.BottomStart).padding(20.dp)) {
                    Text("${publishStateLabel(item.state)} · $position OF $total", style = MaterialTheme.typography.labelSmall, color = Color(0xFFD6E0D2))
                    Text(item.commonName, style = MaterialTheme.typography.headlineLarge, color = Paper, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    if (item.scientificName.isNotBlank()) {
                        Text(item.scientificName, style = MaterialTheme.typography.bodyLarge, color = Color(0xFFD6E0D2), fontStyle = FontStyle.Italic)
                    }
                }
            }
        }
        item {
            Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 22.dp)) {
                Text(item.hikeTitle, style = MaterialTheme.typography.titleLarge, color = Ink)
                val contextLine = listOf(formatPublishDate(item.photo.takenAt ?: item.hikeDate), item.locationName)
                    .filter { it.isNotBlank() }
                    .joinToString(" · ")
                if (contextLine.isNotBlank()) Text(contextLine, style = MaterialTheme.typography.bodyLarge, color = InkMuted, modifier = Modifier.padding(top = 4.dp))
                if (item.photo.caption.isNotBlank()) {
                    Text(item.photo.caption, style = MaterialTheme.typography.bodyLarge, color = Ink, modifier = Modifier.padding(top = 17.dp))
                }

                when (item.state) {
                    "ready" -> {
                        Text(
                            if (connected && item.relatedPhotoCount > 1) {
                                "${item.relatedPhotoCount} photos from this outing can become one iNaturalist observation."
                            } else if (connected) {
                                "Ready to create a public iNaturalist observation with this photo, date, and location."
                            } else {
                                "Connect iNaturalist to publish this observation."
                            },
                            style = MaterialTheme.typography.bodyMedium,
                            color = InkMuted,
                            modifier = Modifier.padding(top = 18.dp),
                        )
                        Button(
                            onClick = { confirmOpen = true },
                            enabled = !offline && !publishing,
                            modifier = Modifier.fillMaxWidth().padding(top = 14.dp).height(52.dp),
                        ) {
                            if (publishing) CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                            else Icon(Icons.Rounded.CloudUpload, null)
                            Spacer(Modifier.width(8.dp))
                            Text(
                                when {
                                    publishing -> "Publishing…"
                                    connected -> "Post to iNaturalist"
                                    else -> "Connect and publish"
                                },
                            )
                        }
                    }
                    "needs_attention" -> {
                        Row(Modifier.padding(top = 18.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Rounded.ErrorOutline, null, tint = Trail)
                            Text("Observation created, but the photo needs attention.", style = MaterialTheme.typography.bodyMedium, color = Ink, modifier = Modifier.padding(start = 9.dp))
                        }
                        if (item.inatUrl.isNotBlank()) {
                            Button(
                                onClick = { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(item.inatUrl))) },
                                modifier = Modifier.fillMaxWidth().padding(top = 14.dp),
                            ) {
                                Icon(Icons.AutoMirrored.Rounded.Launch, null)
                                Spacer(Modifier.width(8.dp))
                                Text("Finish on iNaturalist")
                            }
                        }
                    }
                    else -> {
                        Row(Modifier.padding(top = 18.dp), verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.size(34.dp).clip(CircleShape).background(Color(0xFFDCE5D7)), contentAlignment = Alignment.Center) {
                                Icon(Icons.Rounded.Check, null, tint = Moss, modifier = Modifier.size(21.dp))
                            }
                            Column(Modifier.padding(start = 10.dp)) {
                                Text("Published to iNaturalist", style = MaterialTheme.typography.titleMedium, color = Ink)
                                item.postedAt?.let { Text(formatPublishDate(it), style = MaterialTheme.typography.bodyMedium, color = InkMuted) }
                            }
                        }
                        if (item.inatUrl.isNotBlank()) {
                            OutlinedButton(
                                onClick = { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(item.inatUrl))) },
                                modifier = Modifier.fillMaxWidth().padding(top = 14.dp),
                            ) {
                                Icon(Icons.AutoMirrored.Rounded.Launch, null)
                                Spacer(Modifier.width(8.dp))
                                Text("View on iNaturalist")
                            }
                        }
                    }
                }

                if (!connected) {
                    Button(
                        onClick = onConnectInat,
                        enabled = !offline && !publishing,
                        modifier = Modifier.fillMaxWidth().padding(top = 14.dp).height(52.dp),
                    ) {
                        Text("Connect iNaturalist")
                    }
                }

                OutlinedButton(
                    onClick = onNext,
                    enabled = hasNext && !publishing,
                    modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                ) {
                    Icon(Icons.Rounded.SkipNext, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(7.dp))
                    Text("Next record")
                }
            }
        }
    }

    if (confirmOpen) {
        AlertDialog(
            onDismissRequest = { confirmOpen = false },
            title = { Text("Publish ${item.commonName}?") },
            text = {
                Column(Modifier.heightIn(max = 520.dp).verticalScroll(rememberScrollState())) {
                    Text("This creates a public iNaturalist observation using the recorded date and coordinates.")
                    if (item.relatedPhotoCount > 1) {
                        Row(
                            Modifier.fillMaxWidth().padding(top = 14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text("Combine matching photos", style = MaterialTheme.typography.titleSmall)
                                Text(
                                    "Upload ${item.relatedPhotoCount} photos of this species from the same outing and day.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = InkMuted,
                                )
                            }
                            Switch(includeRelated, { includeRelated = it })
                        }
                    }
                    OutlinedTextField(
                        description,
                        { description = it },
                        Modifier.fillMaxWidth().padding(top = 12.dp),
                        label = { Text("Observation note") },
                        maxLines = 3,
                    )
                    OutlinedTextField(
                        tags,
                        { tags = it },
                        Modifier.fillMaxWidth().padding(top = 9.dp),
                        label = { Text("Tags · comma separated") },
                        singleLine = true,
                    )
                    Text("LOCATION SHARING", style = MaterialTheme.typography.labelSmall, color = InkMuted, modifier = Modifier.padding(top = 14.dp))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf("open" to "Exact", "obscured" to "Obscured", "private" to "Private").forEach { option ->
                            FilterChip(
                                selected = geoprivacy == option.first,
                                onClick = { geoprivacy = option.first },
                                label = { Text(option.second, style = MaterialTheme.typography.labelSmall) },
                                modifier = Modifier.weight(1f),
                            )
                        }
                    }
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Captive or cultivated", style = MaterialTheme.typography.titleSmall)
                            Text("Mark plants or animals that were not wild.", style = MaterialTheme.typography.bodySmall, color = InkMuted)
                        }
                        Switch(captive, { captive = it })
                    }
                }
            },
            confirmButton = {
                Button(onClick = {
                    confirmOpen = false
                    onPublish(
                        PublishOptions(
                            observationIds = if (includeRelated) item.relatedObservationIds else listOf(item.id),
                            description = description.trim(),
                            tags = tags.split(',').map(String::trim).filter(String::isNotBlank),
                            geoprivacy = geoprivacy,
                            captive = captive,
                        ),
                    )
                }) {
                    Text("Publish publicly")
                }
            },
            dismissButton = { TextButton(onClick = { confirmOpen = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun PublishLoading() {
    Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        CircularProgressIndicator(color = Moss, strokeWidth = 2.dp)
        Text("Preparing confirmed records…", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 12.dp))
    }
}

@Composable
private fun PublishEmpty(
    filter: PublishFilter,
    hikeTitle: String?,
    connected: Boolean,
    offline: Boolean,
    onConnectInat: () -> Unit,
    onRefresh: () -> Unit,
) {
    Column(
        Modifier.fillMaxSize().padding(horizontal = 34.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(Modifier.size(82.dp).clip(CircleShape).background(Color(0xFFDCE5D7)), contentAlignment = Alignment.Center) {
            Icon(if (filter == PublishFilter.Attention) Icons.Rounded.ErrorOutline else Icons.Rounded.Check, null, tint = Moss, modifier = Modifier.size(42.dp))
        }
        Text(
            (when (filter) {
                PublishFilter.Ready -> "Nothing waiting to post"
                PublishFilter.Attention -> "No posts need attention"
                PublishFilter.Posted -> "No published records yet"
            }) + if (hikeTitle == null) "" else " on this hike",
            style = MaterialTheme.typography.headlineMedium,
            color = Ink,
            modifier = Modifier.padding(top = 18.dp),
        )
        hikeTitle?.let {
            Text(it, style = MaterialTheme.typography.bodyLarge, color = InkMuted, modifier = Modifier.padding(top = 7.dp))
        }
        if (!connected) {
            Text(
                "Connect iNaturalist to publish confirmed sightings.",
                style = MaterialTheme.typography.bodyLarge,
                color = InkMuted,
                modifier = Modifier.padding(top = 7.dp),
            )
            Button(
                onClick = onConnectInat,
                enabled = !offline,
                modifier = Modifier.fillMaxWidth().padding(top = 18.dp).height(52.dp),
            ) {
                Text("Connect iNaturalist")
            }
        }
        OutlinedButton(
            onClick = onRefresh,
            modifier = Modifier.padding(top = if (connected) 18.dp else 10.dp),
        ) {
            Text("Check again")
        }
    }
}

private fun publishStateLabel(state: String): String = when (state) {
    "needs_attention" -> "NEEDS ATTENTION"
    "posted" -> "POSTED"
    else -> "READY TO POST"
}

private fun formatPublishDate(raw: String?): String {
    if (raw.isNullOrBlank()) return ""
    return try {
        LocalDate.parse(raw.take(10)).format(DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US))
    } catch (_: Exception) {
        raw.take(10)
    }
}
