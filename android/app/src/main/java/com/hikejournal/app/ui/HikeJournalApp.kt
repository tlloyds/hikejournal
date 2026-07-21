@file:OptIn(
    androidx.compose.animation.ExperimentalAnimationApi::class,
    androidx.compose.foundation.ExperimentalFoundationApi::class,
    androidx.compose.material3.ExperimentalMaterial3Api::class,
)

package com.hikejournal.app.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts.PickMultipleVisualMedia
import androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.FactCheck
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.Archive
import androidx.compose.material.icons.rounded.CameraAlt
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.CloudOff
import androidx.compose.material.icons.rounded.CloudQueue
import androidx.compose.material.icons.rounded.CloudSync
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.Edit
import androidx.compose.material.icons.rounded.Image
import androidx.compose.material.icons.rounded.LocationOn
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Unarchive
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.hikejournal.app.AppState
import com.hikejournal.app.AppViewModel
import com.hikejournal.app.BuildConfig
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.HikeDraft
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.SyncAttention
import com.hikejournal.app.ui.theme.Fern
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Lichen
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.TrailText
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale

@Composable
fun HikeJournalApp(viewModel: AppViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var destination by remember { mutableStateOf(TopDestination.Archive) }
    var editingHike by remember { mutableStateOf<Hike?>(null) }
    var creatingHike by remember { mutableStateOf(false) }
    var settingsOpen by remember { mutableStateOf(false) }
    var selectedPhoto by remember { mutableStateOf<Photo?>(null) }
    var pendingUpload by remember { mutableStateOf<List<Uri>>(emptyList()) }
    var syncAttentionOpen by remember { mutableStateOf(false) }

    LaunchedEffect(state.inatAuthorizationUrl) {
        state.inatAuthorizationUrl?.let { url ->
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            viewModel.consumeInatAuthorizationUrl()
        }
    }

    val photoPicker = rememberLauncherForActivityResult(PickMultipleVisualMedia(maxItems = 20)) { uris ->
        pendingUpload = uris
    }

    LaunchedEffect(destination) {
        when (destination) {
            TopDestination.Archive -> Unit
            TopDestination.Species -> viewModel.loadSpecies()
            TopDestination.Review -> viewModel.loadReviewQueue()
            TopDestination.Publish -> viewModel.loadPublishQueue()
            TopDestination.Map -> viewModel.loadSightings()
        }
    }

    val screenKey = when {
        state.journal != null -> "journal:${state.journal?.id}"
        state.speciesDetail != null -> "species:${state.speciesDetail?.key}"
        else -> destination.name
    }

    Box(Modifier.fillMaxSize().background(Parchment)) {
        AnimatedContent(
            targetState = screenKey,
            transitionSpec = {
                (fadeIn(tween(280)) + slideInVertically(tween(320)) { it / 12 }) togetherWith
                    fadeOut(tween(180))
            },
            label = "journal-navigation",
        ) { key ->
            when {
                key.startsWith("journal:") && state.journal != null -> {
                    val journal = state.journal!!
                    JournalScreen(
                        hike = journal,
                        state = state,
                        onBack = viewModel::closeJournal,
                        onEdit = { editingHike = journal },
                        onArchive = { viewModel.setArchived(journal) },
                        onAddPhotos = {
                            photoPicker.launch(PickVisualMediaRequest(PickVisualMedia.ImageOnly))
                        },
                        onPhoto = { selectedPhoto = it },
                    )
                }
                key.startsWith("species:") && state.speciesDetail != null -> {
                    SpeciesDetailScreen(
                        species = state.speciesDetail!!,
                        loading = state.isSpeciesLoading,
                        onBack = viewModel::closeSpecies,
                        onOpenHike = viewModel::openEncounterHike,
                    )
                }
                destination == TopDestination.Species -> SpeciesIndexScreen(
                    species = state.species,
                    hikes = state.hikes,
                    loading = state.isSpeciesLoading,
                    offline = state.isOffline,
                    onRefresh = { viewModel.loadSpecies(force = true) },
                    onOpenSpecies = viewModel::openSpecies,
                )
                destination == TopDestination.Review -> SpeciesReviewScreen(
                    queue = state.reviewQueue,
                    loading = state.isReviewLoading,
                    decidingId = state.decidingReviewId,
                    identifyingId = state.identifyingReviewId,
                    offline = state.isOffline,
                    onRefresh = { viewModel.loadReviewQueue(force = true) },
                    onDecision = viewModel::decideReview,
                    onRequestRecommendation = viewModel::requestReviewRecommendation,
                    onConnectInat = viewModel::connectInat,
                )
                destination == TopDestination.Publish -> PublishingScreen(
                    queue = state.publishQueue,
                    hikes = state.hikes,
                    loading = state.isPublishLoading,
                    publishingId = state.publishingId,
                    notice = state.publishNotice,
                    offline = state.isOffline,
                    onRefresh = { viewModel.loadPublishQueue(force = true) },
                    onPublish = viewModel::publishObservation,
                    onClearNotice = viewModel::clearPublishNotice,
                )
                destination == TopDestination.Map -> SightingsMapScreen(
                    sightings = state.sightings,
                    loading = state.isMapLoading,
                    onRefresh = { viewModel.loadSightings(force = true) },
                    onOpenHike = viewModel::openEncounterHike,
                )
                else -> LibraryScreen(
                    state = state,
                    onOpenHike = viewModel::openHike,
                    onRefresh = { viewModel.refreshLibrary() },
                    onCreate = { creatingHike = true },
                    onSettings = { settingsOpen = true },
                    onSync = viewModel::syncNow,
                    onRetrySync = viewModel::retrySyncAttention,
                    onShowSyncAttention = { syncAttentionOpen = true },
                )
            }
        }

        if (state.journal == null && state.speciesDetail == null) {
            TopNavigation(
                selected = destination,
                onSelect = { destination = it },
                modifier = Modifier.align(Alignment.BottomCenter),
            )
        }

        AnimatedVisibility(
            visible = state.error != null,
            modifier = Modifier.align(Alignment.BottomCenter),
            enter = slideInVertically { it } + fadeIn(),
            exit = fadeOut(),
        ) {
            ErrorBanner(message = state.error.orEmpty(), onDismiss = viewModel::clearError)
        }
    }

    if (creatingHike || editingHike != null) {
        HikeEditorSheet(
            hike = editingHike,
            saving = state.isRefreshing,
            onDismiss = {
                creatingHike = false
                editingHike = null
            },
            onSave = { draft ->
                viewModel.saveHike(draft, editingHike?.id) {
                    creatingHike = false
                    editingHike = null
                }
            },
        )
    }

    if (pendingUpload.isNotEmpty() && state.journal != null) {
        UploadSheet(
            photoCount = pendingUpload.size,
            onDismiss = { pendingUpload = emptyList() },
            onUpload = { caption, queue ->
                viewModel.uploadPhotos(state.journal!!.id, pendingUpload, caption, queue)
                pendingUpload = emptyList()
            },
        )
    }

    selectedPhoto?.let { selected ->
        val photo = state.journal?.photos?.firstOrNull { it.id == selected.id } ?: selected
        PhotoViewer(
            photo = photo,
            queuingReview = state.queuingReviewId == photo.id,
            onDismiss = { selectedPhoto = null },
            onSaveCaption = { caption ->
                viewModel.updateCaption(photo.id, caption)
                selectedPhoto = null
            },
            onDelete = {
                viewModel.deletePhoto(photo.id)
                selectedPhoto = null
            },
            onQueueReview = { viewModel.queueSpeciesReview(photo) },
        )
    }

    if (settingsOpen) {
        SettingsDialog(
            currentUrl = viewModel.serverUrl,
            currentKey = viewModel.pairingKey,
            onDismiss = { settingsOpen = false },
            onSave = { url, key ->
                viewModel.updateConnection(url, key)
                settingsOpen = false
            },
        )
    }

    if (syncAttentionOpen) {
        SyncAttentionSheet(
            items = state.syncStatus.attentionItems,
            onRetry = viewModel::retrySyncAttention,
            onClear = viewModel::clearSyncAttention,
            onDismiss = { syncAttentionOpen = false },
        )
    }
}

