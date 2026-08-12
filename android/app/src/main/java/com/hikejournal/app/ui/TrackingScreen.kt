@file:OptIn(androidx.compose.animation.ExperimentalAnimationApi::class)

package com.hikejournal.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.GpsFixed
import androidx.compose.material.icons.rounded.GpsNotFixed
import androidx.compose.material.icons.rounded.Layers
import androidx.compose.material.icons.rounded.AddLocationAlt
import androidx.compose.material.icons.rounded.MyLocation
import androidx.compose.material.icons.rounded.Pause
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.hikejournal.app.data.RoutePoint
import com.hikejournal.app.data.FieldMark
import com.hikejournal.app.data.Sighting
import com.hikejournal.app.tracking.TrackingSnapshot
import com.hikejournal.app.tracking.TrackingStatus
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail
import java.util.Locale

internal enum class TrackingGpsUiStatus {
    Searching,
    Strong,
    Weak,
    Unavailable,
}

internal val DEFAULT_TRACKING_MAP_LAYER = MapLayerMode.Satellite

internal data class TrackingUiModel(
    val sessionId: String,
    val status: TrackingStatus,
    val elapsedSeconds: Long,
    val distanceMiles: Double,
    val routeSegments: List<List<RoutePoint>>,
    val currentPoint: RoutePoint?,
    val gpsStatus: TrackingGpsUiStatus,
    val accuracyMeters: Double?,
    val pointCount: Int,
    val error: String? = null,
) {
    val isPaused: Boolean get() = status == TrackingStatus.PAUSED
    val isBusy: Boolean get() = status == TrackingStatus.STARTING || status == TrackingStatus.FINALIZING
}

internal fun TrackingSnapshot.toTrackingUiModel(nowEpochMs: Long = System.currentTimeMillis()): TrackingUiModel {
    val ageMs = lastFixEpochMs?.let { (nowEpochMs - it).coerceAtLeast(0L) }
    val accuracyMeters = lastAccuracyMeters?.toDouble()
    val gpsStatus = when {
        status == TrackingStatus.FINISHED -> TrackingGpsUiStatus.Unavailable
        accuracyMeters == null || ageMs == null -> TrackingGpsUiStatus.Searching
        ageMs > 60_000L -> TrackingGpsUiStatus.Searching
        accuracyMeters <= 20.0 -> TrackingGpsUiStatus.Strong
        accuracyMeters <= 50.0 -> TrackingGpsUiStatus.Weak
        else -> TrackingGpsUiStatus.Unavailable
    }
    val mappedSegments = routeSegments.map { segment ->
        segment.map { RoutePoint(latitude = it.latitude, longitude = it.longitude) }
    }
    return TrackingUiModel(
        sessionId = sessionId,
        status = status,
        elapsedSeconds = (activeElapsedMs / 1_000L).coerceAtLeast(0L),
        distanceMiles = (distanceMeters / METERS_PER_MILE).coerceAtLeast(0.0),
        routeSegments = mappedSegments,
        currentPoint = mappedSegments.lastOrNull { it.isNotEmpty() }?.last(),
        gpsStatus = gpsStatus,
        accuracyMeters = accuracyMeters,
        pointCount = pointCount,
        error = error ?: trackingRecoveryMessage(recoveryReason),
    )
}

