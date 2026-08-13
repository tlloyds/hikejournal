package com.hikejournal.app.ui

import android.app.Activity
import android.content.ActivityNotFoundException
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
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.IosShare
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
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
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request

internal const val MAX_SOCIAL_CAROUSEL_ITEMS = 20
internal const val MAX_SOCIAL_PHOTOS = MAX_SOCIAL_CAROUSEL_ITEMS - 1

internal data class ShareRoutePoint(val x: Float, val y: Float)

internal data class PreparedHikeShare(
    val uris: ArrayList<Uri>,
    val caption: String,
    val omittedPhotoCount: Int,
)

private val shareHttpClient = OkHttpClient()

@Composable
internal fun HikeShareDialog(
    hike: Hike,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val availablePhotos = remember(hike.photos) {
        hike.photos.filter { !it.contentType.startsWith("video/") && it.url.isNotBlank() }
    }
    var selectedIds by remember(hike.id) { mutableStateOf<Set<String>>(emptySet()) }
    var preparingTarget by remember(hike.id) { mutableStateOf<String?>(null) }
    var errorMessage by remember(hike.id) { mutableStateOf<String?>(null) }
    var revealed by remember(hike.id) { mutableStateOf(false) }
    LaunchedEffect(hike.id) { revealed = true }

    val preview = remember(
        hike.id,
        hike.title,
        hike.hikeDate,
        hike.distanceMiles,
        hike.durationSeconds,
        hike.routeStartedAt,
        hike.locationName,
        hike.routeSegments,
    ) {
        renderHikeShareCard(context, hike, width = 540, height = 675)
    }
    val previewPresence by animateFloatAsState(
        targetValue = if (revealed) 1f else 0f,
        animationSpec = tween(480),
        label = "share-card-preview",
    )
    val navigationBarPadding = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()

    fun beginShare(instagramOnly: Boolean) {
        if (preparingTarget != null) return
        preparingTarget = if (instagramOnly) "instagram" else "more"
        errorMessage = null
        val selectedPhotos = availablePhotos.filter { it.id in selectedIds }.take(MAX_SOCIAL_PHOTOS)
        scope.launch {
            runCatching { prepareHikeShare(context, hike, selectedPhotos) }
                .onSuccess { prepared ->
                    preparingTarget = null
                    val openedInstagram = launchHikeShare(
                        context = context,
                        prepared = prepared,
                        instagramOnly = instagramOnly,
                    )
                    if (instagramOnly && !openedInstagram) {
                        Toast.makeText(
                            context,
                            "Instagram was not available, so the Android share sheet opened instead.",
                            Toast.LENGTH_LONG,
                        ).show()
                    }
                    if (prepared.omittedPhotoCount > 0) {
                        Toast.makeText(
                            context,
                            "${prepared.omittedPhotoCount} photo${if (prepared.omittedPhotoCount == 1) " was" else "s were"} unavailable; the rest are ready to share.",
                            Toast.LENGTH_LONG,
                        ).show()
                    }
                }
                .onFailure { error ->
                    preparingTarget = null
                    errorMessage = error.message ?: "HikeJournal could not prepare these images."
                }
        }
    }

    Dialog(
        onDismissRequest = { if (preparingTarget == null) onDismiss() },
        properties = DialogProperties(
            dismissOnBackPress = preparingTarget == null,
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
                IconButton(onClick = onDismiss, enabled = preparingTarget == null) {
                    Icon(Icons.Rounded.Close, "Close share preview", tint = Paper)
                }
            }

            LazyColumn(
                Modifier.weight(1f),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 18.dp),
            ) {
                item(key = "share-preview") {
                    Image(
                        bitmap = preview.asImageBitmap(),
                        contentDescription = "Social card preview for ${hike.title}",
                        contentScale = ContentScale.Fit,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 18.dp)
                            .aspectRatio(4f / 5f)
                            .clip(RoundedCornerShape(8.dp))
                            .border(1.dp, Color.White.copy(alpha = 0.2f), RoundedCornerShape(8.dp))
                            .alpha(previewPresence)
                            .scale(0.97f + previewPresence * 0.03f),
                    )
                }

                item(key = "share-copy") {
                    AnimatedVisibility(
                        visible = revealed,
                        enter = fadeIn(tween(360, delayMillis = 100)) +
                            slideInVertically(tween(420, delayMillis = 100)) { it / 7 },
                    ) {
                        Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 18.dp)) {
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
                                "Your map, date, time, and distance are already set.",
                                style = MaterialTheme.typography.bodyLarge,
                                color = Color(0xFFD6E0D3),
                                modifier = Modifier.padding(top = 7.dp),
                            )
                        }
                    }
                }

                if (availablePhotos.isNotEmpty()) {
                    item(key = "photo-label") {
                        Row(
                            Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 4.dp),
                            verticalAlignment = Alignment.Bottom,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text("ADD HIKE PHOTOS", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                                Text("Choose up to $MAX_SOCIAL_PHOTOS", style = MaterialTheme.typography.titleLarge, color = Paper)
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                Text(
                                    "${selectedIds.size}/$MAX_SOCIAL_PHOTOS",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = Color(0xFFD6E0D3),
                                )
                                TextButton(
                                    onClick = {
                                        selectedIds = if (
                                            selectedIds.size == min(availablePhotos.size, MAX_SOCIAL_PHOTOS)
                                        ) {
                                            emptySet()
                                        } else {
                                            availablePhotos.take(MAX_SOCIAL_PHOTOS).mapTo(linkedSetOf(), Photo::id)
                                        }
                                    },
                                    enabled = preparingTarget == null,
                                ) {
                                    Text(
                                        if (selectedIds.size == min(availablePhotos.size, MAX_SOCIAL_PHOTOS)) {
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
                    item(key = "photo-picker") {
                        LazyRow(
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 20.dp, vertical = 12.dp),
                            horizontalArrangement = Arrangement.spacedBy(9.dp),
                        ) {
                            items(availablePhotos, key = Photo::id) { photo ->
                                val selected = photo.id in selectedIds
                                val canSelect = selected || selectedIds.size < MAX_SOCIAL_PHOTOS
                                SharePhotoTile(
                                    photo = photo,
                                    selected = selected,
                                    enabled = canSelect && preparingTarget == null,
                                    onClick = {
                                        selectedIds = if (selected) {
                                            selectedIds - photo.id
                                        } else {
                                            (selectedIds + photo.id).take(MAX_SOCIAL_PHOTOS).toSet()
                                        }
                                    },
                                )
                            }
                        }
                    }
                    item(key = "photo-order") {
                        Text(
                            "The trail card shares first, followed by your selected photos — ${selectedIds.size + 1} of $MAX_SOCIAL_CAROUSEL_ITEMS items.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFB8C9BC),
                            modifier = Modifier.padding(horizontal = 20.dp, vertical = 2.dp),
                        )
                    }
                }

                errorMessage?.let { message ->
                    item(key = "share-error") {
                        Text(
                            message,
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color(0xFFFFD0C5),
                            modifier = Modifier.padding(horizontal = 20.dp, vertical = 14.dp),
                        )
                    }
                }
            }

            Surface(color = Color(0xF2183A2D), shadowElevation = 12.dp) {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp)
                        .padding(top = 13.dp, bottom = navigationBarPadding + 14.dp),
                ) {
                    Button(
                        onClick = { beginShare(instagramOnly = true) },
                        enabled = preparingTarget == null,
                        colors = ButtonDefaults.buttonColors(containerColor = Trail, contentColor = Paper),
                        modifier = Modifier.fillMaxWidth().height(52.dp),
                    ) {
                        if (preparingTarget == "instagram") {
                            CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Rounded.IosShare, null, Modifier.size(19.dp))
                        }
                        Spacer(Modifier.width(8.dp))
                        Text(if (preparingTarget == "instagram") "Preparing images…" else "Share to Instagram")
                    }
                    TextButton(
                        onClick = { beginShare(instagramOnly = false) },
                        enabled = preparingTarget == null,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        if (preparingTarget == "more") {
                            CircularProgressIndicator(Modifier.size(17.dp), color = Paper, strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                        }
                        Text("More sharing options", color = Paper)
                    }
                }
            }
        }
    }
}

