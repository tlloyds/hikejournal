@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.hikejournal.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.SkipNext
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
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
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.hikejournal.app.data.ReviewCandidate
import com.hikejournal.app.data.ReviewItem
import com.hikejournal.app.data.ReviewBatchStatus
import com.hikejournal.app.data.ReviewPhotoGroup
import com.hikejournal.app.data.buildReviewPhotoGroups
import com.hikejournal.app.data.reviewConfidenceLabel
import com.hikejournal.app.data.splitReviewPhotoGroups
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.Trail
import java.util.Locale

@Composable
fun SpeciesReviewScreen(
    queue: List<ReviewItem>,
    loading: Boolean,
    decidingId: String?,
    identifyingId: String?,
    batchIdentifying: Boolean,
    batchProgress: ReviewBatchStatus?,
    inatConnected: Boolean,
    offline: Boolean,
    onRefresh: () -> Unit,
    onDecision: (ReviewItem, String, ReviewCandidate?) -> Unit,
    onRemoveFromReview: (ReviewItem) -> Unit,
    onRequestRecommendation: (ReviewItem) -> Unit,
    onConnectInat: () -> Unit,
    onSubmitBatch: (List<List<String>>) -> Unit,
    onBatchFinished: () -> Unit,
    onNavigateBack: () -> Unit,
) {
    var index by remember { mutableIntStateOf(0) }
    var horizontalDragDistance by remember { mutableFloatStateOf(0f) }
    var batchMode by remember { mutableStateOf(false) }
    val queueSignature = remember(queue) { queue.joinToString(",") { it.id } }
    val waitingItems = queue.filter { it.candidates.isEmpty() }
    val unsyncedWaitingItems = waitingItems.filterNot { reviewPhotoIsSynced(it) }
    val batchResumable = shouldResumeReviewBatch(batchIdentifying, batchProgress?.state)
    LaunchedEffect(queueSignature) {
        if (queue.isEmpty()) index = 0 else index = index.coerceIn(0, queue.lastIndex)
    }
    LaunchedEffect(batchProgress?.jobId, batchProgress?.state, batchIdentifying) {
        if (batchResumable) {
            batchMode = true
        }
        if (shouldAutoCloseReviewBatch(batchIdentifying, batchProgress?.state)) {
            onBatchFinished()
            batchMode = false
        }
    }
    val item = queue.getOrNull(index)
    val pendingCount = queue.count { it.state == "pending" }
    val waitingCount = queue.count { it.candidates.isEmpty() }

    BackHandler {
        when (reviewBackAction(batchMode, batchIdentifying, index)) {
            ReviewBackAction.Wait -> Unit
            ReviewBackAction.CloseBatch -> {
                if (batchProgress?.state == "failed") onBatchFinished()
                batchMode = false
            }
            ReviewBackAction.PreviousPhoto -> index -= 1
            ReviewBackAction.LeaveReview -> onNavigateBack()
        }
    }

    Column(Modifier.fillMaxSize().background(Parchment)) {
        Row(
            Modifier.fillMaxWidth().background(Moss).statusBarsPadding().padding(start = 20.dp, end = 8.dp, top = 15.dp, bottom = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text("HikeJournal", style = MaterialTheme.typography.titleMedium, color = Color(0xFFB7C8B5))
                Text("Species review", style = MaterialTheme.typography.headlineMedium, color = Paper)
                val syncSuffix = when {
                    unsyncedWaitingItems.any { it.photo.syncState == "needs_attention" } ->
                        " · ${unsyncedWaitingItems.size} NEED SYNC"
                    unsyncedWaitingItems.isNotEmpty() -> " · ${unsyncedWaitingItems.size} SYNCING"
                    else -> ""
                }
                Text("$pendingCount TO DECIDE · $waitingCount NEED ID$syncSuffix", style = MaterialTheme.typography.labelSmall, color = Color(0xFFB7C8B5))
            }
            TextButton(
                onClick = {
                    if (batchResumable) batchMode = true
                    else if (inatConnected) batchMode = true else onConnectInat()
                },
                enabled = if (batchResumable) {
                    !loading
                } else {
                    waitingItems.isNotEmpty() && unsyncedWaitingItems.isEmpty() && !loading && !offline
                },
                colors = ButtonDefaults.textButtonColors(
                    contentColor = Paper,
                    disabledContentColor = Color(0xFFD6E0D2),
                ),
            ) {
                Text(
                    when {
                        loading -> "Loading"
                        batchResumable -> "Resume batch"
                        unsyncedWaitingItems.isNotEmpty() -> "Syncing"
                        !inatConnected -> "Connect iNaturalist"
                        else -> "Batch ID"
                    },
                )
            }
            IconButton(onClick = onRefresh, enabled = !loading && decidingId == null) {
                if (loading) CircularProgressIndicator(Modifier.size(20.dp), color = Paper, strokeWidth = 2.dp)
                else Icon(Icons.Rounded.Refresh, "Refresh review queue", tint = Paper)
            }
        }

        if (offline) {
            Text(
                "OFFLINE COPY · DECISIONS PAUSE UNTIL CONNECTED",
                style = MaterialTheme.typography.labelSmall,
                color = Paper,
                modifier = Modifier.fillMaxWidth().background(Trail).padding(horizontal = 20.dp, vertical = 8.dp),
            )
        }

        when {
            batchMode -> SpeciesBatchIdentificationContent(
                queue = waitingItems,
                submitting = batchIdentifying,
                refreshing = loading,
                progress = batchProgress,
                connected = inatConnected,
                offline = offline,
                onBack = {
                    if (!batchIdentifying) {
                        if (batchProgress?.state == "failed") onBatchFinished()
                        batchMode = false
                    }
                },
                onSubmit = onSubmitBatch,
                onConnectInat = onConnectInat,
            )
            loading && queue.isEmpty() -> ReviewLoading()
            item == null -> ReviewEmpty(
                offline = offline,
                inatConnected = inatConnected,
                onRefresh = onRefresh,
                onConnectInat = onConnectInat,
            )
            else -> Box(
                Modifier.fillMaxSize().pointerInput(queueSignature, index) {
                    detectHorizontalDragGestures(
                        onHorizontalDrag = { _, dragAmount -> horizontalDragDistance += dragAmount },
                        onDragEnd = {
                            when {
                                horizontalDragDistance > 72f && index > 0 -> index -= 1
                                horizontalDragDistance < -72f && index < queue.lastIndex -> index += 1
                            }
                            horizontalDragDistance = 0f
                        },
                        onDragCancel = { horizontalDragDistance = 0f },
                    )
                },
            ) {
                AnimatedContent(
                    targetState = item.id,
                    transitionSpec = {
                        (fadeIn() + slideInHorizontally { it / 8 }) togetherWith
                            (fadeOut() + slideOutHorizontally { -it / 8 })
                    },
                    label = "review-photo",
                ) { targetId ->
                    val targetItem = queue.firstOrNull { it.id == targetId } ?: item
                    val targetPosition = queue.indexOfFirst { it.id == targetId }
                        .takeIf { it >= 0 }
                        ?.plus(1)
                        ?: index + 1
                    ReviewItemContent(
                        item = targetItem,
                        position = targetPosition,
                        total = queue.size,
                        hasNext = targetPosition < queue.size,
                        deciding = decidingId == targetItem.id,
                        identifying = identifyingId == targetItem.id,
                        inatConnected = inatConnected,
                        offline = offline,
                        enabled = reviewPhotoIsSynced(targetItem) && !offline && decidingId == null && identifyingId == null,
                        onNext = { if (index < queue.lastIndex) index += 1 },
                        onDecision = onDecision,
                        onRemoveFromReview = onRemoveFromReview,
                        onRequestRecommendation = onRequestRecommendation,
                        onConnectInat = onConnectInat,
                    )
                }
            }
        }
    }
}