@Composable
private fun LibraryScreen(
    state: AppState,
    onOpenHike: (String) -> Unit,
    onRefresh: () -> Unit,
    onCreate: () -> Unit,
    onSettings: () -> Unit,
    onSync: () -> Unit,
    onRetrySync: () -> Unit,
    onShowSyncAttention: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var showArchived by remember { mutableStateOf(false) }
    val visibleHikes = state.hikes.filter { hike ->
        (showArchived || !hike.isArchived) && listOf(hike.title, hike.locationName, hike.notes)
            .any { it.contains(query, ignoreCase = true) }
    }
    val featured = visibleHikes.firstOrNull()
    val remaining = visibleHikes.drop(1)

    Scaffold(
        containerColor = Parchment,
        floatingActionButton = {
            FloatingActionButton(
                onClick = onCreate,
                containerColor = Trail,
                contentColor = Paper,
                shape = CircleShape,
                modifier = Modifier.padding(bottom = 84.dp).navigationBarsPadding(),
            ) { Icon(Icons.Rounded.Add, contentDescription = "Create hike") }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = padding.calculateBottomPadding() + 96.dp),
        ) {
            item {
                LibraryHeader(
                    hikeCount = state.hikes.count { !it.isArchived },
                    offline = state.isOffline,
                    refreshing = state.isRefreshing,
                    onRefresh = onRefresh,
                    onSettings = onSettings,
                )
            }
            item {
                SyncStrip(
                    status = state.syncStatus,
                    syncing = state.isSyncing,
                    onSync = onSync,
                    onRetry = onRetrySync,
                    onShowAttention = onShowSyncAttention,
                )
            }
            item {
                SearchLine(query = query, onQueryChange = { query = it })
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        if (showArchived) "CURRENT + ARCHIVED" else "CURRENT OUTINGS",
                        style = MaterialTheme.typography.labelSmall,
                        color = InkMuted,
                    )
                    TextButton(onClick = { showArchived = !showArchived }) {
                        Text(if (showArchived) "Hide archived" else "Show archived")
                    }
                }
            }
            if (state.isLoading && state.hikes.isEmpty()) {
                item { LoadingFieldNotes() }
            } else if (featured == null) {
                item { EmptyLibrary(onCreate) }
            } else {
                item { FeaturedHike(featured, onOpenHike) }
                items(remaining, key = { it.id }) { hike ->
                    HikeRow(hike, onOpenHike)
                }
            }
        }
    }
}

