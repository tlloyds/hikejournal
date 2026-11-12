package com.hikejournal.app.ui

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.os.Build
import android.widget.Toast
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.IosShare
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.FileProvider
import androidx.core.content.res.ResourcesCompat
import androidx.core.graphics.createBitmap
import androidx.core.graphics.drawable.toBitmap
import coil.imageLoader
import coil.request.ImageRequest
import com.hikejournal.app.R
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.MossSoft
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

internal fun speciesSharePhotos(species: SpeciesRecord): List<Photo> = species.encounters
    .map { it.photo }
    .filter { it.url.isNotBlank() && !it.contentType.startsWith("video/", ignoreCase = true) }
    .distinctBy(Photo::id)

internal fun selectedSpeciesSharePhotos(
    species: SpeciesRecord,
    selectedIds: List<String>,
    keepsake: HikeShareKeepsake,
): List<Photo> {
    val available = speciesSharePhotos(species).associateBy(Photo::id)
    return selectedIds.distinct().mapNotNull(available::get).take(keepsake.maximumPhotos)
}

internal fun speciesShareImageUrl(species: SpeciesRecord, photos: List<Photo>): String =
    photos.firstOrNull()?.url ?: speciesSharePhotos(species).firstOrNull()?.url ?: species.coverUrl

@Composable
internal fun SpeciesShareDialog(species: SpeciesRecord, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val configuration = LocalConfiguration.current
    val direction = LocalLayoutDirection.current
    val systemBars = WindowInsets.systemBars.asPaddingValues()
    // This Compose version measures dialogs from Configuration, which includes system
    // bars on Android 15+. Constrain the content to the native window's usable bounds.
    val dialogHeight = configuration.screenHeightDp.dp - if (Build.VERSION.SDK_INT >= 35) {
        systemBars.calculateTopPadding() + systemBars.calculateBottomPadding()
    } else 0.dp
    val dialogWidth = configuration.screenWidthDp.dp - if (Build.VERSION.SDK_INT >= 35) {
        systemBars.calculateLeftPadding(direction) + systemBars.calculateRightPadding(direction)
    } else 0.dp
    val scope = rememberCoroutineScope()
    val availablePhotos = remember(species.encounters) { speciesSharePhotos(species) }
    var keepsake by remember(species.key) { mutableStateOf(HikeShareKeepsake.FIRST) }
    var selectedIds by remember(species.key) { mutableStateOf(emptyList<String>()) }
    var preparing by remember(species.key) { mutableStateOf(false) }
    var errorMessage by remember(species.key) { mutableStateOf<String?>(null) }
    var preview by remember(species.key) { mutableStateOf<Bitmap?>(null) }
    val photos = selectedSpeciesSharePhotos(species, selectedIds, keepsake)
    val imageCount = photos.size + if (keepsake.includesKeepsake) 1 else 0
    val heroUrl = speciesShareImageUrl(species, photos)
    LaunchedEffect(species, heroUrl, keepsake.includesKeepsake) {
        if (!keepsake.includesKeepsake) return@LaunchedEffect
        preview = null
        val image = loadSpeciesShareImage(context, heroUrl)
        preview = withContext(Dispatchers.Default) {
            renderSpeciesShareCard(context, species, image, width = 540, height = 675)
        }
    }

    fun beginShare() {
        if (preparing || imageCount == 0) return
        preparing = true
        errorMessage = null
        scope.launch {
            try {
                val prepared = prepareSpeciesShare(context, species, photos.map(Photo::id), keepsake)
                launchPreparedImageShare(context, prepared, "Share ${species.commonName}", "HikeJournal species")
                if (prepared.omittedPhotoCount > 0) {
                    Toast.makeText(context,
                        "${prepared.omittedPhotoCount} selected photos were unavailable; the rest are ready to share.",
                        Toast.LENGTH_LONG).show()
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                errorMessage = error.message ?: "HikeJournal could not prepare these images."
            } finally {
                preparing = false
            }
        }
    }

    Dialog(
        onDismissRequest = { if (!preparing) onDismiss() },
        properties = DialogProperties(
            dismissOnBackPress = !preparing,
            dismissOnClickOutside = false,
            usePlatformDefaultWidth = false,
            decorFitsSystemWindows = true,
        ),
    ) {
        Column(Modifier.width(dialogWidth).height(dialogHeight).background(
            Brush.verticalGradient(listOf(MossSoft, Moss, Color(0xFF1D2A17))),
        )) {
            Row(Modifier.fillMaxWidth().padding(start = 18.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("HIKEJOURNAL", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                    Text("Share ${species.commonName}", style = MaterialTheme.typography.headlineMedium, color = Paper,
                        maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
                IconButton(onClick = onDismiss, enabled = !preparing) {
                    Icon(Icons.Rounded.Close, "Close species share", tint = Paper)
                }
            }
            LazyVerticalGrid(
                columns = GridCells.Fixed(2), modifier = Modifier.weight(1f).clipToBounds(),
                contentPadding = PaddingValues(start = 18.dp, end = 18.dp, bottom = 22.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item(key = "keepsake-choice", span = { GridItemSpan(maxLineSpan) }) {
                    Column(Modifier.fillMaxWidth().selectableGroup()) {
                        Text("FIELD GUIDE KEEPSAKE", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                        HikeShareKeepsake.entries.forEach { option ->
                            Row(Modifier.fillMaxWidth().selectable(
                                selected = keepsake == option, enabled = !preparing, role = Role.RadioButton,
                                onClick = {
                                    keepsake = option
                                    selectedIds = selectedIds.take(option.maximumPhotos)
                                },
                            ).heightIn(min = 48.dp), verticalAlignment = Alignment.CenterVertically) {
                                RadioButton(selected = keepsake == option, onClick = null, enabled = !preparing,
                                    colors = RadioButtonDefaults.colors(selectedColor = Trail, unselectedColor = Paper.copy(alpha = 0.7f)))
                                Text(option.label, style = MaterialTheme.typography.bodyLarge, color = Paper,
                                    modifier = Modifier.padding(start = 10.dp))
                            }
                        }
                        Text("Choose up to ${keepsake.maximumPhotos} photos, in the order you want to share them. " +
                            "Adding a keepsake keeps your first 19 selections.",
                            style = MaterialTheme.typography.bodySmall, color = Color(0xFFD6E0D3))
                    }
                }
                if (keepsake.includesKeepsake) {
                    item(key = "preview", span = { GridItemSpan(maxLineSpan) }) {
                        Column {
                            Box(Modifier.fillMaxWidth().aspectRatio(4f / 5f), contentAlignment = Alignment.Center) {
                                val rendered = preview
                                androidx.compose.animation.AnimatedVisibility(visible = rendered != null,
                                    enter = fadeIn(tween(360)) + slideInVertically(tween(420)) { it / 12 }) {
                                    if (rendered != null) Image(rendered.asImageBitmap(),
                                        "Field guide keepsake for ${species.commonName}", modifier = Modifier.fillMaxSize())
                                }
                                if (rendered == null) CircularProgressIndicator(color = Paper)
                            }
                            Text("Your first selected photo appears on the keepsake, with this species’ name and encounter history.",
                                style = MaterialTheme.typography.bodySmall, color = Color(0xFFD6E0D3),
                                modifier = Modifier.padding(top = 8.dp))
                        }
                    }
                }
                item(key = "photos", span = { GridItemSpan(maxLineSpan) }) {
                    Row(Modifier.fillMaxWidth().padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("CHOOSE SPECIES PHOTOS", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF1BE79))
                            Text("${photos.size}/${keepsake.maximumPhotos} selected", style = MaterialTheme.typography.titleLarge, color = Paper)
                        }
                        if (availablePhotos.isNotEmpty()) TextButton(enabled = !preparing, onClick = {
                            selectedIds = if (photos.size == minOf(availablePhotos.size, keepsake.maximumPhotos)) emptyList()
                                else availablePhotos.take(keepsake.maximumPhotos).map(Photo::id)
                        }) {
                            Text(if (photos.size == minOf(availablePhotos.size, keepsake.maximumPhotos)) "Clear" else "Select all",
                                color = Color(0xFFF1BE79))
                        }
                    }
                }
                itemsIndexed(availablePhotos, key = { _, photo -> photo.id }) { index, photo ->
                    val selectedIndex = selectedIds.indexOf(photo.id).takeIf { it >= 0 }
                    SharePhotoTile(photo, selectedIndex,
                        enabled = !preparing && (selectedIndex != null || photos.size < keepsake.maximumPhotos),
                        onClick = { selectedIds = if (selectedIndex != null) selectedIds - photo.id else selectedIds + photo.id },
                        label = "${species.commonName} photo ${index + 1}",
                    )
                }
                item(key = "share-details", span = { GridItemSpan(maxLineSpan) }) {
                    val message = when {
                        availablePhotos.isEmpty() -> "No encounter photos are available. You can still share the field guide keepsake."
                        !keepsake.includesKeepsake && photos.isEmpty() -> "Select at least one photo to share without a keepsake."
                        keepsake == HikeShareKeepsake.FIRST -> "Your field guide keepsake shares first, followed by your selected photos."
                        keepsake == HikeShareKeepsake.LAST -> "Your selected photos share first, followed by your field guide keepsake."
                        else -> "Only your selected photos will be shared."
                    }
                    Column {
                        Text("$message $imageCount of $MAX_SOCIAL_CAROUSEL_ITEMS images. Videos are excluded.",
                            style = MaterialTheme.typography.bodySmall, color = Color(0xFFD6E0D3))
                        errorMessage?.let { Text(it, color = Color(0xFFFFD0C5), modifier = Modifier.padding(top = 12.dp)) }
                    }
                }
            }
            Surface(color = Color(0xF2324223), shadowElevation = 12.dp) {
                Box(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 14.dp)) {
                    Button(onClick = ::beginShare, enabled = !preparing && imageCount > 0,
                        colors = ButtonDefaults.buttonColors(containerColor = Trail, contentColor = Paper),
                        modifier = Modifier.fillMaxWidth().height(52.dp)) {
                        if (preparing) CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                        else Icon(Icons.Rounded.IosShare, null, Modifier.size(19.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(if (preparing) "Preparing $imageCount images…" else "Share $imageCount image${if (imageCount == 1) "" else "s"}")
                    }
                }
            }
        }
    }
}

private suspend fun loadSpeciesShareImage(context: Context, url: String): Bitmap? {
    if (url.isBlank()) return null
    return context.imageLoader.execute(ImageRequest.Builder(context).data(url).size(1080)
        .allowHardware(false).build()).drawable?.toBitmap()
}

internal fun renderSpeciesShareCard(
    context: Context,
    species: SpeciesRecord,
    image: Bitmap?,
    width: Int = 1080,
    height: Int = 1350,
): Bitmap {
    val bitmap = createBitmap(width.coerceAtLeast(320), height.coerceAtLeast(400))
    val canvas = Canvas(bitmap)
    val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    drawKeepsakeBackground(context, canvas, paint, bitmap.width, bitmap.height)
    canvas.scale(bitmap.width / 1080f, bitmap.height / 1350f)
    val body = ResourcesCompat.getFont(context, R.font.quicksand_400) ?: Typeface.SANS_SERIF
    val brand = ResourcesCompat.getFont(context, R.font.quicksand_700) ?: Typeface.DEFAULT_BOLD
    val display = ResourcesCompat.getFont(context, R.font.cormorant_garamond_400) ?: Typeface.SERIF
    val mark = requireNotNull(BitmapFactory.decodeResource(context.resources, R.drawable.hj_logo_color_icon))
    canvas.drawBitmap(mark, null, RectF(72f, 42f, 146f, 130f), paint)
    mark.recycle()
    paint.color = android.graphics.Color.WHITE
    paint.typeface = brand
    paint.textSize = 52f
    canvas.drawText("HikeJournal", 160f, 105f, paint)
    paint.typeface = body
    paint.textSize = 22f
    paint.textAlign = Paint.Align.RIGHT
    paint.color = 0xFFB8C9BC.toInt()
    canvas.drawText("FIELD GUIDE KEEPSAKE", 1008f, 96f, paint)
    paint.textAlign = Paint.Align.LEFT
    val imageBounds = RectF(56f, 170f, 1024f, 850f)
    if (image != null) {
        val scale = maxOf(imageBounds.width() / image.width, imageBounds.height() / image.height)
        val centerX = imageBounds.centerX()
        val centerY = imageBounds.centerY()
        canvas.save()
        canvas.clipRect(imageBounds)
        canvas.drawBitmap(image, null, RectF(centerX - image.width * scale / 2, centerY - image.height * scale / 2,
            centerX + image.width * scale / 2, centerY + image.height * scale / 2), paint)
        canvas.restore()
    } else {
        paint.textSize = 32f
        canvas.drawText("From your personal field guide", 72f, 520f, paint)
    }
    paint.color = 0xFFF5F1E7.toInt()
    paint.typeface = display
    paint.textSize = 68f
    textLines(species.commonName, paint, 936f, 2).forEachIndexed { index, line ->
        canvas.drawText(line, 72f, 942f + index * 70f, paint)
    }
    paint.typeface = Typeface.create(body, Typeface.ITALIC)
    paint.textSize = 32f
    paint.color = 0xFFD6E0D3.toInt()
    canvas.drawText(textLines(species.scientificName, paint, 936f, 1).first(), 72f, 1072f, paint)
    paint.typeface = body
    paint.textSize = 30f
    paint.color = 0xFFF1BE79.toInt()
    canvas.drawText("${species.encounterCount} encounter${if (species.encounterCount == 1) "" else "s"} across " +
        "${species.hikeCount} outing${if (species.hikeCount == 1) "" else "s"}", 72f, 1152f, paint)
    paint.color = 0xFFB8C9BC.toInt()
    paint.textSize = 26f
    canvas.drawText("A page from my personal field guide", 72f, 1262f, paint)
    return bitmap
}

internal suspend fun prepareSpeciesShare(
    context: Context,
    species: SpeciesRecord,
    selectedIds: List<String>,
    keepsake: HikeShareKeepsake,
): PreparedImageShare = withContext(Dispatchers.IO) {
    val photos = selectedSpeciesSharePhotos(species, selectedIds, keepsake)
    val directory = File(context.cacheDir, "shared_hikes").apply { mkdirs() }
    directory.listFiles().orEmpty().filter { System.currentTimeMillis() - it.lastModified() > 86_400_000L }
        .forEach(File::delete)
    // Each share keeps its own files so a second share cannot overwrite open attachments.
    val shareId = "species-${UUID.randomUUID()}"
    val cardUri = if (keepsake.includesKeepsake) {
        val image = loadSpeciesShareImage(context, speciesShareImageUrl(species, photos))
        val card = renderSpeciesShareCard(context, species, image)
        val file = File(directory, "HikeJournal-$shareId.jpg")
        try {
            FileOutputStream(file).use { check(card.compress(Bitmap.CompressFormat.JPEG, 94, it)) {
                "HikeJournal could not save the field guide keepsake."
            } }
        } finally {
            card.recycle()
        }
        FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    } else null
    val cached = coroutineScope {
        photos.mapIndexed { index, photo -> async {
            try {
                cacheSharedPhoto(context, photo, directory, shareId, index)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                null
            }
        } }.awaitAll()
    }
    val photoUris = cached.filterNotNull().map { FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", it) }
    val uris = ArrayList(keepsake.orderedItems(cardUri, photoUris))
    check(uris.isNotEmpty()) { "No selected photos were available. Check your connection and try again." }
    PreparedImageShare(uris, buildString {
        append(species.commonName)
        if (species.scientificName.isNotBlank()) append(" (${species.scientificName})")
        append(" · ${species.encounterCount} encounter${if (species.encounterCount == 1) "" else "s"}")
        append(" across ${species.hikeCount} outing${if (species.hikeCount == 1) "" else "s"} · HikeJournal")
    }, cached.count { it == null })
}