@Composable
private fun SharePhotoTile(
    photo: Photo,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    Box(
        Modifier
            .size(width = 92.dp, height = 112.dp)
            .clip(RoundedCornerShape(6.dp))
            .clickable(enabled = enabled, onClick = onClick)
            .alpha(if (enabled || selected) 1f else 0.42f)
            .border(
                width = if (selected) 3.dp else 1.dp,
                color = if (selected) Trail else Color.White.copy(alpha = 0.24f),
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
            visible = selected,
            modifier = Modifier.align(Alignment.TopEnd),
            enter = fadeIn(tween(140)) + scaleIn(tween(180), initialScale = 0.65f),
        ) {
            Box(
                Modifier.padding(6.dp).size(24.dp).background(Trail, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Rounded.Check, "Selected", tint = Paper, modifier = Modifier.size(17.dp))
            }
        }
    }
}

internal fun socialSharePhotos(photos: List<Photo>): List<Photo> =
    photos.filter { !it.contentType.startsWith("video/") && it.url.isNotBlank() }.take(MAX_SOCIAL_PHOTOS)

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
    val projected = projectShareRoute(
        routeSegments = hike.routeSegments,
        width = mapWidth,
        height = mapHeight,
        padding = 48f * sx,
    )
    if (projected.isNotEmpty()) {
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

private suspend fun prepareHikeShare(
    context: Context,
    hike: Hike,
    photos: List<Photo>,
): PreparedHikeShare = withContext(Dispatchers.IO) {
    val shareDirectory = File(context.cacheDir, "shared_hikes").apply { mkdirs() }
    shareDirectory.listFiles().orEmpty()
        .filter { System.currentTimeMillis() - it.lastModified() > 24L * 60L * 60L * 1_000L }
        .forEach(File::delete)

    val safeHikeId = hike.id.replace(Regex("[^A-Za-z0-9._-]"), "-").take(64).ifBlank { "outing" }
    val cardFile = File(shareDirectory, "HikeJournal-$safeHikeId.jpg")
    FileOutputStream(cardFile).use { output ->
        check(renderHikeShareCard(context, hike).compress(Bitmap.CompressFormat.JPEG, 94, output)) {
            "HikeJournal could not save the trail card."
        }
    }
    val uris = arrayListOf(
        FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", cardFile)
    )
    var omitted = 0
    photos.take(MAX_SOCIAL_PHOTOS).forEachIndexed { index, photo ->
        runCatching {
            cacheSharedPhoto(context, photo, shareDirectory, safeHikeId, index)
        }.onSuccess { file ->
            uris += FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        }.onFailure {
            omitted += 1
        }
    }
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
        omittedPhotoCount = omitted,
    )
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

private fun launchHikeShare(
    context: Context,
    prepared: PreparedHikeShare,
    instagramOnly: Boolean,
): Boolean {
    fun shareIntent(packageName: String? = null) = Intent(
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
        if (packageName != null) setPackage(packageName)
        if (context !is Activity) addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }

    if (instagramOnly) {
        try {
            context.startActivity(shareIntent("com.instagram.android"))
            return true
        } catch (_: ActivityNotFoundException) {
            // Fall through to the system chooser when Instagram is not installed.
        } catch (_: SecurityException) {
            // Fall through if the installed app refuses the external share intent.
        }
    }
    val chooser = Intent.createChooser(shareIntent(), "Share your HikeJournal outing")
    if (context !is Activity) chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    context.startActivity(chooser)
    return !instagramOnly
}