@Composable
private fun LibraryHeader(
    hikeCount: Int,
    offline: Boolean,
    refreshing: Boolean,
    onRefresh: () -> Unit,
    onSettings: () -> Unit,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(Moss)
            .statusBarsPadding()
            .padding(start = 20.dp, end = 8.dp, top = 18.dp, bottom = 22.dp),
    ) {
        Row(verticalAlignment = Alignment.Top) {
            Column(Modifier.weight(1f)) {
                Text("HikeJournal", style = MaterialTheme.typography.displayMedium, color = Paper)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "$hikeCount OUTINGS · FIELD ARCHIVE",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFFB8C9B6),
                    )
                    if (offline) {
                        Spacer(Modifier.width(10.dp))
                        Icon(Icons.Rounded.CloudOff, null, tint = Trail, modifier = Modifier.size(15.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("OFFLINE", style = MaterialTheme.typography.labelSmall, color = TrailText)
                    }
                }
            }
            IconButton(onClick = onRefresh, enabled = !refreshing) {
                if (refreshing) CircularProgressIndicator(Modifier.size(20.dp), color = Paper, strokeWidth = 2.dp)
                else Icon(Icons.Rounded.Refresh, "Refresh", tint = Paper)
            }
            IconButton(onClick = onSettings) {
                Icon(Icons.Rounded.Settings, "Settings", tint = Paper)
            }
        }
    }
}

@Composable
private fun SyncStrip(
    status: com.hikejournal.app.data.SyncStatus,
    syncing: Boolean,
    onSync: () -> Unit,
    onRetry: () -> Unit,
    onShowAttention: () -> Unit,
) {
    val queued = status.pendingCount + status.syncingCount
    val background = when {
        status.needsAttentionCount > 0 -> Color(0xFFF0D8CC)
        queued > 0 -> Color(0xFFDDE5D8)
        else -> Parchment
    }
    Row(
        Modifier.fillMaxWidth().background(background).padding(horizontal = 20.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            when {
                !status.connected -> Icons.Rounded.CloudOff
                syncing || status.syncingCount > 0 -> Icons.Rounded.CloudSync
                else -> Icons.Rounded.CloudQueue
            },
            null,
            tint = if (status.needsAttentionCount > 0) Color(0xFF8F3D32) else Moss,
            modifier = Modifier.size(20.dp),
        )
        Column(Modifier.weight(1f).padding(start = 10.dp)) {
            Text(
                when {
                    status.needsAttentionCount > 0 -> "${status.needsAttentionCount} change${if (status.needsAttentionCount == 1) "" else "s"} need attention"
                    syncing || status.syncingCount > 0 -> "Syncing field notes…"
                    queued > 0 && !status.connected -> "Offline · $queued change${if (queued == 1) "" else "s"} saved"
                    queued > 0 -> "$queued change${if (queued == 1) "" else "s"} ready to sync"
                    else -> "Field journal is up to date"
                },
                style = MaterialTheme.typography.titleSmall,
                color = Ink,
            )
            Text(
                if (status.connected) "Photos and notes sync safely in the background." else "Keep hiking—everything here is stored on this phone.",
                style = MaterialTheme.typography.bodySmall,
                color = InkMuted,
            )
        }
        when {
            status.needsAttentionCount > 0 -> TextButton(onClick = onShowAttention) { Text("Review") }
            queued > 0 && status.connected -> TextButton(onClick = onSync, enabled = !syncing) { Text("Sync") }
        }
    }
}