@Composable
private fun SpeciesBatchIdentificationContent(
    queue: List<ReviewItem>,
    submitting: Boolean,
    refreshing: Boolean,
    progress: ReviewBatchStatus?,
    connected: Boolean,
    offline: Boolean,
    onBack: () -> Unit,
    onSubmit: (List<List<String>>) -> Unit,
    onConnectInat: () -> Unit,
) {
    var selectedIds by remember(queue) { mutableStateOf(queue.map { it.id }.toSet()) }
    var separatePhotoIds by remember(queue) { mutableStateOf(emptySet<String>()) }
    val listState = rememberLazyListState()
    val selectedItems = queue.filter { it.id in selectedIds }
    val proposedGroups = buildReviewPhotoGroups(selectedItems)
    val displayGroups = proposedGroups.sortedBy { it.items.size == 1 }
    val plannedGroups = splitReviewPhotoGroups(proposedGroups, separatePhotoIds)
    val groupedCount = plannedGroups.count { it.items.size > 1 }
    val individualCount = plannedGroups.count { it.items.size == 1 }

    LaunchedEffect(submitting) {
        if (submitting) listState.animateScrollToItem(0)
    }

    LazyColumn(
        state = listState,
        modifier = Modifier.fillMaxSize().padding(bottom = 92.dp),
    ) {
        item {
            Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 20.dp)) {
                TextButton(
                    onClick = onBack,
                    enabled = !submitting && !refreshing,
                    colors = ButtonDefaults.textButtonColors(
                        contentColor = Moss,
                        disabledContentColor = InkMuted,
                    ),
                    contentPadding = ButtonDefaults.TextButtonContentPadding,
                ) {
                    Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Back")
                }
                Text("Plan batch IDs", style = MaterialTheme.typography.headlineMedium, color = Ink)
                Text(
                    "Select waiting photos and HikeJournal will propose groups from the same outing within 2 minutes and 12 meters. Split any photo that deserves its own request.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 5.dp),
                )
                Row(
                    Modifier.fillMaxWidth().padding(top = 14.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    OutlinedButton(
                        onClick = { selectedIds = queue.map { it.id }.toSet() },
                        enabled = !submitting && !refreshing,
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.outlinedButtonColors(
                            contentColor = Moss,
                            disabledContentColor = InkMuted,
                        ),
                    ) { Text("Select waiting") }
                    OutlinedButton(
                        onClick = {
                            selectedIds = emptySet()
                            separatePhotoIds = emptySet()
                        },
                        enabled = !submitting && !refreshing && selectedIds.isNotEmpty(),
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.outlinedButtonColors(
                            contentColor = Trail,
                            disabledContentColor = InkMuted,
                        ),
                    ) { Text("Clear") }
                }
                Text(
                    "${selectedItems.size} selected · ${plannedGroups.size} ID request${if (plannedGroups.size == 1) "" else "s"} · $groupedCount grouped · $individualCount individual",
                    style = MaterialTheme.typography.labelMedium,
                    color = if (selectedItems.isEmpty()) InkMuted else Moss,
                    modifier = Modifier.padding(top = 15.dp),
                )
                progress?.let { batch ->
                    val total = batch.totalPhotos.coerceAtLeast(1)
                    val current = when {
                        batch.state == "completed" -> total
                        batch.currentPhotoNumber > 0 -> batch.currentPhotoNumber.coerceIn(1, total)
                        else -> 0
                    }
                    val statusLabel = when (batch.state) {
                        "queued" -> "Preparing ID requests…"
                        "running" -> "Submitting photo $current of ${batch.totalPhotos}…"
                        "completed" -> "Submitted ${batch.processedCount} of ${batch.totalPhotos} photos"
                        "failed" -> "Stopped after ${batch.processedCount} of ${batch.totalPhotos} photos"
                        else -> "Updating submission status…"
                    }
                    Text(
                        statusLabel,
                        style = MaterialTheme.typography.labelMedium,
                        color = if (batch.state == "failed") Trail else Moss,
                        modifier = Modifier.padding(top = 14.dp),
                    )
                    LinearProgressIndicator(
                        progress = { current.toFloat() / total.toFloat() },
                        modifier = Modifier.fillMaxWidth().padding(top = 7.dp),
                        color = if (batch.state == "failed") Trail else Moss,
                    )
                    if (batch.currentGroup > 0 && batch.totalGroups > 0 && batch.state == "running") {
                        Text(
                            "Request ${batch.currentGroup} of ${batch.totalGroups}",
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
                    "Choose at least one photo to build the request plan.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = InkMuted,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 18.dp),
                )
            }
        } else {
            items(displayGroups, key = { group -> group.photoIds.joinToString("|") }) { group ->
                BatchGroupSection(
                    group = group,
                    selectedIds = selectedIds,
                    separatePhotoIds = separatePhotoIds,
                    enabled = !submitting && !refreshing,
                    onSelectedChange = { photoId, selected ->
                        selectedIds = if (selected) selectedIds + photoId else selectedIds - photoId
                        separatePhotoIds = separatePhotoIds - photoId
                    },
                    onSeparateChange = { photoId, separate ->
                        separatePhotoIds = if (separate) separatePhotoIds + photoId else separatePhotoIds - photoId
                    },
                )
            }
        }
        item {
            Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 18.dp)) {
                Text(
                    "Two-photo groups use the stronger top suggestion for both photos. Larger groups need a shared top-choice consensus; otherwise the request saves individual suggestions.",
                    style = MaterialTheme.typography.bodySmall,
                    color = InkMuted,
                )
                Button(
                    onClick = {
                        if (connected) onSubmit(plannedGroups.map { it.photoIds }) else onConnectInat()
                    },
                    enabled = plannedGroups.isNotEmpty() && !submitting && !refreshing && !offline,
                    modifier = Modifier.fillMaxWidth().padding(top = 14.dp).height(52.dp),
                ) {
                    if (submitting || refreshing) CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                    else Icon(Icons.Rounded.Refresh, null)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        when {
                            submitting -> "Submitting ID requests…"
                            refreshing -> "Refreshing remaining photos…"
                            !connected -> "Connect iNaturalist"
                            else -> "Submit ${plannedGroups.size} ID request${if (plannedGroups.size == 1) "" else "s"}"
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun BatchGroupSection(
    group: ReviewPhotoGroup,
    selectedIds: Set<String>,
    separatePhotoIds: Set<String>,
    enabled: Boolean,
    onSelectedChange: (String, Boolean) -> Unit,
    onSeparateChange: (String, Boolean) -> Unit,
) {
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 10.dp),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
            Text(
                if (group.items.size > 1) "Proposed group · ${group.items.size} photos" else "Individual",
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
        group.items.forEach { item ->
            Row(
                Modifier.fillMaxWidth().padding(top = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Checkbox(
                    checked = item.id in selectedIds && item.id !in separatePhotoIds,
                    onCheckedChange = { checked -> onSelectedChange(item.id, checked) },
                    enabled = enabled,
                )
                AsyncImage(
                    model = item.photo.url,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.size(58.dp).clip(RoundedCornerShape(4.dp)),
                )
                Column(Modifier.weight(1f).padding(start = 10.dp)) {
                    Text(
                        item.hikeTitle,
                        style = MaterialTheme.typography.bodyMedium,
                        color = Ink,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        item.photo.takenAt ?: item.hikeDate.ifBlank { "Time unavailable" },
                        style = MaterialTheme.typography.bodySmall,
                        color = InkMuted,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                if (group.items.size > 1 && item.id in selectedIds) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Checkbox(
                            checked = item.id in separatePhotoIds,
                            onCheckedChange = { separate -> onSeparateChange(item.id, separate) },
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
    if (suffix == "min") "${String.format(Locale.US, "%.1f", value)} $suffix"
    else "${String.format(Locale.US, "%.0f", value)} $suffix"

internal fun shouldShowInatConnectionAction(inatConnected: Boolean): Boolean = !inatConnected

@Composable
private fun ReviewItemContent(
    item: ReviewItem,
    position: Int,
    total: Int,
    hasNext: Boolean,
    deciding: Boolean,
    identifying: Boolean,
    inatConnected: Boolean,
    offline: Boolean,
    enabled: Boolean,
    onNext: () -> Unit,
    onDecision: (ReviewItem, String, ReviewCandidate?) -> Unit,
    onRemoveFromReview: (ReviewItem) -> Unit,
    onRequestRecommendation: (ReviewItem) -> Unit,
    onConnectInat: () -> Unit,
) {
    var selectedIndex by remember(item.id) { mutableIntStateOf(0) }
    val selected = item.candidates.getOrNull(selectedIndex)
    LazyColumn(Modifier.fillMaxSize().padding(bottom = 84.dp)) {
        item {
            Box(Modifier.fillMaxWidth().height(390.dp).background(Moss)) {
                AsyncImage(
                    model = item.photo.url,
                    contentDescription = "Photo awaiting species review",
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.Crop,
                )
                Box(
                    Modifier.fillMaxWidth().height(130.dp).align(Alignment.BottomCenter).background(
                        Brush.verticalGradient(listOf(Color.Transparent, Color(0xD8183A2D))),
                    ),
                )
                Column(Modifier.align(Alignment.BottomStart).padding(20.dp)) {
                    Text("$position OF $total", style = MaterialTheme.typography.labelSmall, color = Color(0xFFD6E0D2))
                    Text(item.hikeTitle, style = MaterialTheme.typography.headlineMedium, color = Paper, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    val place = item.locationName.ifBlank { item.hikeDate }
                    if (place.isNotBlank()) Text(place, style = MaterialTheme.typography.bodyMedium, color = Color(0xFFD6E0D2), maxLines = 1)
                }
            }
        }

        item {
            Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 22.dp)) {
                if (item.candidates.isEmpty()) {
                    val photoSynced = reviewPhotoIsSynced(item)
                    Text(
                        when (item.photo.syncState) {
                            "needs_attention" -> "Photo needs sync attention"
                            else -> if (photoSynced) "Awaiting a suggestion" else "Waiting for photo sync"
                        },
                        style = MaterialTheme.typography.headlineMedium,
                        color = Ink,
                    )
                    Text(
                        when (item.photo.syncState) {
                            "needs_attention" -> "Resolve the sync notice, then HikeJournal will include this photo in Batch ID."
                            else -> if (photoSynced) {
                                "Ask iNaturalist to analyze this photo using its computer-vision model. Location and date help narrow the result."
                            } else {
                                "This selected photo is in the review queue and will become available for identification as soon as its upload finishes."
                            }
                        },
                        style = MaterialTheme.typography.bodyLarge,
                        color = InkMuted,
                        modifier = Modifier.padding(top = 7.dp),
                    )
                    Button(
                        onClick = { if (inatConnected) onRequestRecommendation(item) else onConnectInat() },
                        enabled = !offline && !identifying &&
                            (!inatConnected || (enabled && photoSynced)),
                        modifier = Modifier.fillMaxWidth().padding(top = 20.dp).height(52.dp),
                    ) {
                        if (identifying) CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                        else Icon(Icons.Rounded.Refresh, null)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            when {
                                identifying -> "Asking iNaturalist…"
                                !inatConnected -> "Connect iNaturalist"
                                !photoSynced -> "Upload before ID"
                                else -> "Get iNaturalist recommendation"
                            },
                        )
                    }
                    OutlinedButton(
                        onClick = onNext,
                        enabled = hasNext && !identifying,
                        modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                    ) {
                        Icon(Icons.Rounded.SkipNext, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Skip for now")
                    }
                    OutlinedButton(
                        onClick = { onRemoveFromReview(item) },
                        enabled = !identifying && !deciding,
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = Trail),
                        modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                    ) {
                        if (deciding) CircularProgressIndicator(Modifier.size(18.dp), color = Trail, strokeWidth = 2.dp)
                        else Icon(Icons.Rounded.Close, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Remove from review")
                    }
                    if (shouldShowInatConnectionAction(inatConnected)) {
                        TextButton(onClick = onConnectInat, enabled = !identifying, modifier = Modifier.fillMaxWidth().padding(top = 5.dp)) {
                            Text("Connect iNaturalist")
                        }
                    }
                } else {
                    Text("Choose the best match", style = MaterialTheme.typography.headlineMedium, color = Ink)
                    Text("The first option is the current suggestion.", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
                    Spacer(Modifier.height(13.dp))
                    item.candidates.forEachIndexed { candidateIndex, candidate ->
                        CandidateRow(
                            candidate = candidate,
                            selected = selectedIndex == candidateIndex,
                            onClick = { selectedIndex = candidateIndex },
                        )
                    }

                    Button(
                        onClick = { onDecision(item, "confirm", selected) },
                        enabled = enabled && selected != null,
                        modifier = Modifier.fillMaxWidth().padding(top = 18.dp).height(52.dp),
                    ) {
                        if (deciding) CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                        else Icon(Icons.Rounded.Check, null)
                        Spacer(Modifier.width(8.dp))
                        Text(if (selectedIndex == 0) "Confirm ID" else "Use this ID")
                    }
                    Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedButton(onClick = onNext, enabled = hasNext && deciding.not(), modifier = Modifier.weight(1f)) {
                            Icon(Icons.Rounded.SkipNext, null, Modifier.size(18.dp))
                            Spacer(Modifier.width(5.dp))
                            Text("Skip")
                        }
                        OutlinedButton(
                            onClick = { onDecision(item, "reject", null) },
                            enabled = enabled,
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Trail),
                            modifier = Modifier.weight(1f),
                        ) {
                            Icon(Icons.Rounded.Close, null, Modifier.size(18.dp))
                            Spacer(Modifier.width(5.dp))
                            Text("Reject")
                        }
                    }
                    Text(
                        "Reject removes this suggestion but keeps the photo queued for a better ID.",
                        style = MaterialTheme.typography.bodySmall,
                        color = InkMuted,
                        modifier = Modifier.padding(top = 9.dp),
                    )
                    OutlinedButton(
                        onClick = { onRemoveFromReview(item) },
                        enabled = enabled,
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = Trail),
                        modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                    ) {
                        if (deciding) CircularProgressIndicator(Modifier.size(18.dp), color = Trail, strokeWidth = 2.dp)
                        else Icon(Icons.Rounded.Close, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Remove from review")
                    }
                }
            }
        }
    }
}

internal enum class ReviewBackAction { Wait, CloseBatch, PreviousPhoto, LeaveReview }

internal fun reviewBackAction(
    batchMode: Boolean,
    batchIdentifying: Boolean,
    index: Int,
): ReviewBackAction = when {
    batchMode && batchIdentifying -> ReviewBackAction.Wait
    batchMode -> ReviewBackAction.CloseBatch
    index > 0 -> ReviewBackAction.PreviousPhoto
    else -> ReviewBackAction.LeaveReview
}

internal fun shouldAutoCloseReviewBatch(batchIdentifying: Boolean, state: String?): Boolean =
    !batchIdentifying && state == "completed"

internal fun shouldResumeReviewBatch(batchIdentifying: Boolean, state: String?): Boolean =
    batchIdentifying || state in setOf("queued", "running", "failed")

internal fun reviewPhotoIsSynced(item: ReviewItem): Boolean =
    item.photo.syncState == "synced" && !item.photo.url.startsWith("file:")

@Composable
private fun CandidateRow(
    candidate: ReviewCandidate,
    selected: Boolean,
    onClick: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = onClick)
        Column(Modifier.weight(1f).padding(start = 7.dp)) {
            Text(candidate.commonName, style = MaterialTheme.typography.titleMedium, color = Ink)
            if (candidate.scientificName.isNotBlank()) {
                Text(candidate.scientificName, style = MaterialTheme.typography.bodyMedium, color = InkMuted, fontStyle = FontStyle.Italic)
            }
            reviewConfidenceLabel(candidate.confidence)?.let { confidence ->
                Text(confidence, style = MaterialTheme.typography.bodySmall, color = InkMuted)
            }
        }
    }
}

@Composable
private fun ReviewLoading() {
    Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        CircularProgressIndicator(color = Moss, strokeWidth = 2.dp)
        Text("Gathering field decisions…", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 12.dp))
    }
}

@Composable
private fun ReviewEmpty(
    offline: Boolean,
    inatConnected: Boolean,
    onRefresh: () -> Unit,
    onConnectInat: () -> Unit,
) {
    Column(
        Modifier.fillMaxSize().padding(horizontal = 34.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(Modifier.size(82.dp).clip(CircleShape).background(Color(0xFFDCE5D7)), contentAlignment = Alignment.Center) {
            Icon(Icons.Rounded.Check, null, tint = Moss, modifier = Modifier.size(42.dp))
        }
        Text("Review queue clear", style = MaterialTheme.typography.headlineMedium, color = Ink, modifier = Modifier.padding(top = 18.dp))
        Text("New photos marked for species review will gather here.", style = MaterialTheme.typography.bodyLarge, color = InkMuted, modifier = Modifier.padding(top = 6.dp))
        if (shouldShowInatConnectionAction(inatConnected)) {
            Button(
                onClick = onConnectInat,
                enabled = !offline,
                modifier = Modifier.fillMaxWidth().padding(top = 22.dp).height(52.dp),
            ) {
                Text("Connect iNaturalist")
            }
        }
        OutlinedButton(
            onClick = onRefresh,
            modifier = Modifier.padding(top = if (inatConnected) 22.dp else 10.dp),
        ) { Text("Check again") }
    }
}
