package com.hikejournal.app.ui

import android.app.Activity
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.net.Uri
import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.scaleIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.Image
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.IosShare
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.FileProvider
import androidx.core.content.res.ResourcesCompat
import androidx.core.graphics.createBitmap
import androidx.core.net.toUri
import coil.compose.AsyncImage
import com.hikejournal.app.R
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.RoutePoint
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.MossSoft
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.cos
import kotlin.math.min
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request

internal const val MAX_SOCIAL_CAROUSEL_ITEMS = 20

internal enum class HikeShareKeepsake(val label: String, val orderDescription: String) {
    FIRST("Keepsake first", "The trail keepsake shares first, followed by your selected photos."),
    LAST("Keepsake last", "Your selected photos share first, followed by the trail keepsake."),
    NONE("No keepsake", "Only your selected photos will be shared."),
    ;

    val includesKeepsake: Boolean get() = this != NONE
    val maximumPhotos: Int get() = MAX_SOCIAL_CAROUSEL_ITEMS - if (includesKeepsake) 1 else 0

    fun <T : Any> orderedItems(keepsake: T?, photos: List<T>): List<T> {
        val selected = photos.take(maximumPhotos)
        return when (this) {
            FIRST -> listOfNotNull(keepsake) + selected
            LAST -> selected + listOfNotNull(keepsake)
            NONE -> selected
        }
    }
}

internal data class ShareRoutePoint(val x: Float, val y: Float)

internal data class PreparedHikeShare(
    val uris: ArrayList<Uri>,
    val caption: String,
    val omittedPhotoCount: Int,
)

private data class HikeSharePhotoRef(val hikeId: String, val photoId: String)

private val shareHttpClient = OkHttpClient()

