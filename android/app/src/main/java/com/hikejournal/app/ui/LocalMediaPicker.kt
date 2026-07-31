@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.hikejournal.app.ui

import android.net.Uri
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
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
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.ImageLoader
import coil.compose.AsyncImage
import coil.decode.VideoFrameDecoder
import coil.request.ImageRequest
import coil.request.videoFrameMillis
import com.hikejournal.app.data.LocalMediaAccess
import com.hikejournal.app.data.LocalMediaAlbum
import com.hikejournal.app.data.LocalMediaItem
import com.hikejournal.app.data.MAX_LOCAL_MEDIA_SELECTION
import com.hikejournal.app.data.addLocalMediaSelection
import com.hikejournal.app.data.loadLocalMediaLibrary
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.TrailText

@Composable
internal fun LocalMediaPickerDialog(
    access: LocalMediaAccess,
    onDismiss: () -> Unit,
    onConfirm: (List<Uri>) -> Unit,
) {
    val context = LocalContext.current
    val imageLoader = remember {
        ImageLoader.Builder(context)
            .components { add(VideoFrameDecoder.Factory()) }
            .build()
    }
    var albums by remember { mutableStateOf<List<LocalMediaAlbum>?>(null) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var openAlbumId by remember { mutableStateOf<String?>(null) }
    var selectedUris by remember { mutableStateOf<List<String>>(emptyList()) }
    var selectionNotice by remember { mutableStateOf<String?>(null) }

    DisposableEffect(imageLoader) {
        onDispose { imageLoader.shutdown() }
    }
    LaunchedEffect(access) {
        runCatching { loadLocalMediaLibrary(context, access) }
            .onSuccess { albums = it }
            .onFailure {
                loadError = "HikeJournal couldn't open your photo library. Check access in Settings and try again."
            }
    }

    val openAlbum = albums?.firstOrNull { it.id == openAlbumId }
    Dialog(
        onDismissRequest = {
            if (openAlbumId == null) onDismiss() else openAlbumId = null
        },
        properties = DialogProperties(
            usePlatformDefaultWidth = false,
            decorFitsSystemWindows = false,
        ),
    ) {
        Scaffold(
            containerColor = Parchment,
            topBar = {
                Column(Modifier.background(Paper).statusBarsPadding()) {
                    Row(
                        Modifier.fillMaxWidth().height(58.dp).padding(horizontal = 6.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        IconButton(
                            onClick = {
                                if (openAlbumId == null) onDismiss() else openAlbumId = null
                            },
                        ) {
                            Icon(
                                if (openAlbumId == null) Icons.Rounded.Close else Icons.AutoMirrored.Rounded.ArrowBack,
                                if (openAlbumId == null) "Close" else "Back to albums",
                                tint = Ink,
                            )
                        }
                        Column(Modifier.weight(1f)) {
                            Text(
                                "PHONE ORIGINALS",
                                style = MaterialTheme.typography.labelSmall,
                                color = TrailText,
                            )
                            Text(
                                openAlbum?.name ?: "Local albums",
                                style = MaterialTheme.typography.titleLarge,
                                color = Ink,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        if (selectedUris.isNotEmpty()) {
                            Text(
                                "${selectedUris.size} selected",
                                style = MaterialTheme.typography.labelMedium,
                                color = Moss,
                                modifier = Modifier.padding(end = 12.dp),
                            )
                        }
                    }
                    HorizontalDivider(color = Line)
                }
            },
            bottomBar = {
                Surface(
                    color = Paper,
                    shadowElevation = 10.dp,
                ) {
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .windowInsetsPadding(
                                WindowInsets.safeDrawing.only(WindowInsetsSides.Bottom),
                            )
                            .padding(start = 16.dp, top = 12.dp, end = 16.dp, bottom = 30.dp),
                    ) {
                        selectionNotice?.let {
                            Text(
                                it,
                                style = MaterialTheme.typography.bodySmall,
                                color = TrailText,
                                modifier = Modifier.padding(bottom = 8.dp),
                            )
                        }
                        Button(
                            onClick = { onConfirm(selectedUris.map(Uri::parse)) },
                            enabled = selectedUris.isNotEmpty(),
                            modifier = Modifier.fillMaxWidth().height(58.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Moss,
                                contentColor = Paper,
                                disabledContainerColor = Moss.copy(alpha = 0.36f),
                                disabledContentColor = Paper.copy(alpha = 0.78f),
                            ),
                        ) {
                            if (selectedUris.isNotEmpty()) {
                                Icon(Icons.Rounded.Check, null)
                                Spacer(Modifier.size(8.dp))
                            }
                            Text(
                                if (selectedUris.isEmpty()) {
                                    "Select media"
                                } else {
                                    "Add ${selectedUris.size} file${if (selectedUris.size == 1) "" else "s"}"
                                },
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                }
            },
        ) { innerPadding ->
            Box(Modifier.fillMaxSize().padding(innerPadding)) {
                when {
                    loadError != null -> LocalMediaMessage(
                        title = "Phone library unavailable",
                        detail = loadError.orEmpty(),
                    )
                    albums == null -> Column(
                        Modifier.align(Alignment.Center),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        CircularProgressIndicator(color = Trail)
                        Text(
                            "Reading local albums…",
                            style = MaterialTheme.typography.bodyMedium,
                            color = InkMuted,
                            modifier = Modifier.padding(top = 12.dp),
                        )
                    }
                    albums!!.isEmpty() -> LocalMediaMessage(
                        title = "No local originals found",
                        detail = if (access.hasFullLibraryAccess) {
                            "No supported photos or videos under 30 MB are stored on this phone."
                        } else {
                            "No supported photos or videos are available in your current selection. Close this screen and choose Browse media to pick more."
                        },
                    )
                    else -> AnimatedContent(
                        targetState = openAlbumId,
                        transitionSpec = {
                            if (targetState == null) {
                                (slideInHorizontally(tween(190)) { -it / 4 } + fadeIn(tween(150))) togetherWith
                                    (slideOutHorizontally(tween(170)) { it / 4 } + fadeOut(tween(130)))
                            } else {
                                (slideInHorizontally(tween(190)) { it / 4 } + fadeIn(tween(150))) togetherWith
                                    (slideOutHorizontally(tween(170)) { -it / 4 } + fadeOut(tween(130)))
                            }
                        },
                        label = "local-album-navigation",
                    ) { visibleAlbumId ->
                        val visibleAlbum = albums.orEmpty().firstOrNull { it.id == visibleAlbumId }
                        if (visibleAlbum == null) {
                            LocalAlbumGrid(
                                albums = albums.orEmpty(),
                                imageLoader = imageLoader,
                                limitedAccess = !access.hasFullLibraryAccess,
                                onOpenAlbum = { openAlbumId = it.id },
                            )
                        } else {
                            LocalMediaGrid(
                                album = visibleAlbum,
                                imageLoader = imageLoader,
                                selectedUris = selectedUris,
                                onToggle = { uri ->
                                    selectionNotice = null
                                    selectedUris = if (uri in selectedUris) {
                                        selectedUris.filterNot { it == uri }
                                    } else {
                                        val next = addLocalMediaSelection(selectedUris, listOf(uri))
                                        if (next.size == selectedUris.size) {
                                            selectionNotice =
                                                "You can upload up to $MAX_LOCAL_MEDIA_SELECTION files at a time."
                                        }
                                        next
                                    }
                                },
                                onSelectAlbum = {
                                    val next = addLocalMediaSelection(
                                        selectedUris,
                                        visibleAlbum.items.map(LocalMediaItem::uri),
                                    )
                                    val requestedCount =
                                        (selectedUris + visibleAlbum.items.map(LocalMediaItem::uri)).distinct().size
                                    selectionNotice = if (next.size < requestedCount) {
                                        "Selected the first $MAX_LOCAL_MEDIA_SELECTION files. Upload this batch before adding more."
                                    } else {
                                        null
                                    }
                                    selectedUris = next
                                },
                                onClearAlbum = {
                                    val albumUris = visibleAlbum.items.mapTo(hashSetOf(), LocalMediaItem::uri)
                                    selectedUris = selectedUris.filterNot(albumUris::contains)
                                    selectionNotice = null
                                },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun LocalAlbumGrid(
    albums: List<LocalMediaAlbum>,
    imageLoader: ImageLoader,
    limitedAccess: Boolean,
    onOpenAlbum: (LocalMediaAlbum) -> Unit,
) {
    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp, 18.dp, 16.dp, 28.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        item(span = { androidx.compose.foundation.lazy.grid.GridItemSpan(maxLineSpan) }) {
            Column(Modifier.padding(bottom = 2.dp)) {
                Text(
                    "Choose a local album",
                    style = MaterialTheme.typography.headlineLarge,
                    color = Ink,
                )
                Text(
                    if (limitedAccess) {
                        "Only your selected photos are shown. They stay on this phone until you add them to HikeJournal."
                    } else {
                        "Choose original photos or videos from this phone. Location and capture details are preserved when available."
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 5.dp),
                )
            }
        }
        items(albums, key = LocalMediaAlbum::id) { album ->
            Column(
                Modifier
                    .fillMaxWidth()
                    .clickable { onOpenAlbum(album) },
            ) {
                Box(
                    Modifier
                        .fillMaxWidth()
                        .aspectRatio(1.08f)
                        .clip(MaterialTheme.shapes.medium)
                        .background(Moss),
                ) {
                    AsyncImage(
                        model = album.coverUri,
                        contentDescription = null,
                        imageLoader = imageLoader,
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop,
                    )
                    Box(
                        Modifier
                            .fillMaxSize()
                            .background(
                                Brush.verticalGradient(
                                    listOf(Color.Transparent, Color(0x8A10291D)),
                                    startY = 90f,
                                )
                            )
                    )
                    Text(
                        "${album.items.size}",
                        style = MaterialTheme.typography.labelMedium,
                        color = Paper,
                        modifier = Modifier.align(Alignment.BottomEnd).padding(10.dp),
                    )
                }
                Text(
                    album.name,
                    style = MaterialTheme.typography.titleMedium,
                    color = Ink,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 7.dp),
                )
            }
        }
    }
}

@Composable
private fun LocalMediaGrid(
    album: LocalMediaAlbum,
    imageLoader: ImageLoader,
    selectedUris: List<String>,
    onToggle: (String) -> Unit,
    onSelectAlbum: () -> Unit,
    onClearAlbum: () -> Unit,
) {
    val selectedInAlbum = album.items.count { it.uri in selectedUris }
    LazyVerticalGrid(
        columns = GridCells.Fixed(3),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp),
        horizontalArrangement = Arrangement.spacedBy(2.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        item(span = { androidx.compose.foundation.lazy.grid.GridItemSpan(maxLineSpan) }) {
            Column(Modifier.background(Paper).padding(horizontal = 16.dp, vertical = 12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "${album.items.size} local file${if (album.items.size == 1) "" else "s"}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = InkMuted,
                        modifier = Modifier.weight(1f),
                    )
                    if (selectedInAlbum > 0) {
                        TextButton(onClick = onClearAlbum) { Text("Clear album") }
                    }
                    TextButton(onClick = onSelectAlbum) {
                        Text(if (album.items.size > MAX_LOCAL_MEDIA_SELECTION) "Select first 500" else "Select album")
                    }
                }
                Text(
                    "Original bytes are checked for embedded GPS before anything is saved.",
                    style = MaterialTheme.typography.bodySmall,
                    color = InkMuted,
                )
            }
        }
        items(album.items, key = LocalMediaItem::uri) { item ->
            val selectedIndex = selectedUris.indexOf(item.uri)
            Box(
                Modifier
                    .fillMaxWidth()
                    .aspectRatio(1f)
                    .background(Moss)
                    .clickable { onToggle(item.uri) },
            ) {
                val request = ImageRequest.Builder(LocalContext.current)
                    .data(item.uri)
                    .apply {
                        if (item.contentType.startsWith("video/")) videoFrameMillis(750)
                    }
                    .build()
                AsyncImage(
                    model = request,
                    contentDescription = item.displayName,
                    imageLoader = imageLoader,
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.Crop,
                )
                AnimatedVisibility(
                    visible = selectedIndex >= 0,
                    enter = fadeIn(tween(120)),
                    exit = fadeOut(tween(100)),
                ) {
                    Box(Modifier.fillMaxSize().background(Color(0x52183A2D))) {
                        Box(
                            Modifier
                                .align(Alignment.TopEnd)
                                .padding(7.dp)
                                .size(27.dp)
                                .clip(MaterialTheme.shapes.extraLarge)
                                .background(Trail),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                "${selectedIndex + 1}",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = Paper,
                            )
                        }
                    }
                }
                AnimatedVisibility(
                    visible = selectedIndex < 0,
                    enter = fadeIn(tween(120)),
                    exit = fadeOut(tween(100)),
                    modifier = Modifier.align(Alignment.TopEnd),
                ) {
                    Box(
                        Modifier
                            .padding(8.dp)
                            .size(23.dp)
                            .clip(MaterialTheme.shapes.extraLarge)
                            .background(Color(0x66000000)),
                    )
                }
                if (item.contentType.startsWith("video/")) {
                    Icon(
                        Icons.Rounded.PlayArrow,
                        "Video",
                        tint = Paper,
                        modifier = Modifier.align(Alignment.BottomStart).padding(7.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun LocalMediaMessage(title: String, detail: String) {
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 28.dp, vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(title, style = MaterialTheme.typography.headlineMedium, color = Ink)
        Text(
            detail,
            style = MaterialTheme.typography.bodyMedium,
            color = InkMuted,
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}
