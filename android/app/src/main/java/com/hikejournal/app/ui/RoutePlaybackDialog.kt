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
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Pause
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Replay
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
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
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.hikejournal.app.data.RoutePoint
import com.hikejournal.app.data.Sighting
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail
import kotlinx.coroutines.delay
import java.util.Locale

private const val ROUTE_REPLAY_DURATION_MILLIS = 24_000L
private const val ROUTE_REPLAY_UPDATE_MILLIS = 66L

@Composable
internal fun RoutePlaybackDialog(
    routeTitle: String,
    routeSegments: List<List<RoutePoint>>,
    onDismiss: () -> Unit,
) {
    val path = remember(routeSegments) { RouteReplayPath(routeSegments) }
    val routeMileMarkers = remember(path) { path.mileMarkers() }
    var progress by remember(path) { mutableFloatStateOf(0f) }
    var isPlaying by remember(path) { mutableStateOf(false) }
    var playbackSpeed by remember(path) { mutableFloatStateOf(1f) }
    val completedDistanceMeters = path.distanceAt(progress)
    val completedRouteMile = (completedDistanceMeters / ROUTE_REPLAY_METERS_PER_MILE).toInt()

    LaunchedEffect(isPlaying, path, playbackSpeed) {
        if (!isPlaying) return@LaunchedEffect
        if (progress >= 1f) progress = 0f
        val startingProgress = progress
        val durationMillis = (ROUTE_REPLAY_DURATION_MILLIS * (1f - startingProgress) / playbackSpeed)
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
                routeFitTopInset = 80.dp,
                routeFitBottomInset = 240.dp,
                routeMileMarkers = routeMileMarkers,
                completedRouteMile = completedRouteMile,
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
                            listOf(Color.Transparent, Color(0xE2183A2D), Color(0xF2183A2D)),
                        ),
                    )
                    .padding(bottom = 56.dp)
                    .navigationBarsPadding()
                    .padding(start = 20.dp, end = 20.dp, top = 26.dp, bottom = 14.dp),
            ) {
                Text(
                    String.format(
                        Locale.US,
                        "%.2f / %.2f mi",
                        completedDistanceMeters / ROUTE_REPLAY_METERS_PER_MILE,
                        path.totalDistanceMiles,
                    ),
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
                    colors = SliderDefaults.colors(
                        thumbColor = Paper,
                        activeTrackColor = Trail,
                        inactiveTrackColor = Paper.copy(alpha = 0.72f),
                        activeTickColor = Trail,
                        inactiveTickColor = Paper.copy(alpha = 0.72f),
                    ),
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(
                        onClick = {
                            if (progress >= 1f) progress = 0f
                            isPlaying = !isPlaying
                        },
                        modifier = Modifier
                            .size(52.dp)
                            .background(Paper, CircleShape),
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
                            tint = Color(0xFF183A2D),
                            modifier = Modifier.size(32.dp),
                        )
                    }
                    Text(
                        if (isPlaying) "Playing" else if (progress >= 1f) "Finished" else "Play",
                        style = MaterialTheme.typography.titleSmall,
                        color = Paper,
                        modifier = Modifier.weight(1f).padding(start = 8.dp),
                    )
                    Row(
                        Modifier
                            .background(Color(0x553A5C4A), RoundedCornerShape(12.dp))
                            .selectableGroup(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        listOf(0.5f, 1f, 2f).forEach { speed ->
                            val selected = playbackSpeed == speed
                            Box(
                                Modifier
                                    .padding(3.dp)
                                    .background(
                                        color = if (selected) Paper else Color.Transparent,
                                        shape = RoundedCornerShape(9.dp),
                                    )
                                    .selectable(
                                        selected = selected,
                                        role = Role.RadioButton,
                                        onClick = { playbackSpeed = speed },
                                    )
                                    .padding(horizontal = 8.dp, vertical = 8.dp),
                            ) {
                                Text(
                                    text = when (speed) {
                                        0.5f -> "0.5×"
                                        1f -> "1×"
                                        else -> "2×"
                                    },
                                    style = MaterialTheme.typography.labelSmall,
                                    color = if (selected) Color(0xFF183A2D) else Paper,
                                )
                            }
                        }
                    }
                    val replayDurationSeconds = (ROUTE_REPLAY_DURATION_MILLIS / 1000f / playbackSpeed).toInt()
                    Text(
                        "$replayDurationSeconds sec",
                        style = MaterialTheme.typography.labelMedium,
                        color = Paper.copy(alpha = 0.82f),
                        modifier = Modifier.padding(start = 8.dp),
                    )
                }
            }
        }
    }
}
