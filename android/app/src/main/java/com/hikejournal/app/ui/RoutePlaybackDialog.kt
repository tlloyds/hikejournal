package com.hikejournal.app.ui

import android.os.SystemClock
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Pause
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Replay
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.hikejournal.app.data.RoutePoint
import com.hikejournal.app.data.Sighting
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.TrailText
import kotlinx.coroutines.delay

private const val ROUTE_REPLAY_DURATION_MILLIS = 24_000L
private const val ROUTE_REPLAY_UPDATE_MILLIS = 66L

@Composable
internal fun RoutePlaybackDialog(
    routeTitle: String,
    routeSegments: List<List<RoutePoint>>,
    onDismiss: () -> Unit,
) {
    val path = remember(routeSegments) { RouteReplayPath(routeSegments) }
    var progress by remember(path) { mutableFloatStateOf(0f) }
    var isPlaying by remember(path) { mutableStateOf(false) }

    LaunchedEffect(isPlaying, path) {
        if (!isPlaying) return@LaunchedEffect
        if (progress >= 1f) progress = 0f
        val startingProgress = progress
        val durationMillis = (ROUTE_REPLAY_DURATION_MILLIS * (1f - startingProgress))
            .toLong()
            .coerceAtLeast(1L)
        val startTime = SystemClock.elapsedRealtime()
        while (progress < 1f) {
            delay(ROUTE_REPLAY_UPDATE_MILLIS)
            val elapsed = SystemClock.elapsedRealtime() - startTime
            progress = (startingProgress + elapsed.toFloat() / durationMillis).coerceAtMost(1f)
        }
        isPlaying = false
    }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Box(Modifier.fillMaxSize().background(Color(0xFF101A16))) {
            HikeJournalMap(
                sightings = emptyList<Sighting>(),
                selectedSighting = null,
                layerMode = MapLayerMode.Satellite,
                onSelect = {},
                onViewportChanged = {},
                modifier = Modifier.fillMaxSize(),
                routeSegments = routeSegments,
                currentPoint = path.pointAt(progress),
                routeRevealProgress = progress,
                selectedTrailIds = emptySet(),
                showsPhotos = false,
            )

            Row(
                Modifier
                    .align(Alignment.TopStart)
                    .fillMaxWidth()
                    .background(
                        Brush.verticalGradient(
                            listOf(Color(0xD9101A16), Color.Transparent),
                        ),
                    )
                    .statusBarsPadding()
                    .padding(start = 12.dp, end = 20.dp, top = 8.dp, bottom = 24.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onDismiss) {
                    Icon(Icons.Rounded.Close, "Close route replay", tint = Paper)
                }
                Column(Modifier.padding(start = 6.dp)) {
                    Text("ROUTE REPLAY", style = MaterialTheme.typography.labelSmall, color = Trail)
                    Text(
                        routeTitle.ifBlank { "Recorded hike" },
                        style = MaterialTheme.typography.titleMedium,
                        color = Paper,
                        maxLines = 1,
                    )
                }
            }

            Column(
                Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .background(
                        Brush.verticalGradient(
                            listOf(Color.Transparent, Color(0xD9101A16), Color(0xF2101A16)),
                        ),
                    )
                    .navigationBarsPadding()
                    .padding(start = 20.dp, end = 20.dp, top = 34.dp, bottom = 18.dp),
            ) {
                Text(
                    "Watch the route draw from start to finish.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Paper,
                )
                Slider(
                    value = progress,
                    onValueChange = { value ->
                        isPlaying = false
                        progress = value
                    },
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(
                        onClick = {
                            if (progress >= 1f) progress = 0f
                            isPlaying = !isPlaying
                        },
                        modifier = Modifier.size(48.dp),
                    ) {
                        Icon(
                            imageVector = when {
                                isPlaying -> Icons.Rounded.Pause
                                progress >= 1f -> Icons.Rounded.Replay
                                else -> Icons.Rounded.PlayArrow
                            },
                            contentDescription = when {
                                isPlaying -> "Pause route replay"
                                progress >= 1f -> "Replay route"
                                else -> "Play route"
                            },
                            tint = Trail,
                            modifier = Modifier.size(32.dp),
                        )
                    }
                    Text(
                        if (isPlaying) "Playing" else if (progress >= 1f) "Finished" else "Play",
                        style = MaterialTheme.typography.titleSmall,
                        color = Paper,
                        modifier = Modifier.weight(1f).padding(start = 8.dp),
                    )
                    Text("24 sec", style = MaterialTheme.typography.labelMedium, color = TrailText)
                }
            }
        }
    }
}