@Composable
private fun SyncAttentionSheet(
    items: List<SyncAttention>,
    onRetry: () -> Unit,
    onClear: () -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Paper) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).navigationBarsPadding().padding(horizontal = 20.dp).padding(bottom = 28.dp),
        ) {
            Text("SYNC ATTENTION", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text("Changes that could not sync", style = MaterialTheme.typography.headlineLarge, color = Ink)
            Text(
                "These changes remain safely on this phone. Review the server response below, then retry after correcting the cause.",
                style = MaterialTheme.typography.bodyMedium,
                color = InkMuted,
                modifier = Modifier.padding(top = 5.dp),
            )
            items.forEach { item ->
                Column(Modifier.fillMaxWidth().padding(top = 18.dp)) {
                    Text(syncOperationLabel(item.kind), style = MaterialTheme.typography.titleMedium, color = Ink)
                    Text(item.error, style = MaterialTheme.typography.bodyMedium, color = Color(0xFF8F3D32), modifier = Modifier.padding(top = 3.dp))
                }
            }
            Button(onClick = { onRetry(); onDismiss() }, modifier = Modifier.fillMaxWidth().padding(top = 24.dp)) {
                Text("Retry all changes")
            }
            OutlinedButton(
                onClick = { onClear(); onDismiss() },
                modifier = Modifier.fillMaxWidth().padding(top = 9.dp),
            ) {
                Text("Clear errors")
            }
            TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth().padding(top = 3.dp)) { Text("Close") }
        }
    }
}

private fun syncOperationLabel(kind: String): String = when (kind) {
    "create_hike" -> "Create outing"
    "update_hike" -> "Update outing"
    "archive_hike" -> "Archive outing"
    "upload_photo" -> "Upload photo"
    "update_caption" -> "Save photo note"
    "delete_photo" -> "Delete photo"
    "queue_species_review" -> "Queue species review"
    "review_decision" -> "Save species decision"
    else -> "Sync change"
}

@Composable
private fun SearchLine(query: String, onQueryChange: (String) -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Rounded.Search, null, tint = InkMuted, modifier = Modifier.size(21.dp))
        OutlinedTextField(
            value = query,
            onValueChange = onQueryChange,
            modifier = Modifier.weight(1f).padding(start = 6.dp),
            placeholder = { Text("Search places, trails, and notes") },
            singleLine = true,
            shape = RoundedCornerShape(4.dp),
        )
    }
}