@Composable
internal fun HikeTrackingScreen(
    tracking: TrackingUiModel,
    fieldMarks: List<FieldMark>,
    selectedTrailIds: Set<String>,
    onBack: () -> Unit,
    onPause: () -> Unit,
    onResume: () -> Unit,
    onEnd: () -> Unit,
    onDiscard: () -> Unit,
    onAddFieldMark: (String, String) -> Unit,
    requestEndConfirmation: Boolean = false,
    onEndConfirmationShown: () -> Unit = {},
) {
    var layerMode by remember { mutableStateOf(DEFAULT_TRACKING_MAP_LAYER) }
    var followPosition by rememberSaveable(tracking.sessionId) { mutableStateOf(true) }
    var confirmEnd by rememberSaveable(tracking.sessionId) { mutableStateOf(false) }
    var markDialogOpen by rememberSaveable(tracking.sessionId) { mutableStateOf(false) }

    androidx.compose.runtime.LaunchedEffect(requestEndConfirmation, tracking.isPaused) {
        if (requestEndConfirmation && tracking.isPaused) {
            confirmEnd = true
            onEndConfirmationShown()
        }
    }
    BackHandler(onBack = onBack)

    Box(Modifier.fillMaxSize().background(Moss)) {
        HikeJournalMap(
            sightings = fieldMarks.map { mark ->
                Sighting(
                    id = mark.id,
                    hikeId = mark.hikeId,
                    hikeTitle = "Current hike",
                    hikeDate = "",
                    locationName = "",
                    url = "",
                    caption = mark.note,
                    takenAt = mark.markedAt,
                    latitude = mark.latitude,
                    longitude = mark.longitude,
                    speciesName = fieldMarkLabel(mark.markType),
                    scientificName = "Field Mark",
                    confirmed = true,
                )
            },
            selectedSighting = null,
            layerMode = layerMode,
            onSelect = {},
            onViewportChanged = {},
            routeSegments = tracking.routeSegments,
            currentPoint = tracking.currentPoint,
            followCurrentPoint = followPosition,
            selectedTrailIds = selectedTrailIds,
            modifier = Modifier.fillMaxSize(),
        )

        Box(
            Modifier
                .fillMaxWidth()
                .height(176.dp)
                .background(
                    Brush.verticalGradient(
                        listOf(Color(0xF2183A2D), Color(0xB8183A2D), Color.Transparent),
                    ),
                ),
        )

        TrackingTopBar(
            tracking = tracking,
            layerMode = layerMode,
            onBack = onBack,
            onToggleLayer = {
                layerMode = if (layerMode == MapLayerMode.Trail) MapLayerMode.Satellite else MapLayerMode.Trail
            },
            modifier = Modifier.align(Alignment.TopCenter),
        )

        FilledIconButton(
            onClick = { followPosition = !followPosition },
            colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(
                containerColor = if (followPosition) Trail else Color(0xEFFFFCF3),
                contentColor = if (followPosition) Paper else Moss,
            ),
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .navigationBarsPadding()
                .padding(end = 16.dp, bottom = 278.dp),
        ) {
            Icon(
                Icons.Rounded.MyLocation,
                contentDescription = if (followPosition) "Stop following my location" else "Follow my location",
            )
        }

        TrackingControls(
            tracking = tracking,
            onPause = onPause,
            onResume = onResume,
            onRequestEnd = { confirmEnd = true },
            onMark = { markDialogOpen = true },
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }

    if (markDialogOpen) {
        FieldMarkDialog(
            onDismiss = { markDialogOpen = false },
            onSave = { type, note ->
                markDialogOpen = false
                onAddFieldMark(type, note)
            },
        )
    }

    if (confirmEnd) {
        AlertDialog(
            onDismissRequest = { if (!tracking.isBusy) confirmEnd = false },
            icon = { Icon(Icons.Rounded.Stop, contentDescription = null, tint = Trail) },
            title = { Text("End this hike?") },
            text = {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        if (tracking.pointCount < 2) {
                            "GPS has not captured enough points for a route. The hike will still be saved with its active time and a zero distance."
                        } else {
                            "Your route, active time, and distance will be saved as an Untitled hike. You can name it next."
                        },
                        textAlign = TextAlign.Center,
                    )
                    Text(
                        "${formatTrackingDuration(tracking.elapsedSeconds)}  ·  ${formatTrackingDistance(tracking.distanceMiles)}",
                        style = MaterialTheme.typography.titleMedium,
                        color = Moss,
                        modifier = Modifier.padding(top = 14.dp),
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmEnd = false
                        onEnd()
                    },
                    enabled = tracking.isPaused && !tracking.isBusy,
                ) {
                    Text("End hike", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                Row {
                    TextButton(
                        onClick = {
                            confirmEnd = false
                            onDiscard()
                        },
                        enabled = tracking.isPaused && !tracking.isBusy,
                    ) {
                        Text("Discard hike", color = MaterialTheme.colorScheme.error)
                    }
                    TextButton(onClick = { confirmEnd = false }, enabled = !tracking.isBusy) {
                        Text("Keep hiking")
                    }
                }
            },
        )
    }
}

@Composable
private fun TrackingTopBar(
    tracking: TrackingUiModel,
    layerMode: MapLayerMode,
    onBack: () -> Unit,
    onToggleLayer: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(start = 5.dp, end = 7.dp, top = 7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack) {
            Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Return to journal", tint = Paper)
        }
        Column(Modifier.weight(1f).padding(start = 2.dp)) {
            Text("HikeJournal", style = MaterialTheme.typography.titleMedium, color = Color(0xFFD6E0D3))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    if (tracking.gpsStatus == TrackingGpsUiStatus.Strong) Icons.Rounded.GpsFixed else Icons.Rounded.GpsNotFixed,
                    contentDescription = null,
                    tint = trackingGpsColor(tracking.gpsStatus),
                    modifier = Modifier.size(15.dp),
                )
                Spacer(Modifier.width(5.dp))
                Text(
                    trackingGpsLabel(tracking.gpsStatus, tracking.accuracyMeters),
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFFD6E0D3),
                )
            }
        }
        TextButton(onClick = onToggleLayer) {
            Icon(Icons.Rounded.Layers, contentDescription = null, tint = Paper, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(5.dp))
            Text(if (layerMode == MapLayerMode.Trail) "Satellite" else "Trail", color = Paper)
        }
    }
}

