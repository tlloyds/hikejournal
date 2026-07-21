@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.hikejournal.app.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.SkipNext
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.hikejournal.app.data.ReviewCandidate
import com.hikejournal.app.data.ReviewItem
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
    offline: Boolean,
    onRefresh: () -> Unit,
    onDecision: (ReviewItem, String, ReviewCandidate?) -> Unit,
    onRequestRecommendation: (ReviewItem) -> Unit,
) {
    var index by remember { mutableIntStateOf(0) }
    val queueSignature = remember(queue) { queue.joinToString(",") { it.id } }
    LaunchedEffect(queueSignature) {
        if (queue.isEmpty()) index = 0 else index = index.coerceIn(0, queue.lastIndex)
    }
    val item = queue.getOrNull(index)
    val pendingCount = queue.count { it.state == "pending" }
    val waitingCount = queue.count { it.candidates.isEmpty() }

    Column(Modifier.fillMaxSize().background(Parchment)) {
        Row(
            Modifier.fillMaxWidth().background(Moss).statusBarsPadding().padding(start = 20.dp, end = 8.dp, top = 15.dp, bottom = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text("HikeJournal", style = MaterialTheme.typography.titleMedium, color = Color(0xFFB7C8B5))
                Text("Species review", style = MaterialTheme.typography.headlineMedium, color = Paper)
                Text("$pendingCount TO DECIDE · $waitingCount NEED ID", style = MaterialTheme.typography.labelSmall, color = Color(0xFFB7C8B5))
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
            loading && queue.isEmpty() -> ReviewLoading()
            item == null -> ReviewEmpty(onRefresh)
            else -> AnimatedContent(
                targetState = item.id,
                transitionSpec = {
                    (fadeIn() + slideInHorizontally { it / 8 }) togetherWith
                        (fadeOut() + slideOutHorizontally { -it / 8 })
                },
                label = "review-photo",
            ) { targetId ->
                val targetItem = queue.firstOrNull { it.id == targetId } ?: item
                ReviewItemContent(
                    item = targetItem,
                    position = queue.indexOfFirst { it.id == targetId }.takeIf { it >= 0 }?.plus(1) ?: index + 1,
                    total = queue.size,
                    deciding = decidingId == targetItem.id,
                    identifying = identifyingId == targetItem.id,
                    enabled = !offline && decidingId == null && identifyingId == null,
                    onNext = { if (queue.isNotEmpty()) index = (index + 1) % queue.size },
                    onDecision = onDecision,
                    onRequestRecommendation = onRequestRecommendation,
                )
            }
        }
    }
}

@Composable
private fun ReviewItemContent(
    item: ReviewItem,
    position: Int,
    total: Int,
    deciding: Boolean,
    identifying: Boolean,
    enabled: Boolean,
    onNext: () -> Unit,
    onDecision: (ReviewItem, String, ReviewCandidate?) -> Unit,
    onRequestRecommendation: (ReviewItem) -> Unit,
) {
    var selectedIndex by remember(item.id) { mutableIntStateOf(0) }
    val selected = item.candidates.getOrNull(selectedIndex)
    val confidenceUsesFractionalScale = usesFractionalConfidenceScale(item.candidates.map { it.confidence })

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
                    Text("Awaiting a suggestion", style = MaterialTheme.typography.headlineMedium, color = Ink)
                    Text(
                        "Ask iNaturalist to analyze this photo using its computer-vision model. Location and date help narrow the result.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = InkMuted,
                        modifier = Modifier.padding(top = 7.dp),
                    )
                    Button(
                        onClick = { onRequestRecommendation(item) },
                        enabled = enabled,
                        modifier = Modifier.fillMaxWidth().padding(top = 20.dp).height(52.dp),
                    ) {
                        if (identifying) CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                        else Icon(Icons.Rounded.Refresh, null)
                        Spacer(Modifier.width(8.dp))
                        Text(if (identifying) "Asking iNaturalist…" else "Get iNaturalist recommendation")
                    }
                    OutlinedButton(onClick = onNext, enabled = !identifying, modifier = Modifier.fillMaxWidth().padding(top = 10.dp)) {
                        Icon(Icons.Rounded.SkipNext, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Skip for now")
                    }
                } else {
                    Text("Choose the best match", style = MaterialTheme.typography.headlineMedium, color = Ink)
                    Text("The first option is the current suggestion.", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
                    Spacer(Modifier.height(13.dp))
                    item.candidates.forEachIndexed { candidateIndex, candidate ->
                        CandidateRow(
                            candidate = candidate,
                            selected = selectedIndex == candidateIndex,
                            usesFractionalConfidenceScale = confidenceUsesFractionalScale,
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
                        OutlinedButton(onClick = onNext, enabled = deciding.not(), modifier = Modifier.weight(1f)) {
                            Icon(Icons.Rounded.SkipNext, null, Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("Skip")
                        }
                        OutlinedButton(
                            onClick = { onDecision(item, "reject", null) },
                            enabled = enabled,
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Trail),
                            modifier = Modifier.weight(1f),
                        ) {
                            Icon(Icons.Rounded.Close, null, Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("Reject")
                        }
                    }
                    Text(
                        "Reject removes this suggestion but keeps the photo queued for a better ID.",
                        style = MaterialTheme.typography.bodySmall,
                        color = InkMuted,
                        modifier = Modifier.padding(top = 9.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun CandidateRow(
    candidate: ReviewCandidate,
    selected: Boolean,
    usesFractionalConfidenceScale: Boolean,
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
        }
        candidate.confidence?.let {
            Text(
                formatConfidencePercent(it, usesFractionalConfidenceScale),
                style = MaterialTheme.typography.labelMedium,
                color = if (selected) Moss else InkMuted,
            )
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
private fun ReviewEmpty(onRefresh: () -> Unit) {
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
        OutlinedButton(onClick = onRefresh, modifier = Modifier.padding(top = 18.dp)) { Text("Check again") }
    }
}