@Composable
private fun FeaturedHike(hike: Hike, onOpen: (String) -> Unit) {
    Box(
        Modifier
            .fillMaxWidth()
            .height(390.dp)
            .clickable { onOpen(hike.id) }
            .background(MossSoftFallback),
    ) {
        if (hike.coverUrl.isNotBlank()) {
            AsyncImage(
                model = ImageRequest.Builder(LocalContext.current).data(hike.coverUrl).crossfade(400).build(),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            MountainField(Modifier.fillMaxSize())
        }
        Box(
            Modifier.fillMaxSize().background(
                Brush.verticalGradient(
                    0f to Color.Transparent,
                    .45f to Color.Transparent,
                    1f to Color(0xE817271F),
                ),
            ),
        )
        Column(Modifier.align(Alignment.BottomStart).padding(22.dp)) {
            if (hike.syncState != "synced") {
                Text("SAVED ON PHONE", style = MaterialTheme.typography.labelSmall, color = TrailText)
            }
            Text(formatDate(hike.hikeDate).uppercase(Locale.US), style = MaterialTheme.typography.labelSmall, color = Color(0xFFD7DFD2))
            Text(
                hike.title,
                style = MaterialTheme.typography.headlineLarge,
                color = Paper,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(5.dp))
            Text(
                hikeMeta(hike),
                style = MaterialTheme.typography.bodyMedium,
                color = Color(0xFFE4E9DF),
            )
        }
    }
}

@Composable
private fun HikeRow(hike: Hike, onOpen: (String) -> Unit) {
    Column(Modifier.clickable { onOpen(hike.id) }) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 15.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(Modifier.size(88.dp).background(Moss)) {
                if (hike.coverUrl.isNotBlank()) {
                    AsyncImage(hike.coverUrl, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                } else {
                    MountainField(Modifier.fillMaxSize())
                }
            }
            Column(Modifier.weight(1f).padding(start = 16.dp)) {
                if (hike.syncState != "synced") {
                    Text("SAVED ON PHONE", style = MaterialTheme.typography.labelSmall, color = Moss)
                }
                Text(formatDate(hike.hikeDate).uppercase(Locale.US), style = MaterialTheme.typography.labelSmall, color = TrailText)
                Text(hike.title, style = MaterialTheme.typography.titleLarge, color = Ink, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(hikeMeta(hike), style = MaterialTheme.typography.bodyMedium, color = InkMuted, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Text(hike.photoCount.toString().padStart(2, '0'), style = MaterialTheme.typography.headlineSmall, color = Fern)
        }
        HorizontalDivider(color = Line, modifier = Modifier.padding(start = 124.dp))
    }
}

@Composable
private fun JournalScreen(
    hike: Hike,
    state: AppState,
    onBack: () -> Unit,
    onEdit: () -> Unit,
    onArchive: () -> Unit,
    onAddPhotos: () -> Unit,
    onPhoto: (Photo) -> Unit,
) {
    LazyColumn(
        Modifier.fillMaxSize().background(Parchment),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 64.dp),
    ) {
        item { JournalHero(hike, onBack, onEdit, onArchive) }
        item {
            Column(Modifier.padding(horizontal = 20.dp, vertical = 24.dp)) {
                Text(formatDate(hike.hikeDate).uppercase(Locale.US), style = MaterialTheme.typography.labelSmall, color = TrailText)
                Text(hike.title, style = MaterialTheme.typography.displayMedium, color = Ink)
                if (hike.locationName.isNotBlank()) {
                    Row(Modifier.padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Rounded.LocationOn, null, tint = Fern, modifier = Modifier.size(18.dp))
                        Text(hikeMeta(hike), style = MaterialTheme.typography.bodyMedium, color = InkMuted)
                    }
                }
                if (hike.notes.isNotBlank()) {
                    Text(
                        hike.notes,
                        style = MaterialTheme.typography.bodyLarge,
                        color = Ink,
                        modifier = Modifier.padding(top = 22.dp),
                    )
                }
                Row(Modifier.fillMaxWidth().padding(top = 24.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(onClick = onAddPhotos, colors = ButtonDefaults.buttonColors(containerColor = Moss)) {
                        Icon(Icons.Rounded.CameraAlt, null, Modifier.size(19.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Add photos")
                    }
                    OutlinedButton(onClick = onEdit) {
                        Icon(Icons.Rounded.Edit, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(7.dp))
                        Text("Edit notes")
                    }
                }
                if (state.uploadTotal > 0) {
                    Column(Modifier.fillMaxWidth().padding(top = 18.dp)) {
                        Text("Saving ${state.uploadCurrent + 1} of ${state.uploadTotal} on this phone", style = MaterialTheme.typography.labelMedium, color = Moss)
                        LinearProgressIndicator(
                            progress = { state.uploadCurrent.toFloat() / state.uploadTotal.coerceAtLeast(1) },
                            modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
                            color = Trail,
                        )
                    }
                }
            }
        }
        item {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Bottom,
            ) {
                Column {
                    Text("FIELD NOTES", style = MaterialTheme.typography.labelSmall, color = TrailText)
                    Text("Photo journal", style = MaterialTheme.typography.headlineMedium, color = Ink)
                }
                Text("${hike.photos.size} frames", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
            }
        }
        if (hike.photos.isEmpty()) {
            item { EmptyPhotos(onAddPhotos) }
        } else {
            items(hike.photos.chunked(2), key = { row -> row.joinToString { it.id } }) { rowPhotos ->
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    rowPhotos.forEach { photo ->
                        PhotoTile(photo, Modifier.weight(1f), onPhoto)
                    }
                    if (rowPhotos.size == 1) Spacer(Modifier.weight(1f))
                }
            }
        }
        item { WebDeskLink(hike) }
    }
}

@Composable
private fun JournalHero(hike: Hike, onBack: () -> Unit, onEdit: () -> Unit, onArchive: () -> Unit) {
    Box(Modifier.fillMaxWidth().height(330.dp).background(Moss)) {
        if (hike.coverUrl.isNotBlank()) {
            AsyncImage(hike.coverUrl, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        } else {
            MountainField(Modifier.fillMaxSize())
        }
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xA0000000), Color.Transparent, Color(0x66000000)))))
        Row(
            Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 8.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            FilledIconButton(onClick = onBack, colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(containerColor = Color(0x99172820))) {
                Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back", tint = Paper)
            }
            Spacer(Modifier.weight(1f))
            FilledIconButton(onClick = onEdit, colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(containerColor = Color(0x99172820))) {
                Icon(Icons.Rounded.Edit, "Edit hike", tint = Paper)
            }
            Spacer(Modifier.width(6.dp))
            FilledIconButton(onClick = onArchive, colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(containerColor = Color(0x99172820))) {
                Icon(if (hike.isArchived) Icons.Rounded.Unarchive else Icons.Rounded.Archive, "Archive hike", tint = Paper)
            }
        }
        Text("HikeJournal", style = MaterialTheme.typography.headlineSmall, color = Paper, modifier = Modifier.align(Alignment.BottomStart).padding(20.dp))
    }
}