@Composable
private fun TrackingControls(
    tracking: TrackingUiModel,
    onPause: () -> Unit,
    onResume: () -> Unit,
    onRequestEnd: () -> Unit,
    onMark: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier
            .fillMaxWidth()
            .background(Color(0xF7183A2D))
            .navigationBarsPadding()
            .padding(horizontal = 20.dp, vertical = 18.dp),
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(20.dp)) {
            TrackingMetric(
                value = formatTrackingDuration(tracking.elapsedSeconds),
                label = "ACTIVE TIME",
                modifier = Modifier.weight(1f),
            )
            Box(Modifier.width(1.dp).height(60.dp).background(Color(0x5076916D)))
            TrackingMetric(
                value = formatTrackingDistance(tracking.distanceMiles),
                label = "DISTANCE",
                modifier = Modifier.weight(1f),
            )
        }

        tracking.error?.takeIf { it.isNotBlank() }?.let { error ->
            Text(
                error,
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFFF2B8AE),
                modifier = Modifier.padding(top = 8.dp),
            )
        }

        Button(
            onClick = onMark,
            enabled = !tracking.isBusy && tracking.currentPoint != null,
            modifier = Modifier.fillMaxWidth().padding(top = 14.dp).height(58.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Color(0xFFE7B868),
                contentColor = Moss,
            ),
            shape = RoundedCornerShape(5.dp),
        ) {
            Icon(Icons.Rounded.AddLocationAlt, contentDescription = null)
            Spacer(Modifier.width(9.dp))
            Text("MARK", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        }

        AnimatedContent(
            targetState = tracking.status,
            transitionSpec = {
                (fadeIn(tween(180)) + slideInVertically(tween(220)) { it / 3 }) togetherWith
                    (fadeOut(tween(130)) + slideOutVertically(tween(180)) { -it / 3 })
            },
            label = "tracking-control",
        ) { status ->
            when (status) {
                TrackingStatus.RECORDING -> Button(
                    onClick = onPause,
                    modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(54.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Trail, contentColor = Paper),
                    shape = RoundedCornerShape(5.dp),
                ) {
                    Icon(Icons.Rounded.Pause, contentDescription = null)
                    Spacer(Modifier.width(9.dp))
                    Text("Pause hike", style = MaterialTheme.typography.titleMedium)
                }
                TrackingStatus.PAUSED -> Column(Modifier.fillMaxWidth()) {
                    Button(
                        onClick = onResume,
                        modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(54.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Trail, contentColor = Paper),
                        shape = RoundedCornerShape(5.dp),
                    ) {
                        Icon(Icons.Rounded.PlayArrow, contentDescription = null)
                        Spacer(Modifier.width(9.dp))
                        Text("Resume hike", style = MaterialTheme.typography.titleMedium)
                    }
                    OutlinedButton(
                        onClick = onRequestEnd,
                        modifier = Modifier.fillMaxWidth().padding(top = 9.dp).height(48.dp),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = Paper),
                        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x99FFFCF3)),
                        shape = RoundedCornerShape(5.dp),
                    ) {
                        Icon(Icons.Rounded.Stop, contentDescription = null, modifier = Modifier.size(19.dp))
                        Spacer(Modifier.width(7.dp))
                        Text("End hike")
                    }
                }
                TrackingStatus.STARTING,
                TrackingStatus.FINALIZING,
                TrackingStatus.FINISHED -> Button(
                    onClick = {},
                    enabled = false,
                    modifier = Modifier.fillMaxWidth().padding(top = 16.dp).height(58.dp),
                    shape = RoundedCornerShape(5.dp),
                ) {
                    CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = Paper)
                    Spacer(Modifier.width(9.dp))
                    Text(if (status == TrackingStatus.FINALIZING) "Saving hike…" else "Starting GPS…")
                }
            }
        }

        AnimatedVisibility(
            visible = tracking.status == TrackingStatus.RECORDING,
            enter = fadeIn(),
            exit = fadeOut(),
        ) {
            Text(
                "Pause before ending · ${tracking.pointCount} GPS point${if (tracking.pointCount == 1) "" else "s"}",
                style = MaterialTheme.typography.labelSmall,
                color = Color(0xFFB7C8B5),
                modifier = Modifier.fillMaxWidth().padding(top = 9.dp),
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun FieldMarkDialog(
    onDismiss: () -> Unit,
    onSave: (String, String) -> Unit,
) {
    var selected by rememberSaveable { mutableStateOf("note") }
    var note by rememberSaveable { mutableStateOf("") }
    val types = listOf(
        "wildlife" to "Wildlife",
        "plant" to "Plant",
        "trail_condition" to "Trail",
        "water" to "Water",
        "campsite" to "Campsite",
        "hazard" to "Hazard",
        "note" to "Note",
    )
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Rounded.AddLocationAlt, contentDescription = null, tint = Trail) },
        title = { Text("Mark this place") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                types.chunked(2).forEach { row ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        row.forEach { (value, label) ->
                            if (selected == value) {
                                Button(
                                    onClick = { selected = value },
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(5.dp),
                                    colors = ButtonDefaults.buttonColors(containerColor = Trail),
                                ) { Text(label) }
                            } else {
                                OutlinedButton(
                                    onClick = { selected = value },
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(5.dp),
                                ) { Text(label) }
                            }
                        }
                        if (row.size == 1) Spacer(Modifier.weight(1f))
                    }
                }
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it.take(500) },
                    label = { Text("Optional note") },
                    minLines = 2,
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    "Saved with your current GPS position and synced when service returns.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(selected, note) }) { Text("Save mark") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

