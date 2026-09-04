@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.hikejournal.app.ui

import android.net.Uri
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
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
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.ImageLoader
import coil.compose.AsyncImage
import coil.decode.VideoFrameDecoder
import coil.request.ImageRequest
import coil.request.videoFrameMillis
import com.hikejournal.app.data.LocalMediaItem
import com.hikejournal.app.data.MAX_LOCAL_MEDIA_SELECTION
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
    selectedUris: List<Uri>,
    onDismiss: () -> Unit,
    onChooseMore: (List<Uri>) -> Unit,
    onConfirm: (List<Uri>) -> Unit,
) {
    val context = LocalContext.current
    val imageLoader = remember {
        ImageLoader.Builder(context)
            .components { add(VideoFrameDecoder.Factory()) }
            .build()
    }
    var selectedStrings by remember(selectedUris) {
        mutableStateOf(selectedUris.map(Uri::toString))
    }
    var selectionNotice by remember { mutableStateOf<String?>(null) }
    val mediaItems = remember(selectedUris) {
        selectedUris.mapIndexed { index, uri ->
            LocalMediaItem(
                uri = uri.toString(),
                displayName = uri.lastPathSegment?.substringAfterLast('/')
                    ?.takeIf(String::isNotBlank)
                    ?: "Selected media ${index + 1}",
                contentType = context.contentResolver.getType(uri).orEmpty()
                    .ifBlank { "image/jpeg" },
                albumId = "selected",
                albumName = "Selected media",
                takenAtMillis = 0L,
                sizeBytes = 0L,
            )
        }
    }

    DisposableEffect(imageLoader) {
        onDispose { imageLoader.shutdown() }
    }
    Dialog(
        onDismissRequest = onDismiss,
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
                        IconButton(onClick = onDismiss) {
                            Icon(Icons.Rounded.Close, "Close", tint = Ink)
                        }
                        Column(Modifier.weight(1f)) {
                            Text(
                                "PHONE ORIGINALS",
                                style = MaterialTheme.typography.labelSmall,
                                color = TrailText,
                            )
                            Text(
                                "Selected media",
                                style = MaterialTheme.typography.titleLarge,
                                color = Ink,
                            )
                        }
                        Text(
                            "${selectedStrings.size} selected",
                            style = MaterialTheme.typography.labelMedium,
                            color = Moss,
                            modifier = Modifier.padding(end = 12.dp),
                        )
                    }
                    HorizontalDivider(color = Line)
                }
            },
            bottomBar = {
                Surface(color = Paper, shadowElevation = 10.dp) {
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .windowInsetsPadding(
                                WindowInsets.safeDrawing.only(WindowInsetsSides.Bottom),
                            )
                            .padding(start = 16.dp, top = 10.dp, end = 16.dp, bottom = 24.dp),
                    ) {
                        Row(
                            Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            TextButton(
                                onClick = { onChooseMore(selectedStrings.map(Uri::parse)) },
                                modifier = Modifier.weight(1f).height(54.dp),
                            ) {
                                Text("Choose more")
                            }
                            Button(
                                onClick = { onConfirm(selectedStrings.map(Uri::parse)) },
                                enabled = selectedStrings.isNotEmpty(),
                                modifier = Modifier.weight(1f).height(54.dp),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = Moss,
                                    contentColor = Paper,
                                    disabledContainerColor = Moss.copy(alpha = 0.36f),
                                    disabledContentColor = Paper.copy(alpha = 0.78f),
                                ),
                            ) {
                                Icon(Icons.Rounded.Check, null)
                                Spacer(Modifier.size(8.dp))
                                Text(
                                    "Add ${selectedStrings.size}",
                                    fontWeight = FontWeight.Bold,
                                )
                            }
                        }
                        selectionNotice?.let {
                            Text(
                                it,
                                style = MaterialTheme.typography.bodySmall,
                                color = TrailText,
                                modifier = Modifier.padding(top = 8.dp),
                            )
                        }
                    }
                }
            },
        ) { innerPadding ->
            LazyVerticalGrid(
                columns = GridCells.Fixed(3),
                modifier = Modifier.fillMaxSize().padding(innerPadding),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp),
                horizontalArrangement = Arrangement.spacedBy(2.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                item(span = { GridItemSpan(maxLineSpan) }) {
                    Column(
                        Modifier.background(Paper).padding(horizontal = 16.dp, vertical = 14.dp),
                    ) {
                        Text(
                            "Review phone originals",
                            style = MaterialTheme.typography.headlineSmall,
                            color = Ink,
                        )
                        Text(
                            "These are the files you selected in Android's Photo Picker. HikeJournal checks the original bytes for embedded GPS before upload.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = InkMuted,
                            modifier = Modifier.padding(top = 5.dp),
                        )
                    }
                }
                items(mediaItems, key = LocalMediaItem::uri) { item ->
                    val selectedIndex = selectedStrings.indexOf(item.uri)
                    Box(
                        Modifier
                            .fillMaxWidth()
                            .aspectRatio(1f)
                            .background(Moss)
                            .clickable {
                                selectionNotice = null
                                selectedStrings = if (selectedIndex >= 0) {
                                    selectedStrings.filterNot { it == item.uri }
                                } else if (selectedStrings.size < MAX_LOCAL_MEDIA_SELECTION) {
                                    selectedStrings + item.uri
                                } else {
                                    selectionNotice =
                                        "You can upload up to $MAX_LOCAL_MEDIA_SELECTION files at a time."
                                    selectedStrings
                                }
                            },
                    ) {
                        val request = ImageRequest.Builder(context)
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
                            enter = fadeIn(),
                            exit = fadeOut(),
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
    }
}