@Composable
private fun PhotoTile(photo: Photo, modifier: Modifier, onPhoto: (Photo) -> Unit) {
    Column(modifier.clickable { onPhoto(photo) }) {
        Box(Modifier.fillMaxWidth().height(190.dp).background(Moss)) {
            AsyncImage(
                model = ImageRequest.Builder(LocalContext.current).data(photo.url).crossfade(true).build(),
                contentDescription = photo.caption.ifBlank { "Hike photo" },
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
            if (photo.processingStatus == "in_review") {
                Box(Modifier.align(Alignment.TopEnd).padding(8.dp).background(Trail, RoundedCornerShape(2.dp)).padding(horizontal = 7.dp, vertical = 3.dp)) {
                    Text("REVIEW", style = MaterialTheme.typography.labelSmall, color = Paper)
                }
            }
            if (photo.syncState != "synced") {
                Box(Modifier.align(Alignment.BottomStart).padding(8.dp).background(Moss, RoundedCornerShape(2.dp)).padding(horizontal = 7.dp, vertical = 3.dp)) {
                    Text(if (photo.syncState == "needs_attention") "ATTENTION" else "SAVED", style = MaterialTheme.typography.labelSmall, color = Paper)
                }
            }
        }
        val speciesName = photo.species.firstOrNull { it.isPrimary }?.commonName
            ?: photo.species.firstOrNull()?.commonName
        Text(
            speciesName?.takeIf { it.isNotBlank() } ?: photo.caption.ifBlank { formatTakenAt(photo.takenAt) },
            style = MaterialTheme.typography.bodyMedium,
            color = if (speciesName.isNullOrBlank()) InkMuted else Moss,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 7.dp, bottom = 8.dp),
        )
    }
}

@Composable
private fun HikeEditorSheet(hike: Hike?, saving: Boolean, onDismiss: () -> Unit, onSave: (HikeDraft) -> Unit) {
    var title by remember(hike?.id) { mutableStateOf(hike?.title.orEmpty()) }
    var date by remember(hike?.id) { mutableStateOf(hike?.hikeDate ?: LocalDate.now().toString()) }
    var location by remember(hike?.id) { mutableStateOf(hike?.locationName.orEmpty()) }
    var distance by remember(hike?.id) { mutableStateOf(hike?.distanceMiles?.toString().orEmpty()) }
    var notes by remember(hike?.id) { mutableStateOf(hike?.notes.orEmpty()) }
    var validation by remember { mutableStateOf<String?>(null) }
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = sheetState, containerColor = Paper) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).imePadding().padding(horizontal = 20.dp).padding(bottom = 36.dp),
        ) {
            Text(if (hike == null) "NEW FIELD NOTE" else "EDIT OUTING", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text(if (hike == null) "Create a hike" else "Refine the journal", style = MaterialTheme.typography.headlineLarge, color = Ink)
            Spacer(Modifier.height(18.dp))
            OutlinedTextField(title, { title = it }, Modifier.fillMaxWidth(), label = { Text("Hike title") }, singleLine = true)
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(date, { date = it }, Modifier.fillMaxWidth(), label = { Text("Date · YYYY-MM-DD") }, singleLine = true)
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(location, { location = it }, Modifier.fillMaxWidth(), label = { Text("Location") }, singleLine = true)
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                distance,
                { distance = it },
                Modifier.fillMaxWidth(),
                label = { Text("Distance in miles") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
            )
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(notes, { notes = it }, Modifier.fillMaxWidth().height(150.dp), label = { Text("Opening notes") })
            validation?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 10.dp)) }
            Button(
                onClick = {
                    when {
                        title.isBlank() -> validation = "Give this outing a title."
                        !isValidDate(date) -> validation = "Use a date like 2026-07-12."
                        else -> onSave(HikeDraft(title.trim(), date, distance.toDoubleOrNull(), location.trim(), notes.trim()))
                    }
                },
                enabled = !saving,
                modifier = Modifier.fillMaxWidth().padding(top = 20.dp).height(54.dp),
            ) {
                if (saving) CircularProgressIndicator(Modifier.size(20.dp), color = Paper, strokeWidth = 2.dp)
                else Text(if (hike == null) "Create hike" else "Save changes")
            }
        }
    }
}

@Composable
private fun UploadSheet(photoCount: Int, onDismiss: () -> Unit, onUpload: (String, Boolean) -> Unit) {
    var caption by remember { mutableStateOf("") }
    var queueForReview by remember { mutableStateOf(false) }
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Paper) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
            Text("$photoCount FRAME${if (photoCount == 1) "" else "S"} SELECTED", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text("Add to this journal", style = MaterialTheme.typography.headlineLarge, color = Ink)
            Text("Each original is secured on this phone now, including its date and GPS. Sync resumes automatically on any connection.", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 6.dp))
            OutlinedTextField(caption, { caption = it }, Modifier.fillMaxWidth().padding(top = 18.dp), label = { Text("Shared caption · optional") })
            Row(Modifier.fillMaxWidth().padding(vertical = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Queue for species review", style = MaterialTheme.typography.titleMedium)
                    Text("Review in Android or the web workspace", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
                }
                Switch(queueForReview, { queueForReview = it })
            }
            Button(onClick = { onUpload(caption, queueForReview) }, Modifier.fillMaxWidth().height(54.dp)) {
                Icon(Icons.Rounded.CameraAlt, null)
                Spacer(Modifier.width(8.dp))
                Text("Save $photoCount photo${if (photoCount == 1) "" else "s"}")
            }
        }
    }
}