private fun fieldMarkLabel(markType: String): String = when (markType) {
    "wildlife" -> "Wildlife"
    "plant" -> "Plant"
    "trail_condition" -> "Trail condition"
    "water" -> "Water"
    "campsite" -> "Campsite"
    "hazard" -> "Hazard"
    else -> "Note"
}

@Composable
private fun TrackingMetric(value: String, label: String, modifier: Modifier = Modifier) {
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            value,
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.SemiBold,
            color = Paper,
            maxLines = 1,
        )
        Text(label, style = MaterialTheme.typography.labelSmall, color = Color(0xFFB7C8B5))
    }
}

internal fun formatTrackingDuration(totalSeconds: Long): String {
    val safe = totalSeconds.coerceAtLeast(0L)
    val hours = safe / 3_600L
    val minutes = (safe % 3_600L) / 60L
    val seconds = safe % 60L
    return if (hours > 0L) {
        String.format(Locale.US, "%d:%02d:%02d", hours, minutes, seconds)
    } else {
        String.format(Locale.US, "%02d:%02d", minutes, seconds)
    }
}

internal fun formatTrackingDistance(miles: Double): String =
    String.format(Locale.US, "%.2f mi", miles.takeIf { it.isFinite() }?.coerceAtLeast(0.0) ?: 0.0)

private fun trackingGpsLabel(status: TrackingGpsUiStatus, accuracyMeters: Double?): String = when (status) {
    TrackingGpsUiStatus.Searching -> "FINDING GPS"
    TrackingGpsUiStatus.Strong -> accuracyMeters?.let { "GPS · ±${it.toInt()} M" } ?: "GPS READY"
    TrackingGpsUiStatus.Weak -> accuracyMeters?.let { "WEAK GPS · ±${it.toInt()} M" } ?: "WEAK GPS"
    TrackingGpsUiStatus.Unavailable -> "GPS UNAVAILABLE"
}

private fun trackingGpsColor(status: TrackingGpsUiStatus): Color = when (status) {
    TrackingGpsUiStatus.Strong -> Color(0xFF9DCF91)
    TrackingGpsUiStatus.Searching -> Trail
    TrackingGpsUiStatus.Weak -> Color(0xFFE9B66E)
    TrackingGpsUiStatus.Unavailable -> Color(0xFFF2B8AE)
}

private fun trackingRecoveryMessage(reason: String?): String? = when (reason) {
    "device_restarted" -> "Your phone restarted, so this hike was restored paused. Resume when you are ready."
    "permission_revoked" -> "Location permission changed, so this hike was restored paused."
    "notification_permission_revoked" -> "Notification access changed, so this hike was restored paused."
    "location_disabled" -> "Device location was turned off, so this hike was restored paused."
    "service_interrupted", "finalization_interrupted" ->
        "Tracking was interrupted, but your saved route is safe. Resume or end the paused hike."
    else -> null
}

private const val METERS_PER_MILE = 1_609.344