@Composable
internal fun HikeShareDialog(
    hike: Hike,
    sameDayHikes: List<Hike> = listOf(hike),
    onShareMultiple: () -> Unit = {},
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val availablePhotos = remember(hike.photos) {
        hike.photos.filter { !it.contentType.startsWith("video/", ignoreCase = true) && it.url.isNotBlank() }
    }
    var keepsake by remember(hike.id) { mutableStateOf(HikeShareKeepsake.FIRST) }
    var selectedIds by remember(hike.id) { mutableStateOf<List<String>>(emptyList()) }
    val maximumPhotos = keepsake.maximumPhotos
    val imageCount = selectedIds.size + if (keepsake.includesKeepsake) 1 else 0
    var preparing by remember(hike.id) { mutableStateOf(false) }
    var errorMessage by remember(hike.id) { mutableStateOf<String?>(null) }
    var satelliteMap by remember(hike.id) { mutableStateOf<Bitmap?>(null) }
    var satelliteLoading by remember(hike.id) { mutableStateOf(hike.routeSegments.isNotEmpty()) }
    var revealed by remember(hike.id) { mutableStateOf(false) }
    LaunchedEffect(hike.id) { revealed = true }
    LaunchedEffect(hike.id, hike.routeSegments) {
        if (hike.routeSegments.isEmpty()) return@LaunchedEffect
        satelliteLoading = true
        satelliteMap = captureSatelliteRouteMap(context, hike.routeSegments)
        satelliteLoading = false
    }

    val preview = remember(
        hike.id,
        hike.title,
        hike.hikeDate,
        hike.distanceMiles,
        hike.durationSeconds,
        hike.routeStartedAt,
        hike.locationName,
        hike.routeSegments,
        satelliteMap,
    ) {
        renderHikeShareCard(context, hike, satelliteMap, width = 540, height = 675)
    }
    val previewPresence by animateFloatAsState(
        targetValue = if (revealed) 1f else 0f,
        animationSpec = tween(480),
        label = "share-card-preview",
    )
    val navigationBarPadding = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()

    fun beginShare() {
        if (preparing || imageCount == 0) return
        preparing = true
        errorMessage = null
        val photosById = availablePhotos.associateBy(Photo::id)
        val shareKeepsake = keepsake
        val selectedPhotos = socialSharePhotos(selectedIds.mapNotNull(photosById::get), shareKeepsake)
        scope.launch {
            runCatching { prepareHikeShare(context, hike, selectedPhotos, satelliteMap, shareKeepsake) }
                .onSuccess { prepared ->
                    preparing = false
                    launchHikeShare(context, prepared)
                    if (prepared.omittedPhotoCount > 0) {
                        Toast.makeText(
                            context,
                            "${prepared.omittedPhotoCount} photo${if (prepared.omittedPhotoCount == 1) " was" else "s were"} unavailable; the rest are ready to share.",
                            Toast.LENGTH_LONG,
                        ).show()
                    }
                }
                .onFailure { error ->
                    preparing = false
                    errorMessage = error.message ?: "HikeJournal could not prepare these images."
                }
        }
    }

    Dialog(
        onDismissRequest = { if (!preparing) onDismiss() },
        properties = DialogProperties(
            dismissOnBackPress = !preparing,
            dismissOnClickOutside = false,
            usePlatformDefaultWidth = false,
            decorFitsSystemWindows = false,
        ),
    ) {
        Column(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        listOf(MossSoft, Moss, Color(0xFF10281F)),
                    )
                )
                .statusBarsPadding(),
        ) {
            Row(
                Modifier.fillMaxWidth().padding(start = 18.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("HIKEJOURNAL", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                    Text("Share your outing", style = MaterialTheme.typography.headlineMedium, color = Paper)
                }
                IconButton(onClick = onDismiss, enabled = !preparing) {
                    Icon(Icons.Rounded.Close, "Close share preview", tint = Paper)
                }
            }

            LazyVerticalGrid(
                columns = GridCells.Fixed(2),
                Modifier.weight(1f),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(
                    start = 18.dp,
                    end = 18.dp,
                    bottom = 22.dp,
                ),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item(key = "keepsake-choice", span = { GridItemSpan(maxLineSpan) }) {
                    Column(Modifier.fillMaxWidth().selectableGroup()) {
                        Text("TRAIL KEEPSAKE", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                        HikeShareKeepsake.entries.forEach { option ->
                            Row(
                                Modifier.fillMaxWidth().selectable(
                                    selected = keepsake == option,
                                    enabled = !preparing,
                                    role = Role.RadioButton,
                                    onClick = {
                                        keepsake = option
                                        selectedIds = selectedIds.take(option.maximumPhotos)
                                    },
                                ).heightIn(min = 48.dp).padding(vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                RadioButton(
                                    selected = keepsake == option,
                                    onClick = null,
                                    enabled = !preparing,
                                    colors = RadioButtonDefaults.colors(
                                        selectedColor = Trail,
                                        unselectedColor = Paper.copy(alpha = 0.7f),
                                    ),
                                )
                                Text(option.label, style = MaterialTheme.typography.bodyLarge, color = Paper,
                                    modifier = Modifier.padding(start = 10.dp))
                            }
                        }
                        Text(
                            "${keepsake.orderDescription} Choose up to $maximumPhotos photos. " +
                                "Adding a keepsake keeps your first 19 selections.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFD6E0D3),
                            modifier = Modifier.padding(bottom = 8.dp),
                        )
                    }
                }

                if (sameDayHikes.size > 1) {
                    item(key = "share-multiple-outings", span = { GridItemSpan(maxLineSpan) }) {
                        OutlinedButton(
                            onClick = onShareMultiple,
                            enabled = !preparing,
                            border = BorderStroke(1.dp, Color(0xFFF1BE79).copy(alpha = 0.85f)),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFFF1BE79)),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Icon(Icons.Rounded.IosShare, null, Modifier.size(18.dp), tint = Color(0xFFF1BE79))
                            Spacer(Modifier.width(8.dp))
                            Text(
                                "Combine ${sameDayHikes.size} outings from this day",
                                color = Color(0xFFF1BE79),
                            )
                        }
                    }
                }

                if (keepsake.includesKeepsake) {
                    item(key = "share-preview", span = { GridItemSpan(maxLineSpan) }) {
                        Box {
                            Image(
                                bitmap = preview.asImageBitmap(),
                                contentDescription = "Social card preview for ${hike.title}",
                                contentScale = ContentScale.Fit,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .aspectRatio(4f / 5f)
                                    .clip(RoundedCornerShape(8.dp))
                                    .border(1.dp, Color.White.copy(alpha = 0.2f), RoundedCornerShape(8.dp))
                                    .alpha(previewPresence)
                                    .scale(0.97f + previewPresence * 0.03f),
                            )
                            if (satelliteLoading) {
                                Row(
                                    Modifier
                                        .align(Alignment.TopEnd)
                                        .padding(10.dp)
                                        .background(Color(0xD9183A2D), RoundedCornerShape(5.dp))
                                        .padding(horizontal = 10.dp, vertical = 7.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    CircularProgressIndicator(Modifier.size(15.dp), color = Paper, strokeWidth = 2.dp)
                                    Text(
                                        "Loading satellite map",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = Paper,
                                        modifier = Modifier.padding(start = 7.dp),
                                    )
                                }
                            }
                        }
                    }

                    item(key = "share-copy", span = { GridItemSpan(maxLineSpan) }) {
                        AnimatedVisibility(
                            visible = revealed,
                            enter = fadeIn(tween(360, delayMillis = 100)) +
                                slideInVertically(tween(420, delayMillis = 100)) { it / 7 },
                        ) {
                            Column(Modifier.fillMaxWidth().padding(top = 9.dp, bottom = 8.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(Icons.Rounded.AutoAwesome, null, tint = Trail, modifier = Modifier.size(18.dp))
                                    Text(
                                        "TRAIL KEEPSAKE",
                                        style = MaterialTheme.typography.labelMedium,
                                        color = Color(0xFFF1BE79),
                                        modifier = Modifier.padding(start = 8.dp),
                                    )
                                }
                                Text(
                                    if (satelliteMap != null) {
                                        "Your route is layered over satellite imagery."
                                    } else {
                                        "Your map, date, time, and distance are already set."
                                    },
                                    style = MaterialTheme.typography.bodyLarge,
                                    color = Color(0xFFD6E0D3),
                                    modifier = Modifier.padding(top = 7.dp),
                                )
                            }
                        }
                    }
                }

                if (availablePhotos.isNotEmpty()) {
                    item(key = "photo-label", span = { GridItemSpan(maxLineSpan) }) {
                        Row(
                            Modifier.fillMaxWidth().padding(top = 8.dp),
                            verticalAlignment = Alignment.Bottom,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text("ADD HIKE PHOTOS", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                                Text("Choose up to $maximumPhotos", style = MaterialTheme.typography.titleLarge, color = Paper)
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                Text(
                                    "${selectedIds.size}/$maximumPhotos",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = Color(0xFFD6E0D3),
                                )
                                TextButton(
                                    onClick = {
                                        selectedIds = if (
                                            selectedIds.size == min(availablePhotos.size, maximumPhotos)
                                        ) {
                                            emptyList()
                                        } else {
                                            availablePhotos.take(maximumPhotos).map(Photo::id)
                                        }
                                    },
                                    enabled = !preparing,
                                ) {
                                    Text(
                                        if (selectedIds.size == min(availablePhotos.size, maximumPhotos)) {
                                            "Clear"
                                        } else {
                                            "Select all"
                                        },
                                        color = Color(0xFFF1BE79),
                                    )
                                }
                            }
                        }
                    }
                    items(availablePhotos, key = Photo::id) { photo ->
                        val selectedIndex = selectedIds.indexOf(photo.id).takeIf { it >= 0 }
                        val canSelect = selectedIndex != null || selectedIds.size < maximumPhotos
                        SharePhotoTile(
                            photo = photo,
                            selectionIndex = selectedIndex,
                            enabled = canSelect && !preparing,
                            onClick = {
                                selectedIds = if (selectedIndex != null) {
                                    selectedIds - photo.id
                                } else {
                                    (selectedIds + photo.id).take(maximumPhotos)
                                }
                            },
                        )
                    }
                    item(key = "photo-order", span = { GridItemSpan(maxLineSpan) }) {
                        Text(
                            "${keepsake.orderDescription} $imageCount of $MAX_SOCIAL_CAROUSEL_ITEMS images. Videos are excluded.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFB8C9BC),
                            modifier = Modifier.padding(top = 4.dp, bottom = 6.dp),
                        )
                    }
                }

                if (!keepsake.includesKeepsake && selectedIds.isEmpty()) {
                    item(key = "photo-required", span = { GridItemSpan(maxLineSpan) }) {
                        Text(
                            if (availablePhotos.isEmpty()) "This outing has no photos to share. Choose a keepsake to share its route."
                            else "Select at least one photo to share without a keepsake.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Paper,
                            modifier = Modifier.padding(vertical = 12.dp),
                        )
                    }
                }

                errorMessage?.let { message ->
                    item(key = "share-error", span = { GridItemSpan(maxLineSpan) }) {
                        Text(
                            message,
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color(0xFFFFD0C5),
                            modifier = Modifier.padding(vertical = 14.dp),
                        )
                    }
                }
            }

            Surface(color = Color(0xF2183A2D), shadowElevation = 12.dp) {
                Box(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp)
                        .padding(top = 13.dp, bottom = navigationBarPadding + 14.dp),
                ) {
                    Button(
                        onClick = ::beginShare,
                        enabled = !preparing && imageCount > 0,
                        colors = ButtonDefaults.buttonColors(containerColor = Trail, contentColor = Paper),
                        modifier = Modifier.fillMaxWidth().height(52.dp),
                    ) {
                        if (preparing) {
                            CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Rounded.IosShare, null, Modifier.size(19.dp))
                        }
                        Spacer(Modifier.width(8.dp))
                        Text(
                            if (preparing) {
                                "Preparing $imageCount images…"
                            } else {
                                "Share $imageCount image${if (imageCount == 1) "" else "s"}"
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
internal fun MultiHikeShareDialog(
    currentHike: Hike,
    sameDayHikes: List<Hike>,
    onLoadHike: suspend (Hike) -> Hike,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val outings = remember(currentHike.id, sameDayHikes) {
        (sameDayHikes + currentHike).distinctBy(Hike::id)
            .sortedWith(compareBy<Hike> { it.routeStartedAt.orEmpty() }.thenBy { it.title })
    }
    var hikesById by remember(currentHike.id) {
        mutableStateOf(outings.associateBy(Hike::id) + (currentHike.id to currentHike))
    }
    var selectedHikeIds by remember(currentHike.id) { mutableStateOf(listOf(currentHike.id)) }
    var loadedHikeIds by remember(currentHike.id) { mutableStateOf(setOf(currentHike.id)) }
    var loadingHikeIds by remember(currentHike.id) { mutableStateOf(emptySet<String>()) }
    var loadErrors by remember(currentHike.id) { mutableStateOf(emptyMap<String, String>()) }
    var selectedPhotoRefs by remember(currentHike.id) { mutableStateOf(emptyList<HikeSharePhotoRef>()) }
    var keepsake by remember(currentHike.id) { mutableStateOf(HikeShareKeepsake.FIRST) }
    var satelliteMaps by remember(currentHike.id) { mutableStateOf<Map<String, Bitmap?>>(emptyMap()) }
    var preparing by remember(currentHike.id) { mutableStateOf(false) }
    var errorMessage by remember(currentHike.id) { mutableStateOf<String?>(null) }

    val selectedHikes = selectedHikeIds.mapNotNull(hikesById::get)
    val cardCount = if (keepsake.includesKeepsake) selectedHikeIds.size else 0
    val maximumPhotos = (MAX_SOCIAL_CAROUSEL_ITEMS - cardCount).coerceAtLeast(0)
    val imageCount = cardCount + selectedPhotoRefs.size
    val routeKey = selectedHikes.map { it.id to it.routeSegments }

    LaunchedEffect(routeKey) {
        selectedHikes.filter { it.routeSegments.isNotEmpty() && it.id !in satelliteMaps }
            .forEach { hike ->
                satelliteMaps = satelliteMaps + (hike.id to null)
                satelliteMaps = satelliteMaps + (hike.id to captureSatelliteRouteMap(context, hike.routeSegments))
            }
    }
    LaunchedEffect(selectedHikeIds, keepsake) {
        if (selectedPhotoRefs.size > maximumPhotos) {
            selectedPhotoRefs = selectedPhotoRefs.take(maximumPhotos)
        }
    }

    fun loadHikeDetails(summary: Hike) {
        if (summary.id in loadedHikeIds || summary.id in loadingHikeIds) return
        loadingHikeIds = loadingHikeIds + summary.id
        loadErrors = loadErrors - summary.id
        scope.launch {
            runCatching { onLoadHike(summary) }
                .onSuccess { detail ->
                    hikesById = hikesById + (summary.id to detail)
                    loadedHikeIds = loadedHikeIds + summary.id
                }
                .onFailure { error ->
                    loadErrors = loadErrors + (summary.id to (error.message ?: "Could not load this outing."))
                }
            loadingHikeIds = loadingHikeIds - summary.id
        }
    }

    fun toggleHike(hike: Hike) {
        if (hike.id == currentHike.id || preparing) return
        if (hike.id in selectedHikeIds) {
            selectedHikeIds = selectedHikeIds - hike.id
            selectedPhotoRefs = selectedPhotoRefs.filterNot { it.hikeId == hike.id }
        } else {
            if (keepsake.includesKeepsake && selectedHikeIds.size >= MAX_SOCIAL_CAROUSEL_ITEMS) return
            selectedHikeIds = selectedHikeIds + hike.id
            loadHikeDetails(hike)
        }
    }

    fun beginShare() {
        if (preparing || selectedHikeIds.size < 2 || imageCount == 0) return
        if (selectedHikeIds.any { it !in loadedHikeIds || it in loadingHikeIds }) return
        preparing = true
        errorMessage = null
        val shareHikes = selectedHikes
        val photosByKey = shareHikes.flatMap { outing ->
            outing.photos.map { photo -> HikeSharePhotoRef(outing.id, photo.id) to photo }
        }.toMap()
        val sharePhotos = selectedPhotoRefs.mapNotNull(photosByKey::get)
        val shareMaps = satelliteMaps.toMap()
        scope.launch {
            runCatching {
                prepareMultiHikeShare(context, shareHikes, sharePhotos, shareMaps, keepsake)
            }.onSuccess { prepared ->
                preparing = false
                launchHikeShare(context, prepared)
                if (prepared.omittedPhotoCount > 0) {
                    Toast.makeText(
                        context,
                        "${prepared.omittedPhotoCount} photo${if (prepared.omittedPhotoCount == 1) " was" else "s were"} unavailable; the rest are ready to share.",
                        Toast.LENGTH_LONG,
                    ).show()
                }
            }.onFailure { error ->
                preparing = false
                errorMessage = error.message ?: "HikeJournal could not prepare these images."
            }
        }
    }

    val cardPreviews = remember(
        keepsake,
        selectedHikes.map { hike -> listOf(hike.id, hike.title, hike.hikeDate, hike.distanceMiles, hike.routeSegments) },
        satelliteMaps,
    ) {
        if (!keepsake.includesKeepsake) emptyList() else selectedHikes.map { hike ->
            hike.id to renderHikeShareCard(context, hike, satelliteMaps[hike.id], width = 270, height = 338)
        }
    }
    val navigationBarPadding = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val allDetailsLoaded = selectedHikeIds.all { it in loadedHikeIds } && loadingHikeIds.isEmpty()
    val canShare = selectedHikeIds.size >= 2 && allDetailsLoaded && imageCount > 0 && !preparing

    Dialog(
        onDismissRequest = { if (!preparing) onDismiss() },
        properties = DialogProperties(
            dismissOnBackPress = !preparing,
            dismissOnClickOutside = false,
            usePlatformDefaultWidth = false,
            decorFitsSystemWindows = false,
        ),
    ) {
        Column(
            Modifier.fillMaxSize()
                .background(Brush.verticalGradient(listOf(MossSoft, Moss, Color(0xFF10281F))))
                .statusBarsPadding(),
        ) {
            Row(
                Modifier.fillMaxWidth().padding(start = 18.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("HIKEJOURNAL", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                    Text("Share your day", style = MaterialTheme.typography.headlineMedium, color = Paper)
                }
                IconButton(onClick = onDismiss, enabled = !preparing) {
                    Icon(Icons.Rounded.Close, "Close multi-hike share", tint = Paper)
                }
            }

            LazyVerticalGrid(
                columns = GridCells.Fixed(2),
                Modifier.weight(1f),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(start = 18.dp, end = 18.dp, bottom = 22.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item(key = "outing-picker-title", span = { GridItemSpan(maxLineSpan) }) {
                    Column(Modifier.fillMaxWidth().padding(top = 5.dp)) {
                        Text("OUTINGS FROM ${currentHike.hikeDate.take(10)}", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                        Text("Choose the hikes to share together", style = MaterialTheme.typography.titleLarge, color = Paper)
                        Text(
                            "Include at least two. Their photos and keepsakes share as one carousel.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFD6E0D3),
                            modifier = Modifier.padding(top = 3.dp),
                        )
                    }
                }
                items(outings, key = { "outing-${it.id}" }, span = { GridItemSpan(maxLineSpan) }) { hike ->
                    val selected = hike.id in selectedHikeIds
                    Row(
                        Modifier.fillMaxWidth()
                            .clickable(
                                enabled = hike.id != currentHike.id && !preparing &&
                                    (selected || !keepsake.includesKeepsake || selectedHikeIds.size < MAX_SOCIAL_CAROUSEL_ITEMS),
                            ) { toggleHike(hike) }
                            .padding(vertical = 5.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Checkbox(
                            checked = selected,
                            onCheckedChange = null,
                            enabled = hike.id != currentHike.id && !preparing &&
                                (selected || !keepsake.includesKeepsake || selectedHikeIds.size < MAX_SOCIAL_CAROUSEL_ITEMS),
                        )
                        Column(Modifier.weight(1f).padding(start = 8.dp)) {
                            Text(hike.title.ifBlank { "Untitled hike" }, style = MaterialTheme.typography.titleMedium, color = Paper)
                            Text(
                                buildString {
                                    append(hikeShareDateTime(hike))
                                    val place = hike.primaryLocationName.ifBlank { hike.locationName }
                                    if (place.isNotBlank()) append(" · $place")
                                    if (hike.id == currentHike.id) append(" · Current outing")
                                },
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFD6E0D3),
                            )
                        }
                        if (hike.id in loadingHikeIds) {
                            CircularProgressIndicator(Modifier.padding(start = 8.dp).size(19.dp), color = Trail, strokeWidth = 2.dp)
                        }
                    }
                    loadErrors[hike.id]?.let { message ->
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Text(message, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, color = Color(0xFFFFD0C5))
                            TextButton(onClick = { loadHikeDetails(hike) }, enabled = !preparing) { Text("Retry") }
                        }
                    }
                    HorizontalShareDivider()
                }

                item(key = "multi-keepsake-choice", span = { GridItemSpan(maxLineSpan) }) {
                    Column(Modifier.fillMaxWidth().selectableGroup().padding(top = 8.dp)) {
                        Text("TRAIL KEEPSAKE CARDS", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                        HikeShareKeepsake.entries.forEach { option ->
                            val canChooseOption = !preparing &&
                                (option == HikeShareKeepsake.NONE || selectedHikeIds.size <= MAX_SOCIAL_CAROUSEL_ITEMS)
                            val label = when (option) {
                                HikeShareKeepsake.FIRST -> "Keepsake cards first"
                                HikeShareKeepsake.LAST -> "Keepsake cards last"
                                HikeShareKeepsake.NONE -> "No keepsake cards"
                            }
                            Row(
                                Modifier.fillMaxWidth().selectable(
                                    selected = keepsake == option,
                                    enabled = canChooseOption,
                                    role = Role.RadioButton,
                                    onClick = { keepsake = option },
                                ).heightIn(min = 48.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                RadioButton(
                                    selected = keepsake == option,
                                    onClick = null,
                                    enabled = canChooseOption,
                                    colors = RadioButtonDefaults.colors(selectedColor = Trail, unselectedColor = Paper.copy(alpha = 0.7f)),
                                )
                                Text(label, style = MaterialTheme.typography.bodyLarge, color = Paper, modifier = Modifier.padding(start = 10.dp))
                            }
                        }
                        Text(
                            "Each selected hike gets its own card. The cards go before or after all selected photos. " +
                                "Cards count toward the $MAX_SOCIAL_CAROUSEL_ITEMS-image limit.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFD6E0D3),
                            modifier = Modifier.padding(bottom = 5.dp),
                        )
                        if (selectedHikeIds.size > MAX_SOCIAL_CAROUSEL_ITEMS) {
                            Text(
                                "Select 20 or fewer hikes to add a keepsake card for each one.",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFFFD0C5),
                                modifier = Modifier.padding(bottom = 5.dp),
                            )
                        }
                    }
                }

                if (cardPreviews.isNotEmpty()) {
                    item(key = "multi-card-previews", span = { GridItemSpan(maxLineSpan) }) {
                        Column {
                            Text("YOUR KEEPSAKE CARDS", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                            Row(
                                Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(top = 7.dp),
                                horizontalArrangement = Arrangement.spacedBy(9.dp),
                            ) {
                                cardPreviews.forEach { (hikeId, bitmap) ->
                                    val title = hikesById[hikeId]?.title.orEmpty()
                                    Column(Modifier.width(158.dp)) {
                                        Image(
                                            bitmap = bitmap.asImageBitmap(),
                                            contentDescription = "Trail keepsake for $title",
                                            contentScale = ContentScale.Fit,
                                            modifier = Modifier.fillMaxWidth().aspectRatio(4f / 5f)
                                                .clip(RoundedCornerShape(6.dp))
                                                .border(1.dp, Color.White.copy(alpha = 0.2f), RoundedCornerShape(6.dp)),
                                        )
                                        Text(title, style = MaterialTheme.typography.labelMedium, color = Paper, maxLines = 1)
                                    }
                                }
                            }
                        }
                    }
                }

                item(key = "multi-photo-label", span = { GridItemSpan(maxLineSpan) }) {
                    Column(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                        Text("ADD PHOTOS", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                        Text("${selectedPhotoRefs.size} of $maximumPhotos photos · $imageCount of $MAX_SOCIAL_CAROUSEL_ITEMS images", style = MaterialTheme.typography.titleLarge, color = Paper)
                    }
                }

                selectedHikes.forEach { outing ->
                    val detailLoading = outing.id in loadingHikeIds || outing.id !in loadedHikeIds
                    val availablePhotos = outing.photos.filter {
                        !it.contentType.startsWith("video/", ignoreCase = true) && it.url.isNotBlank()
                    }
                    val outingRefs = selectedPhotoRefs.filter { it.hikeId == outing.id }
                    item(key = "multi-photo-heading-${outing.id}", span = { GridItemSpan(maxLineSpan) }) {
                        Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(outing.title.ifBlank { "Untitled hike" }, style = MaterialTheme.typography.titleLarge, color = Paper)
                                Text("${outingRefs.size}/${availablePhotos.size} photos selected", style = MaterialTheme.typography.bodySmall, color = Color(0xFFD6E0D3))
                            }
                            if (availablePhotos.isNotEmpty()) {
                                TextButton(
                                    onClick = {
                                        val allSelected = availablePhotos.all { photo ->
                                            HikeSharePhotoRef(outing.id, photo.id) in selectedPhotoRefs
                                        }
                                        selectedPhotoRefs = if (allSelected) {
                                            selectedPhotoRefs.filterNot { it.hikeId == outing.id }
                                        } else {
                                            val remaining = (maximumPhotos - selectedPhotoRefs.size).coerceAtLeast(0)
                                            selectedPhotoRefs + availablePhotos
                                                .filterNot { photo -> HikeSharePhotoRef(outing.id, photo.id) in selectedPhotoRefs }
                                                .take(remaining)
                                                .map { HikeSharePhotoRef(outing.id, it.id) }
                                        }
                                    },
                                    enabled = !preparing && (outingRefs.isNotEmpty() || selectedPhotoRefs.size < maximumPhotos),
                                ) {
                                    Text(if (outingRefs.size == availablePhotos.size) "Clear" else "Select available", color = Color(0xFFF1BE79))
                                }
                            }
                        }
                    }
                    if (detailLoading) {
                        item(key = "multi-photo-loading-${outing.id}", span = { GridItemSpan(maxLineSpan) }) {
                            Text("Loading photos and route…", style = MaterialTheme.typography.bodySmall, color = Color(0xFFD6E0D3))
                        }
                    } else if (availablePhotos.isEmpty()) {
                        item(key = "multi-photo-empty-${outing.id}", span = { GridItemSpan(maxLineSpan) }) {
                            Text("No photos are available for this outing.", style = MaterialTheme.typography.bodySmall, color = Color(0xFFD6E0D3))
                        }
                    } else {
                        items(availablePhotos, key = { photo -> "multi-photo-${outing.id}-${photo.id}" }) { photo ->
                            val ref = HikeSharePhotoRef(outing.id, photo.id)
                            val selectedIndex = selectedPhotoRefs.indexOf(ref).takeIf { it >= 0 }
                            SharePhotoTile(
                                photo = photo,
                                selectionIndex = selectedIndex,
                                enabled = !preparing && (selectedIndex != null || selectedPhotoRefs.size < maximumPhotos),
                                onClick = {
                                    selectedPhotoRefs = if (selectedIndex != null) {
                                        selectedPhotoRefs - ref
                                    } else if (selectedPhotoRefs.size < maximumPhotos) {
                                        selectedPhotoRefs + ref
                                    } else {
                                        selectedPhotoRefs
                                    }
                                },
                            )
                        }
                    }
                }

                if (selectedHikeIds.size < 2) {
                    item(key = "multi-share-required", span = { GridItemSpan(maxLineSpan) }) {
                        Text("Choose another outing to make a multi-hike share.", style = MaterialTheme.typography.bodyMedium, color = Paper, modifier = Modifier.padding(vertical = 10.dp))
                    }
                }
                errorMessage?.let { message ->
                    item(key = "multi-share-error", span = { GridItemSpan(maxLineSpan) }) {
                        Text(message, style = MaterialTheme.typography.bodyMedium, color = Color(0xFFFFD0C5), modifier = Modifier.padding(vertical = 14.dp))
                    }
                }
            }

            Surface(color = Color(0xF2183A2D), shadowElevation = 12.dp) {
                Box(
                    Modifier.fillMaxWidth().padding(horizontal = 20.dp)
                        .padding(top = 13.dp, bottom = navigationBarPadding + 14.dp),
                ) {
                    Button(
                        onClick = ::beginShare,
                        enabled = canShare,
                        colors = ButtonDefaults.buttonColors(containerColor = Trail, contentColor = Paper),
                        modifier = Modifier.fillMaxWidth().height(52.dp),
                    ) {
                        if (preparing) {
                            CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Rounded.IosShare, null, Modifier.size(19.dp))
                        }
                        Spacer(Modifier.width(8.dp))
                        Text(
                            when {
                                preparing -> "Preparing $imageCount images…"
                                selectedHikeIds.size < 2 -> "Choose another outing"
                                !allDetailsLoaded -> "Loading outings…"
                                imageCount == 0 -> "Choose images to share"
                                else -> "Share $imageCount images from ${selectedHikeIds.size} hikes"
                            },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun HorizontalShareDivider() {
    androidx.compose.material3.HorizontalDivider(color = Color.White.copy(alpha = 0.18f))
}

@Composable
private fun SharePhotoTile(
    photo: Photo,
    selectionIndex: Int?,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    Box(
        Modifier
            .fillMaxWidth()
            .aspectRatio(0.82f)
            .clip(RoundedCornerShape(6.dp))
            .clickable(enabled = enabled, onClick = onClick)
            .alpha(if (enabled || selectionIndex != null) 1f else 0.42f)
            .border(
                width = if (selectionIndex != null) 4.dp else 1.dp,
                color = if (selectionIndex != null) Trail else Color.White.copy(alpha = 0.24f),
                shape = RoundedCornerShape(6.dp),
            ),
    ) {
        AsyncImage(
            model = photo.url,
            contentDescription = photo.caption.ifBlank { "Hike photo" },
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize().background(MossSoft),
        )
        AnimatedVisibility(
            visible = selectionIndex != null,
            modifier = Modifier.align(Alignment.TopEnd),
            enter = fadeIn(tween(140)) + scaleIn(tween(180), initialScale = 0.65f),
        ) {
            Box(
                Modifier.padding(9.dp).size(31.dp).background(Trail, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    "${(selectionIndex ?: 0) + 1}",
                    style = MaterialTheme.typography.labelLarge,
                    color = Paper,
                )
            }
        }
    }
}

internal fun socialSharePhotos(
    photos: List<Photo>,
    keepsake: HikeShareKeepsake = HikeShareKeepsake.FIRST,
): List<Photo> = photos.filter {
    !it.contentType.startsWith("video/", ignoreCase = true) && it.url.isNotBlank()
}.take(keepsake.maximumPhotos)

internal fun projectShareRoute(
    routeSegments: List<List<RoutePoint>>,
    width: Float,
    height: Float,
    padding: Float,
): List<List<ShareRoutePoint>> {
    if (width <= 0f || height <= 0f) return emptyList()
    val usable = routeSegments.map { segment ->
        segment.filter { it.latitude.isFinite() && it.longitude.isFinite() }
    }.filter(List<RoutePoint>::isNotEmpty)
    val all = usable.flatten()
    if (all.isEmpty()) return emptyList()

    val centerLatitude = all.map(RoutePoint::latitude).average()
    val longitudeScale = cos(Math.toRadians(centerLatitude)).coerceAtLeast(0.01)
    fun projectedLongitude(point: RoutePoint): Double = point.longitude * longitudeScale

    val minX = all.minOf(::projectedLongitude)
    val maxX = all.maxOf(::projectedLongitude)
    val minY = all.minOf(RoutePoint::latitude)
    val maxY = all.maxOf(RoutePoint::latitude)
    val sourceWidth = (maxX - minX).coerceAtLeast(0.000001)
    val sourceHeight = (maxY - minY).coerceAtLeast(0.000001)
    val availableWidth = (width - padding * 2f).coerceAtLeast(1f)
    val availableHeight = (height - padding * 2f).coerceAtLeast(1f)
    val scale = min(availableWidth / sourceWidth, availableHeight / sourceHeight)
    val centerX = (minX + maxX) / 2.0
    val centerY = (minY + maxY) / 2.0

    return usable.map { segment ->
        segment.map { point ->
            ShareRoutePoint(
                x = (width / 2f + (projectedLongitude(point) - centerX) * scale).toFloat(),
                y = (height / 2f - (point.latitude - centerY) * scale).toFloat(),
            )
        }
    }
}

internal fun hikeShareDateTime(hike: Hike, zoneId: ZoneId = ZoneId.systemDefault()): String {
    val formatter = DateTimeFormatter.ofPattern("EEEE, MMMM d · h:mm a", Locale.US)
    val localDateTime = hike.routeStartedAt?.takeIf(String::isNotBlank)?.let { raw ->
        runCatching { Instant.parse(raw).atZone(zoneId).toLocalDateTime() }.getOrNull()
            ?: runCatching { OffsetDateTime.parse(raw).atZoneSameInstant(zoneId).toLocalDateTime() }.getOrNull()
            ?: runCatching { LocalDateTime.parse(raw) }.getOrNull()
    }
    if (localDateTime != null) return localDateTime.format(formatter)
    return runCatching {
        LocalDate.parse(hike.hikeDate.take(10))
            .format(DateTimeFormatter.ofPattern("EEEE, MMMM d", Locale.US))
    }.getOrDefault(hike.hikeDate)
}

internal fun hikeShareDistance(hike: Hike): String =
    hike.distanceMiles?.let { String.format(Locale.US, "%.2f", it) } ?: "—"

internal fun hikeShareDuration(durationSeconds: Long?): String {
    if (durationSeconds == null) return "—"
    val safe = durationSeconds.coerceAtLeast(0)
    val hours = safe / 3_600
    val minutes = (safe % 3_600) / 60
    val seconds = safe % 60
    return if (hours > 0) {
        String.format(Locale.US, "%d:%02d:%02d", hours, minutes, seconds)
    } else {
        String.format(Locale.US, "%d:%02d", minutes, seconds)
    }
}

internal fun renderHikeShareCard(
    context: Context,
    hike: Hike,
    satelliteMap: Bitmap? = null,
    width: Int = 1080,
    height: Int = 1350,
): Bitmap {
    val safeWidth = width.coerceAtLeast(320)
    val safeHeight = height.coerceAtLeast(400)
    val bitmap = createBitmap(safeWidth, safeHeight)
    val canvas = Canvas(bitmap)
    val sx = safeWidth / 1080f
    val sy = safeHeight / 1350f
    val bodyFont = ResourcesCompat.getFont(context, R.font.source_sans_3) ?: Typeface.SANS_SERIF
    val displayFont = ResourcesCompat.getFont(context, R.font.cormorant_garamond) ?: Typeface.SERIF
    val paint = Paint(Paint.ANTI_ALIAS_FLAG)

    paint.shader = LinearGradient(
        0f,
        0f,
        0f,
        safeHeight.toFloat(),
        intArrayOf(0xFF315844.toInt(), 0xFF183A2D.toInt(), 0xFF10281F.toInt()),
        floatArrayOf(0f, 0.58f, 1f),
        Shader.TileMode.CLAMP,
    )
    canvas.drawRect(0f, 0f, safeWidth.toFloat(), safeHeight.toFloat(), paint)
    paint.shader = null

    drawTopographicTexture(canvas, paint, safeWidth.toFloat(), 790f * sy, sx, sy)

    paint.color = 0xFFF1BE79.toInt()
    paint.typeface = Typeface.create(bodyFont, Typeface.BOLD)
    paint.textSize = 24f * sx
    paint.letterSpacing = 0.12f
    canvas.drawText("HIKEJOURNAL", 72f * sx, 76f * sy, paint)
    paint.letterSpacing = 0f

    paint.color = 0xFFFFFCF3.toInt()
    paint.typeface = Typeface.create(displayFont, Typeface.BOLD)
    paint.textSize = 55f * sx
    canvas.drawText("Trail keepsake", 72f * sx, 132f * sy, paint)

    val mapLeft = 56f * sx
    val mapTop = 170f * sy
    val mapWidth = safeWidth - 112f * sx
    val mapHeight = 555f * sy
    val mapBounds = RectF(mapLeft, mapTop, mapLeft + mapWidth, mapTop + mapHeight)
    val projected = if (satelliteMap == null) {
        projectShareRoute(
            routeSegments = hike.routeSegments,
            width = mapWidth,
            height = mapHeight,
            padding = 48f * sx,
        )
    } else {
        emptyList()
    }
    if (satelliteMap != null) {
        canvas.drawBitmap(satelliteMap, null, mapBounds, paint)
        paint.shader = LinearGradient(
            0f,
            mapTop + mapHeight * 0.54f,
            0f,
            mapTop + mapHeight,
            0x00000000,
            0xAA10281F.toInt(),
            Shader.TileMode.CLAMP,
        )
        canvas.drawRect(mapBounds, paint)
        paint.shader = null
        paint.color = 0xE6FFFCF3.toInt()
        paint.typeface = Typeface.create(bodyFont, Typeface.BOLD)
        paint.textSize = 18f * sx
        paint.letterSpacing = 0.04f
        canvas.drawText(
            "SOURCES: ESRI, MAXAR, EARTHSTAR GEOGRAPHICS,",
            mapLeft + 18f * sx,
            mapTop + mapHeight - 40f * sy,
            paint,
        )
        canvas.drawText(
            "AND THE GIS USER COMMUNITY",
            mapLeft + 18f * sx,
            mapTop + mapHeight - 17f * sy,
            paint,
        )
        paint.letterSpacing = 0f
    } else if (projected.isNotEmpty()) {
        paint.style = Paint.Style.STROKE
        paint.strokeCap = Paint.Cap.ROUND
        paint.strokeJoin = Paint.Join.ROUND
        projected.forEach { segment ->
            if (segment.isEmpty()) return@forEach
            val routePath = Path().apply {
                moveTo(mapLeft + segment.first().x, mapTop + segment.first().y)
                segment.drop(1).forEach { point -> lineTo(mapLeft + point.x, mapTop + point.y) }
            }
            paint.color = 0x5510271F
            paint.strokeWidth = 18f * sx
            canvas.drawPath(routePath, paint)
            paint.color = 0xFFD17D42.toInt()
            paint.strokeWidth = 9f * sx
            canvas.drawPath(routePath, paint)
        }
        paint.style = Paint.Style.FILL
        val start = projected.first().first()
        val end = projected.last().last()
        paint.color = 0xFFFFFCF3.toInt()
        canvas.drawCircle(mapLeft + start.x, mapTop + start.y, 15f * sx, paint)
        paint.color = 0xFF183A2D.toInt()
        canvas.drawCircle(mapLeft + start.x, mapTop + start.y, 7f * sx, paint)
        paint.color = 0xFFD17D42.toInt()
        canvas.drawCircle(mapLeft + end.x, mapTop + end.y, 15f * sx, paint)
    } else {
        paint.color = 0x99D6E0D3.toInt()
        paint.typeface = Typeface.create(bodyFont, Typeface.BOLD)
        paint.textSize = 22f * sx
        paint.textAlign = Paint.Align.CENTER
        paint.letterSpacing = 0.1f
        canvas.drawText("NO RECORDED ROUTE", safeWidth / 2f, (mapTop + mapHeight / 2f), paint)
        paint.textAlign = Paint.Align.LEFT
        paint.letterSpacing = 0f
    }

    paint.color = 0x33FFFFFF
    canvas.drawRect(72f * sx, 774f * sy, safeWidth - 72f * sx, 776f * sy, paint)

    val eyebrow = hike.locationName.takeIf(String::isNotBlank)?.uppercase(Locale.US) ?: "FIELD JOURNAL"
    paint.color = 0xFFF1BE79.toInt()
    paint.typeface = Typeface.create(bodyFont, Typeface.BOLD)
    paint.textSize = 23f * sx
    paint.letterSpacing = 0.1f
    canvas.drawText(eyebrow.take(52), 72f * sx, 835f * sy, paint)
    paint.letterSpacing = 0f

    paint.color = 0xFFFFFCF3.toInt()
    paint.typeface = Typeface.create(displayFont, Typeface.BOLD)
    paint.textSize = 72f * sx
    val titleLines = textLines(
        text = hike.title.ifBlank { "A day on the trail" },
        paint = paint,
        maxWidth = safeWidth - 144f * sx,
        maxLines = 2,
    )
    val titleBaseline = 918f * sy
    titleLines.forEachIndexed { index, line ->
        canvas.drawText(line, 72f * sx, titleBaseline + index * 70f * sy, paint)
    }
    val titleBottom = titleBaseline + (titleLines.size - 1).coerceAtLeast(0) * 70f * sy

    paint.color = 0xFFD6E0D3.toInt()
    paint.typeface = Typeface.create(bodyFont, Typeface.NORMAL)
    paint.textSize = 28f * sx
    canvas.drawText(hikeShareDateTime(hike), 72f * sx, titleBottom + 58f * sy, paint)

    val metricsTop = 1128f * sy
    paint.color = 0x33FFFFFF
    canvas.drawRect(72f * sx, metricsTop - 34f * sy, safeWidth - 72f * sx, metricsTop - 32f * sy, paint)

    paint.color = 0xFFFFFCF3.toInt()
    paint.typeface = Typeface.create(bodyFont, Typeface.BOLD)
    paint.textSize = 66f * sx
    canvas.drawText(hikeShareDistance(hike), 72f * sx, metricsTop + 55f * sy, paint)
    canvas.drawText(hikeShareDuration(hike.durationSeconds), 590f * sx, metricsTop + 55f * sy, paint)

    paint.color = 0xFFB8C9BC.toInt()
    paint.typeface = Typeface.create(bodyFont, Typeface.BOLD)
    paint.textSize = 21f * sx
    paint.letterSpacing = 0.11f
    canvas.drawText("MILES", 72f * sx, metricsTop + 92f * sy, paint)
    canvas.drawText("ACTIVE TIME", 590f * sx, metricsTop + 92f * sy, paint)
    paint.letterSpacing = 0f

    drawSpark(canvas, 72f * sx, 1290f * sy, 13f * sx, paint)
    paint.color = 0xFFD6E0D3.toInt()
    paint.typeface = Typeface.create(bodyFont, Typeface.NORMAL)
    paint.textSize = 22f * sx
    canvas.drawText("Field notes from HikeJournal", 99f * sx, 1298f * sy, paint)
    return bitmap
}

private fun drawTopographicTexture(
    canvas: Canvas,
    paint: Paint,
    width: Float,
    height: Float,
    sx: Float,
    sy: Float,
) {
    paint.style = Paint.Style.STROKE
    paint.strokeWidth = 2f * sx
    repeat(8) { index ->
        val inset = (index * 54f - 95f) * sx
        paint.color = if (index % 2 == 0) 0x1FFFFFFF else 0x1676916D
        canvas.drawOval(
            RectF(
                -140f * sx + inset,
                120f * sy + inset * 0.32f,
                width * 0.76f + inset,
                height * 0.94f - inset * 0.18f,
            ),
            paint,
        )
    }
    repeat(6) { index ->
        val inset = index * 62f * sx
        paint.color = 0x16FFFFFF
        canvas.drawOval(
            RectF(
                width * 0.56f - inset * 0.18f,
                -190f * sy + inset,
                width * 1.18f + inset * 0.12f,
                height * 0.54f + inset,
            ),
            paint,
        )
    }
    paint.style = Paint.Style.FILL
}

private fun drawSpark(canvas: Canvas, cx: Float, cy: Float, radius: Float, paint: Paint) {
    val path = Path().apply {
        moveTo(cx, cy - radius)
        lineTo(cx + radius * 0.28f, cy - radius * 0.28f)
        lineTo(cx + radius, cy)
        lineTo(cx + radius * 0.28f, cy + radius * 0.28f)
        lineTo(cx, cy + radius)
        lineTo(cx - radius * 0.28f, cy + radius * 0.28f)
        lineTo(cx - radius, cy)
        lineTo(cx - radius * 0.28f, cy - radius * 0.28f)
        close()
    }
    paint.color = 0xFFD17D42.toInt()
    paint.style = Paint.Style.FILL
    canvas.drawPath(path, paint)
}

private fun textLines(text: String, paint: Paint, maxWidth: Float, maxLines: Int): List<String> {
    val words = text.trim().split(Regex("\\s+")).filter(String::isNotBlank)
    if (words.isEmpty()) return listOf("")
    val lines = mutableListOf<String>()
    var current = ""
    words.forEach { word ->
        val candidate = if (current.isBlank()) word else "$current $word"
        if (paint.measureText(candidate) <= maxWidth || current.isBlank()) {
            current = candidate
        } else if (lines.size < maxLines - 1) {
            lines += current
            current = word
        } else {
            current = "$current $word"
        }
    }
    if (current.isNotBlank()) lines += current
    val limited = lines.take(maxLines).toMutableList()
    if (lines.size > maxLines || limited.lastOrNull()?.let { paint.measureText(it) > maxWidth } == true) {
        var last = limited.lastOrNull().orEmpty()
        while (last.isNotEmpty() && paint.measureText("$last…") > maxWidth) last = last.dropLast(1)
        limited[limited.lastIndex] = last.trimEnd() + "…"
    }
    return limited
}

internal suspend fun prepareHikeShare(
    context: Context,
    hike: Hike,
    photos: List<Photo>,
    satelliteMap: Bitmap?,
    keepsake: HikeShareKeepsake,
): PreparedHikeShare {
    val resolvedSatelliteMap = if (keepsake.includesKeepsake) {
        satelliteMap ?: captureSatelliteRouteMap(context, hike.routeSegments)
    } else null
    return withContext(Dispatchers.IO) {
        val shareDirectory = File(context.cacheDir, "shared_hikes").apply { mkdirs() }
        shareDirectory.listFiles().orEmpty()
            .filter { System.currentTimeMillis() - it.lastModified() > 24L * 60L * 60L * 1_000L }
            .forEach(File::delete)

        val safeHikeId = hike.id.replace(Regex("[^A-Za-z0-9._-]"), "-").take(64).ifBlank { "outing" }
        val cardUri = if (keepsake.includesKeepsake) {
            val cardFile = File(shareDirectory, "HikeJournal-$safeHikeId.jpg")
            FileOutputStream(cardFile).use { output ->
                check(
                    renderHikeShareCard(context, hike, resolvedSatelliteMap)
                        .compress(Bitmap.CompressFormat.JPEG, 94, output),
                ) {
                    "HikeJournal could not save the trail card."
                }
            }
            FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", cardFile)
        } else null
        val cachedPhotos = coroutineScope {
            socialSharePhotos(photos, keepsake).mapIndexed { index, photo ->
                async {
                    runCatching { cacheSharedPhoto(context, photo, shareDirectory, safeHikeId, index) }
                        .getOrNull()
                }
            }.awaitAll()
        }
        val photoUris = cachedPhotos.filterNotNull().map { file ->
            FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        }
        val uris = ArrayList(keepsake.orderedItems(cardUri, photoUris))
        check(uris.isNotEmpty()) { "No selected photos were available. Check your connection and try again." }
        PreparedHikeShare(
            uris = uris,
            caption = buildString {
                append(hike.title.ifBlank { "A day on the trail" })
                append(" · ")
                append(hikeShareDateTime(hike))
                hike.distanceMiles?.let {
                    append(" · ")
                    append(hikeShareDistance(hike))
                    append(" miles")
                }
                append(" · HikeJournal")
            },
            omittedPhotoCount = cachedPhotos.count { it == null },
        )
    }
}

internal suspend fun prepareMultiHikeShare(
    context: Context,
    hikes: List<Hike>,
    photos: List<Photo>,
    satelliteMaps: Map<String, Bitmap?>,
    keepsake: HikeShareKeepsake,
): PreparedHikeShare {
    val selectedHikes = hikes.distinctBy(Hike::id)
    require(selectedHikes.size >= 2) { "Choose at least two hikes to share together." }
    val maximumPhotos = (MAX_SOCIAL_CAROUSEL_ITEMS - if (keepsake.includesKeepsake) selectedHikes.size else 0)
        .coerceAtLeast(0)
    val selectedPhotos = photos.filter {
        !it.contentType.startsWith("video/", ignoreCase = true) && it.url.isNotBlank()
    }.take(maximumPhotos)
    val resolvedMaps = if (keepsake.includesKeepsake) {
        selectedHikes.associate { hike ->
            hike.id to (satelliteMaps[hike.id] ?: captureSatelliteRouteMap(context, hike.routeSegments))
        }
    } else {
        emptyMap()
    }

    return withContext(Dispatchers.IO) {
        val shareDirectory = File(context.cacheDir, "shared_hikes").apply { mkdirs() }
        shareDirectory.listFiles().orEmpty()
            .filter { System.currentTimeMillis() - it.lastModified() > 24L * 60L * 60L * 1_000L }
            .forEach(File::delete)

        val cardUris = if (keepsake.includesKeepsake) {
            selectedHikes.map { hike ->
                val safeHikeId = hike.id.replace(Regex("[^A-Za-z0-9._-]"), "-").take(64).ifBlank { "outing" }
                val cardFile = File(shareDirectory, "HikeJournal-$safeHikeId.jpg")
                FileOutputStream(cardFile).use { output ->
                    check(
                        renderHikeShareCard(context, hike, resolvedMaps[hike.id])
                            .compress(Bitmap.CompressFormat.JPEG, 94, output),
                    ) { "HikeJournal could not save a trail card." }
                }
                FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", cardFile)
            }
        } else {
            emptyList()
        }
        val cachedPhotos = coroutineScope {
            selectedPhotos.mapIndexed { index, photo ->
                async {
                    val safeHikeId = photo.hikeId.orEmpty().replace(Regex("[^A-Za-z0-9._-]"), "-").take(64).ifBlank { "outing" }
                    runCatching { cacheSharedPhoto(context, photo, shareDirectory, safeHikeId, index) }.getOrNull()
                }
            }.awaitAll()
        }
        val photoUris = cachedPhotos.filterNotNull().map { file ->
            FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        }
        val orderedUris = when (keepsake) {
            HikeShareKeepsake.FIRST -> cardUris + photoUris
            HikeShareKeepsake.LAST -> photoUris + cardUris
            HikeShareKeepsake.NONE -> photoUris
        }
        check(orderedUris.isNotEmpty()) { "No selected photos were available. Check your connection and try again." }
        PreparedHikeShare(
            uris = ArrayList(orderedUris),
            caption = buildString {
                append("HikeJournal · ")
                append(selectedHikes.size)
                append(" hikes\n")
                append(selectedHikes.joinToString("\n") { hike ->
                    buildString {
                        append(hike.title.ifBlank { "Untitled hike" })
                        append(" · ")
                        append(hikeShareDateTime(hike))
                        hike.distanceMiles?.let {
                            append(" · ")
                            append(hikeShareDistance(hike))
                            append(" miles")
                        }
                    }
                })
            },
            omittedPhotoCount = cachedPhotos.count { it == null },
        )
    }
}

private fun cacheSharedPhoto(
    context: Context,
    photo: Photo,
    directory: File,
    safeHikeId: String,
    index: Int,
): File {
    val extension = when (photo.contentType.lowercase(Locale.US)) {
        "image/png" -> "png"
        "image/webp" -> "webp"
        "image/heic", "image/heif" -> "heic"
        else -> "jpg"
    }
    val destination = File(directory, "$safeHikeId-photo-${index + 1}.$extension")
    val uri = photo.url.toUri()
    when (uri.scheme?.lowercase(Locale.US)) {
        "http", "https" -> {
            val response = shareHttpClient.newCall(Request.Builder().url(photo.url).build()).execute()
            response.use {
                check(it.isSuccessful) { "Photo download failed with ${it.code}." }
                val body = it.body ?: error("Photo download was empty.")
                body.byteStream().use { input ->
                    FileOutputStream(destination).use(input::copyTo)
                }
            }
        }
        "file" -> {
            val source = uri.path?.let(::File) ?: error("The saved photo path is missing.")
            FileInputStream(source).use { input -> FileOutputStream(destination).use(input::copyTo) }
        }
        else -> {
            val input = context.contentResolver.openInputStream(uri)
                ?: error("The selected photo could not be opened.")
            input.use { source -> FileOutputStream(destination).use(source::copyTo) }
        }
    }
    check(destination.length() > 0L) { "The selected photo was empty." }
    return destination
}

internal suspend fun prepareSinglePhotoShare(context: Context, photo: Photo): Uri =
    withContext(Dispatchers.IO) {
        require(!photo.contentType.startsWith("video/")) { "Only photos can be shared here." }
        require(photo.url.isNotBlank()) { "This photo is not available to share." }
        val shareDirectory = File(context.cacheDir, "shared_hikes").apply { mkdirs() }
        shareDirectory.listFiles().orEmpty()
            .filter { System.currentTimeMillis() - it.lastModified() > 24L * 60L * 60L * 1_000L }
            .forEach(File::delete)
        val safePhotoId = photo.id.replace(Regex("[^A-Za-z0-9._-]"), "-").take(64).ifBlank { "photo" }
        val file = cacheSharedPhoto(context, photo, shareDirectory, "single-$safePhotoId", 0)
        FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    }

internal fun launchSinglePhotoShare(context: Context, photo: Photo, uri: Uri) {
    val shareIntent = Intent(Intent.ACTION_SEND).apply {
        type = "image/*"
        putExtra(Intent.EXTRA_STREAM, uri)
        photo.caption.takeIf(String::isNotBlank)?.let { putExtra(Intent.EXTRA_TEXT, it) }
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        clipData = ClipData.newUri(context.contentResolver, "HikeJournal photo", uri)
        if (context !is Activity) addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }
    val chooser = Intent.createChooser(shareIntent, "Share photo")
    if (context !is Activity) chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    context.startActivity(chooser)
}

private fun launchHikeShare(
    context: Context,
    prepared: PreparedHikeShare,
) {
    val shareIntent = Intent(
        if (prepared.uris.size == 1) Intent.ACTION_SEND else Intent.ACTION_SEND_MULTIPLE,
    ).apply {
        type = "image/*"
        if (prepared.uris.size == 1) {
            putExtra(Intent.EXTRA_STREAM, prepared.uris.first())
        } else {
            putParcelableArrayListExtra(Intent.EXTRA_STREAM, prepared.uris)
        }
        putExtra(Intent.EXTRA_TEXT, prepared.caption)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        clipData = ClipData.newUri(context.contentResolver, "HikeJournal outing", prepared.uris.first()).apply {
            prepared.uris.drop(1).forEach { addItem(ClipData.Item(it)) }
        }
        if (context !is Activity) addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }
    val chooser = Intent.createChooser(shareIntent, "Share your HikeJournal outing")
    if (context !is Activity) chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    context.startActivity(chooser)
}