@Composable
private fun PhotoViewer(
    photo: Photo,
    queuingReview: Boolean,
    onDismiss: () -> Unit,
    onSaveCaption: (String) -> Unit,
    onDelete: () -> Unit,
    onQueueReview: () -> Unit,
) {
    var caption by remember(photo.id) { mutableStateOf(photo.caption) }
    var confirmDelete by remember { mutableStateOf(false) }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Column(Modifier.fillMaxSize().background(Color(0xFF101511)).statusBarsPadding()) {
            Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onDismiss) { Icon(Icons.Rounded.Close, "Close", tint = Paper) }
                Text("HikeJournal", style = MaterialTheme.typography.headlineSmall, color = Paper, modifier = Modifier.weight(1f))
                IconButton(onClick = { confirmDelete = true }) { Icon(Icons.Rounded.DeleteOutline, "Delete", tint = Color(0xFFE8A18F)) }
            }
            Box(Modifier.fillMaxWidth().weight(1f)) {
                AsyncImage(photo.url, photo.caption, Modifier.fillMaxSize(), contentScale = ContentScale.Fit)
            }
            Column(
                Modifier
                    .fillMaxWidth()
                    .heightIn(min = 390.dp, max = 430.dp)
                    .background(Color(0xFF18221C))
                    .verticalScroll(rememberScrollState())
                    .imePadding()
                    .navigationBarsPadding()
                    .padding(16.dp),
            ) {
                photo.species.firstOrNull()?.let { species ->
                    Text(species.commonName.ifBlank { species.scientificName }, style = MaterialTheme.typography.titleMedium, color = Color(0xFFBFD2B9))
                }
                AnimatedContent(
                    targetState = photo.processingStatus == "in_review",
                    modifier = Modifier.padding(top = 10.dp),
                    label = "photo-review-state",
                ) { inReview ->
                    if (inReview) {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.AutoMirrored.Rounded.FactCheck, null, tint = Trail, modifier = Modifier.size(25.dp))
                            Column(Modifier.padding(start = 10.dp)) {
                                Text("In species review", style = MaterialTheme.typography.titleMedium, color = Paper)
                                Text(
                                    if (photo.syncState == "synced") {
                                        "Ready in the shared Review workspace."
                                    } else {
                                        "Saved on this phone and will sync automatically."
                                    },
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = Color(0xFFBFD2B9),
                                )
                            }
                        }
                    } else {
                        Column {
                            OutlinedButton(
                                onClick = onQueueReview,
                                enabled = !queuingReview,
                                modifier = Modifier.fillMaxWidth().height(50.dp),
                                border = BorderStroke(1.dp, Color(0xFF91AA8C)),
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = Paper),
                            ) {
                                if (queuingReview) {
                                    CircularProgressIndicator(Modifier.size(18.dp), color = Paper, strokeWidth = 2.dp)
                                } else {
                                    Icon(Icons.AutoMirrored.Rounded.FactCheck, null)
                                }
                                Spacer(Modifier.width(8.dp))
                                Text(if (queuingReview) "Adding to review…" else "Send to species review")
                            }
                            Text(
                                "Shared with Android and Streamlit; syncs automatically.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = Color(0xFFBFD2B9),
                                modifier = Modifier.padding(top = 7.dp),
                            )
                        }
                    }
                }
                HorizontalDivider(color = Color(0xFF405148), modifier = Modifier.padding(vertical = 13.dp))
                OutlinedTextField(
                    caption,
                    { caption = it },
                    Modifier.fillMaxWidth(),
                    label = { Text("Photo note") },
                    textStyle = MaterialTheme.typography.bodyLarge.copy(color = Paper),
                )
                Button(onClick = { onSaveCaption(caption) }, Modifier.fillMaxWidth().padding(top = 10.dp)) { Text("Save note") }
            }
        }
    }
    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete this photo?") },
            text = { Text("This removes the database record and the R2 image. This cannot be undone.") },
            confirmButton = { TextButton(onClick = onDelete) { Text("Delete", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Keep photo") } },
        )
    }
}

@Composable
private fun SettingsDialog(
    currentUrl: String,
    currentKey: String,
    onDismiss: () -> Unit,
    onSave: (String, String) -> Unit,
) {
    var url by remember(currentUrl) { mutableStateOf(currentUrl) }
    var key by remember(currentKey) { mutableStateOf(currentKey) }
    val context = LocalContext.current
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Companion connection", style = MaterialTheme.typography.headlineMedium) },
        text = {
            Column {
                Text("Use the Mac on home Wi-Fi, or paste the HTTPS address of your hosted companion for cellular access.", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
                OutlinedTextField(url, { url = it }, Modifier.fillMaxWidth().padding(top = 14.dp), label = { Text("Server address") }, singleLine = true)
                OutlinedTextField(
                    key,
                    { key = it },
                    Modifier.fillMaxWidth().padding(top = 10.dp),
                    label = { Text("Pairing key") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                )
                TextButton(
                    onClick = { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(BuildConfig.DEFAULT_WEB_URL))) },
                    modifier = Modifier.padding(top = 8.dp),
                ) {
                    Icon(Icons.AutoMirrored.Rounded.OpenInNew, null)
                    Spacer(Modifier.width(7.dp))
                    Text("Open Streamlit workspace")
                }
            }
        },
        confirmButton = { TextButton(onClick = { onSave(url, key) }) { Text("Reconnect") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun WebDeskLink(hike: Hike) {
    val context = LocalContext.current
    Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 40.dp)) {
        HorizontalDivider(color = Line)
        Text("DESKTOP WORKSPACE", style = MaterialTheme.typography.labelSmall, color = TrailText, modifier = Modifier.padding(top = 22.dp))
        Text("Continue on the big screen", style = MaterialTheme.typography.headlineMedium, color = Ink)
        Text("Streamlit remains the full archive workspace; Android and web now share the same reviews, maps, and iNaturalist records.", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 5.dp))
        TextButton(onClick = {
            val url = "${BuildConfig.DEFAULT_WEB_URL}/?view=Journal&hike=${hike.id}"
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        }) {
            Text("Open web journal")
            Spacer(Modifier.width(7.dp))
            Icon(Icons.AutoMirrored.Rounded.OpenInNew, null, Modifier.size(18.dp))
        }
    }
}

@Composable
private fun ErrorBanner(message: String, onDismiss: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().background(Color(0xFF8F3D32)).navigationBarsPadding().clickable(onClick = onDismiss).padding(horizontal = 18.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(message, color = Paper, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
        Icon(Icons.Rounded.Close, "Dismiss", tint = Paper)
    }
}

@Composable
private fun LoadingFieldNotes() {
    Column(Modifier.fillMaxWidth().padding(vertical = 90.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        CircularProgressIndicator(color = Moss, strokeWidth = 2.dp)
        Text("Opening the field archive…", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 14.dp))
    }
}

@Composable
private fun EmptyLibrary(onCreate: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 28.dp, vertical = 70.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        MountainField(Modifier.fillMaxWidth().height(180.dp))
        Text("No outings here yet", style = MaterialTheme.typography.headlineLarge, color = Ink)
        Text("Create the first field note and it will appear in Streamlit too.", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
        Button(onClick = onCreate, modifier = Modifier.padding(top = 18.dp)) { Text("Create a hike") }
    }
}

@Composable
private fun EmptyPhotos(onAdd: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 42.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(Icons.Rounded.Image, null, tint = Fern, modifier = Modifier.size(48.dp))
        Text("The first frame is waiting", style = MaterialTheme.typography.headlineSmall, color = Ink, modifier = Modifier.padding(top = 12.dp))
        TextButton(onClick = onAdd) { Text("Choose photos") }
    }
}

private val MossSoftFallback = Color(0xFF315844)

@Composable
private fun MountainField(modifier: Modifier = Modifier) {
    Canvas(modifier.background(Brush.linearGradient(listOf(Color(0xFF315844), Color(0xFF183A2D))))) {
        val back = Path().apply {
            moveTo(0f, size.height * .78f)
            lineTo(size.width * .34f, size.height * .26f)
            lineTo(size.width * .56f, size.height * .58f)
            lineTo(size.width * .72f, size.height * .31f)
            lineTo(size.width, size.height * .72f)
            lineTo(size.width, size.height)
            lineTo(0f, size.height)
            close()
        }
        drawPath(back, Color(0xFF79916F))
        val trail = Path().apply {
            moveTo(size.width * .05f, size.height)
            cubicTo(size.width * .35f, size.height * .73f, size.width * .56f, size.height * .98f, size.width, size.height * .64f)
        }
        drawPath(trail, Trail, style = Stroke(width = size.width * .035f))
        drawCircle(Color(0x99F4F0E5), radius = size.minDimension * .04f, center = Offset(size.width * .78f, size.height * .18f))
    }
}

private fun hikeMeta(hike: Hike): String {
    val parts = mutableListOf<String>()
    if (hike.locationName.isNotBlank()) parts += hike.locationName
    hike.distanceMiles?.let { parts += String.format(Locale.US, "%.1f mi", it) }
    if (hike.photoCount > 0) parts += "${hike.photoCount} photos"
    return parts.joinToString(" · ").ifBlank { "Field journal" }
}

private fun formatDate(raw: String): String = try {
    LocalDate.parse(raw).format(DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US))
} catch (_: Exception) {
    raw
}

private fun formatTakenAt(raw: String?): String {
    if (raw.isNullOrBlank()) return "Field photograph"
    return raw.take(10).let(::formatDate)
}

private fun isValidDate(raw: String): Boolean = try {
    LocalDate.parse(raw)
    true
} catch (_: DateTimeParseException) {
    false
}
