@file:OptIn(
    androidx.compose.animation.ExperimentalAnimationApi::class,
    androidx.compose.foundation.ExperimentalFoundationApi::class,
    androidx.compose.material3.ExperimentalMaterial3Api::class,
)

package com.hikejournal.app.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import androidx.compose.runtime.DisposableEffect
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts.OpenMultipleDocuments
import androidx.activity.result.contract.ActivityResultContracts.RequestPermission
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
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
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
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.CloudOff
import androidx.compose.material.icons.rounded.CloudQueue
import androidx.compose.material.icons.rounded.CloudSync
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.Edit
import androidx.compose.material.icons.rounded.Fullscreen
import androidx.compose.material.icons.rounded.Image
import androidx.compose.material.icons.rounded.LocationOn
import androidx.compose.material.icons.rounded.Map
import androidx.compose.material.icons.rounded.PhotoAlbum
import androidx.compose.material.icons.rounded.PlayCircle
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Unarchive
import androidx.compose.material.icons.rounded.WorkspacePremium
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
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
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
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import coil.ImageLoader
import coil.decode.VideoFrameDecoder
import coil.request.ImageRequest
import coil.request.videoFrameMillis
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.hikejournal.app.AppState
import com.hikejournal.app.AppViewModel
import com.hikejournal.app.BuildConfig
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.HikeDraft
import com.hikejournal.app.data.MediaLocationSummary
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

private data class HikeMapRequest(
    val hike: Hike?,
    val focusedPhoto: Photo? = null,
    val returnToPhoto: Boolean = false,
)

private enum class PhotoSelectionSource {
    GooglePhotos,
    OriginalFiles,
}

@Composable
fun HikeJournalApp(viewModel: AppViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var destination by remember { mutableStateOf(TopDestination.Archive) }
    var editingHike by remember { mutableStateOf<Hike?>(null) }
    var creatingHike by remember { mutableStateOf(false) }
    var settingsOpen by remember { mutableStateOf(false) }
    var badgesOpen by remember { mutableStateOf(false) }
    var selectedPhoto by remember { mutableStateOf<Photo?>(null) }
    var photoSourceOpen by remember { mutableStateOf(false) }
    var pendingUpload by remember { mutableStateOf<List<Uri>>(emptyList()) }
    var pendingUploadSource by remember { mutableStateOf(PhotoSelectionSource.GooglePhotos) }
    var mediaLocationSummary by remember { mutableStateOf<MediaLocationSummary?>(null) }
    var checkingMediaLocations by remember { mutableStateOf(false) }
    var pendingPickerRequest by remember { mutableStateOf<PickVisualMediaRequest?>(null) }
    var pendingOriginalFileRequest by remember { mutableStateOf(false) }
    var syncAttentionOpen by remember { mutableStateOf(false) }
    var speciesEntryAreaName by remember { mutableStateOf<String?>(null) }
    var hikeMapRequest by remember { mutableStateOf<HikeMapRequest?>(null) }

    fun closeHikeMap() {
        val request = hikeMapRequest
        hikeMapRequest = null
        if (request?.returnToPhoto == true) {
            selectedPhoto = request.focusedPhoto
        }
    }

    LaunchedEffect(state.inatAuthorizationUrl) {
        state.inatAuthorizationUrl?.let { url ->
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            viewModel.consumeInatAuthorizationUrl()
        }
    }

    val photoPicker = rememberLauncherForActivityResult(OriginalMetadataMultipleMediaPicker()) { uris ->
        pendingUploadSource = PhotoSelectionSource.GooglePhotos
        pendingUpload = uris
    }
    val originalFilePicker = rememberLauncherForActivityResult(OpenMultipleDocuments()) { uris ->
        pendingUploadSource = PhotoSelectionSource.OriginalFiles
        pendingUpload = uris
    }
    val mediaLocationPermission = rememberLauncherForActivityResult(RequestPermission()) {
        pendingPickerRequest?.let(photoPicker::launch)
        if (pendingOriginalFileRequest) {
            originalFilePicker.launch(arrayOf("image/*", "video/*"))
        }
        pendingPickerRequest = null
        pendingOriginalFileRequest = false
    }
    val launchPhotoPicker: (PickVisualMediaRequest) -> Unit = { request ->
        val needsPermission = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_MEDIA_LOCATION) !=
            PackageManager.PERMISSION_GRANTED
        if (needsPermission) {
            pendingPickerRequest = request
            mediaLocationPermission.launch(Manifest.permission.ACCESS_MEDIA_LOCATION)
        } else {
            photoPicker.launch(request)
        }
    }
    val launchOriginalFilePicker: () -> Unit = {
        val needsPermission = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_MEDIA_LOCATION) !=
            PackageManager.PERMISSION_GRANTED
        if (needsPermission) {
            pendingOriginalFileRequest = true
            mediaLocationPermission.launch(Manifest.permission.ACCESS_MEDIA_LOCATION)
        } else {
            originalFilePicker.launch(arrayOf("image/*", "video/*"))
        }
    }

    LaunchedEffect(pendingUpload) {
        if (pendingUpload.isEmpty()) {
            mediaLocationSummary = null
            checkingMediaLocations = false
        } else {
            mediaLocationSummary = null
            checkingMediaLocations = true
            mediaLocationSummary = runCatching {
                viewModel.inspectMediaLocations(pendingUpload)
            }.getOrElse {
                MediaLocationSummary(pendingUpload.size, 0)
            }
            checkingMediaLocations = false
        }
    }

    BackHandler(
        enabled = hikeMapRequest != null || selectedPhoto != null || syncAttentionOpen || settingsOpen || photoSourceOpen ||
            pendingUpload.isNotEmpty() ||
            creatingHike || editingHike != null || badgesOpen || state.journal != null ||
            state.speciesDetail != null || state.questMapQuest != null,
    ) {
        when {
            hikeMapRequest != null -> closeHikeMap()
            selectedPhoto != null -> selectedPhoto = null
            syncAttentionOpen -> syncAttentionOpen = false
            settingsOpen -> settingsOpen = false
            photoSourceOpen -> photoSourceOpen = false
            pendingUpload.isNotEmpty() -> pendingUpload = emptyList()
            creatingHike || editingHike != null -> {
                creatingHike = false
                editingHike = null
            }
            badgesOpen -> badgesOpen = false
            state.journal != null -> viewModel.closeJournal()
            state.speciesDetail != null -> viewModel.closeSpecies()
            state.questMapQuest != null -> viewModel.closeQuestSightingsMap()
        }
    }

    LaunchedEffect(destination) {
        when (destination) {
            TopDestination.Archive -> Unit
            TopDestination.Species -> {
                viewModel.loadSpecies()
                viewModel.loadSpeciesDiscovery()
            }
            TopDestination.Review -> viewModel.loadReviewQueue()
            TopDestination.Publish -> viewModel.loadPublishQueue()
            TopDestination.Map -> viewModel.loadSightings()
        }
    }

    val screenKey = when {
        hikeMapRequest != null -> "hike-map:${hikeMapRequest?.hike?.id}:${hikeMapRequest?.focusedPhoto?.id}"
        state.journal != null -> "journal:${state.journal?.id}"
        state.speciesDetail != null -> "species:${state.speciesDetail?.key}"
        badgesOpen -> "badges"
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
                key.startsWith("hike-map:") && hikeMapRequest != null -> {
                    val request = hikeMapRequest!!
                    HikeMapScreen(
                        hike = request.hike,
                        focusedPhoto = request.focusedPhoto,
                        onBack = ::closeHikeMap,
                        onOpenPhoto = { photo ->
                            hikeMapRequest = null
                            selectedPhoto = photo
                        },
                    )
                }
                key.startsWith("journal:") && state.journal != null -> {
                    val journal = state.journal!!
                    JournalScreen(
                        hike = journal,
                        state = state,
                        onBack = viewModel::closeJournal,
                        onEdit = { editingHike = journal },
                        onArchive = { viewModel.setArchived(journal) },
                        onExploreSpecies = {
                            speciesEntryAreaName = journal.locationName
                            viewModel.closeJournal()
                            destination = TopDestination.Species
                        },
                        onAddPhotos = { photoSourceOpen = true },
                        onViewMap = {
                            hikeMapRequest = HikeMapRequest(hike = journal)
                        },
                        onPhoto = { selectedPhoto = it },
                    )
                }
                key.startsWith("species:") && state.speciesDetail != null -> {
                    SpeciesDetailScreen(
                        species = state.speciesDetail!!,
                        allSpecies = state.species,
                        loading = state.isSpeciesLoading,
                        onBack = viewModel::closeSpecies,
                        onOpenSpecies = viewModel::openSpecies,
                        onOpenPhoto = { selectedPhoto = it },
                    )
                }
                key == "badges" -> BadgesScreen(
                    state = state,
                    loading = state.isBadgeLoading,
                    onBack = { badgesOpen = false },
                    onRefresh = { viewModel.loadBadgeProgress(force = true) },
                )
                destination == TopDestination.Species -> SpeciesIndexScreen(
                    species = state.species,
                    hikes = state.hikes,
                    discoveryAreas = state.discoveryAreas,
                    nearbySpecies = state.nearbySpecies,
                    quests = state.speciesQuests,
                    questMapQuest = state.questMapQuest,
                    questMapTaxon = state.questMapTaxon,
                    questSightingsMap = state.questSightingsMap,
                    initialNearbyAreaName = speciesEntryAreaName,
                    loading = state.isSpeciesLoading,
                    discoveryLoading = state.isDiscoveryLoading,
                    savingQuest = state.isSavingQuest,
                    offline = state.isOffline,
                    discoveryNotice = state.discoveryNotice,
                    questMapLoading = state.isQuestMapLoading,
                    questMapNotice = state.questMapNotice,
                    onRefresh = { viewModel.loadSpecies(force = true) },
                    onRefreshDiscovery = { viewModel.loadSpeciesDiscovery(force = true) },
                    onLoadNearby = viewModel::loadNearbySpecies,
                    onSaveQuest = viewModel::saveNearbyQuest,
                    onSaveQuestFocus = viewModel::saveQuestFocus,
                    onArchiveQuest = viewModel::archiveQuest,
                    onDeleteQuest = viewModel::deleteQuest,
                    onOpenNearbyMap = viewModel::openNearbySightingsMap,
                    onOpenQuestMap = viewModel::openQuestSightingsMap,
                    onRefreshQuestMap = viewModel::refreshQuestSightingsMap,
                    onCloseQuestMap = viewModel::closeQuestSightingsMap,
                    onInitialAreaConsumed = { speciesEntryAreaName = null },
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
                    onBadges = {
                        badgesOpen = true
                        viewModel.loadBadgeProgress()
                    },
                    onSync = viewModel::syncNow,
                    onRetrySync = viewModel::retrySyncAttention,
                    onShowSyncAttention = { syncAttentionOpen = true },
                )
            }
        }

        if (
            state.journal == null &&
            state.speciesDetail == null &&
            state.questMapQuest == null &&
            hikeMapRequest == null &&
            !badgesOpen
        ) {
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
            source = pendingUploadSource,
            locationSummary = mediaLocationSummary,
            checkingLocations = checkingMediaLocations,
            onDismiss = { pendingUpload = emptyList() },
            onChooseOriginalFiles = {
                pendingUpload = emptyList()
                launchOriginalFilePicker()
            },
            onUpload = { caption, queue ->
                viewModel.uploadPhotos(state.journal!!.id, pendingUpload, caption, queue)
                pendingUpload = emptyList()
            },
        )
    }

    if (photoSourceOpen && state.journal != null) {
        PhotoSourceSheet(
            onDismiss = { photoSourceOpen = false },
            onAlbums = {
                photoSourceOpen = false
                launchPhotoPicker(
                    hikeMediaPickerRequest(PickVisualMedia.DefaultTab.AlbumsTab),
                )
            },
            onRecent = {
                photoSourceOpen = false
                launchPhotoPicker(
                    hikeMediaPickerRequest(PickVisualMedia.DefaultTab.PhotosTab),
                )
            },
            onOriginalFiles = {
                photoSourceOpen = false
                launchOriginalFilePicker()
            },
            onManageCloudMedia = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                {
                    photoSourceOpen = false
                    runCatching {
                        context.startActivity(Intent(MediaStore.ACTION_PICK_IMAGES_SETTINGS))
                    }
                }
            } else {
                null
            },
        )
    }

    selectedPhoto?.let { selected ->
        val photo = state.journal?.photos?.firstOrNull { it.id == selected.id } ?: selected
        val photos = state.journal?.photos.orEmpty()
        val photoIndex = photos.indexOfFirst { it.id == photo.id }
        PhotoViewer(
            photo = photo,
            position = photoIndex.takeIf { it >= 0 }?.plus(1) ?: 1,
            total = photos.size.coerceAtLeast(1),
            queuingReview = state.queuingReviewId == photo.id,
            onDismiss = { selectedPhoto = null },
            onPrevious = photoIndex.takeIf { it > 0 }?.let { index -> { selectedPhoto = photos[index - 1] } },
            onNext = photoIndex.takeIf { it >= 0 && it < photos.lastIndex }?.let { index -> { selectedPhoto = photos[index + 1] } },
            onSaveCaption = { caption ->
                viewModel.updateCaption(photo.id, caption)
                selectedPhoto = null
            },
            onDelete = {
                viewModel.deletePhoto(photo.id)
                selectedPhoto = null
            },
            onQueueReview = { viewModel.queueSpeciesReview(photo) },
            onViewMap = if (photo.latitude != null && photo.longitude != null) {
                {
                    val mapHike = state.journal?.takeIf { it.id == photo.hikeId }
                        ?: state.hikes.firstOrNull { it.id == photo.hikeId }
                    hikeMapRequest = HikeMapRequest(
                        hike = mapHike,
                        focusedPhoto = photo,
                        returnToPhoto = true,
                    )
                    selectedPhoto = null
                }
            } else {
                null
            },
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
    onBadges: () -> Unit,
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
                    onBadges = onBadges,
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
                item {
                    FeaturedHike(
                        hike = featured,
                        opening = state.openingHikeId == featured.id,
                        onOpen = onOpenHike,
                    )
                }
                items(remaining, key = { it.id }) { hike ->
                    HikeRow(
                        hike = hike,
                        opening = state.openingHikeId == hike.id,
                        onOpen = onOpenHike,
                    )
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
    onBadges: () -> Unit,
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
        Row(
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onBadges)
                .padding(top = 16.dp, bottom = 1.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                Icons.Rounded.WorkspacePremium,
                contentDescription = null,
                tint = Trail,
                modifier = Modifier.size(25.dp),
            )
            Column(Modifier.weight(1f).padding(start = 11.dp)) {
                Text("TRAIL MEDALS", style = MaterialTheme.typography.labelSmall, color = Trail)
                Text(
                    "Milestones from every outing and field find",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color(0xFFD7DFD2),
                )
            }
            Icon(Icons.Rounded.ChevronRight, "View trail medals", tint = Color(0xFFB8C9B6))
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
    "update_species_quest" -> "Save Field Quest focus"
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
private fun FeaturedHike(hike: Hike, opening: Boolean, onOpen: (String) -> Unit) {
    Box(
        Modifier
            .fillMaxWidth()
            .height(390.dp)
            .clickable(enabled = !opening) { onOpen(hike.id) }
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
            AnimatedContent(targetState = opening, label = "featured-hike-opening") { isOpening ->
                if (isOpening) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(17.dp),
                            color = Trail,
                            strokeWidth = 2.dp,
                        )
                        Text(
                            "Opening journal…",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color(0xFFE4E9DF),
                            modifier = Modifier.padding(start = 8.dp),
                        )
                    }
                } else {
                    Text(
                        hikeMeta(hike),
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color(0xFFE4E9DF),
                    )
                }
            }
        }
    }
}

@Composable
private fun HikeRow(hike: Hike, opening: Boolean, onOpen: (String) -> Unit) {
    Column(Modifier.clickable(enabled = !opening) { onOpen(hike.id) }) {
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
            AnimatedContent(targetState = opening, label = "hike-row-opening") { isOpening ->
                if (isOpening) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(22.dp),
                        color = Trail,
                        strokeWidth = 2.dp,
                    )
                } else {
                    Text(
                        hike.photoCount.toString().padStart(2, '0'),
                        style = MaterialTheme.typography.headlineSmall,
                        color = Fern,
                    )
                }
            }
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
    onExploreSpecies: () -> Unit,
    onAddPhotos: () -> Unit,
    onViewMap: () -> Unit,
    onPhoto: (Photo) -> Unit,
) {
    val opening = state.openingHikeId == hike.id
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
                AnimatedVisibility(visible = opening) {
                    Row(
                        Modifier.fillMaxWidth().padding(top = 20.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(22.dp),
                            color = Trail,
                            strokeWidth = 2.dp,
                        )
                        Column(Modifier.padding(start = 12.dp)) {
                            Text(
                                "Opening journal",
                                style = MaterialTheme.typography.titleMedium,
                                color = Ink,
                            )
                            Text(
                                "Loading ${hike.photoCount} photo${if (hike.photoCount == 1) "" else "s"}…",
                                style = MaterialTheme.typography.bodyMedium,
                                color = InkMuted,
                            )
                        }
                    }
                }
                Row(Modifier.fillMaxWidth().padding(top = 24.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(
                        onClick = onAddPhotos,
                        enabled = !opening,
                        colors = ButtonDefaults.buttonColors(containerColor = Moss),
                    ) {
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
                OutlinedButton(
                    onClick = onViewMap,
                    enabled = !opening,
                    modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(48.dp),
                ) {
                    Icon(Icons.Rounded.Map, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(7.dp))
                    Text("View map")
                }
                TextButton(onClick = onExploreSpecies, modifier = Modifier.padding(top = 6.dp)) {
                    Icon(Icons.AutoMirrored.Rounded.FactCheck, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(7.dp))
                    Text("Explore species near this outing")
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
                Text(
                    "${if (opening) hike.photoCount else hike.photos.size} frames",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                )
            }
        }
        if (opening) {
            item { Spacer(Modifier.height(12.dp)) }
        } else if (hike.photos.isEmpty()) {
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
            if (photo.isVideo) {
                VideoThumbnail(photo)
                Box(Modifier.fillMaxSize().background(Color(0x33000000)))
                Icon(Icons.Rounded.PlayCircle, "Play video", tint = Paper, modifier = Modifier.align(Alignment.Center).size(56.dp))
                Text("VIDEO", style = MaterialTheme.typography.labelSmall, color = Paper, modifier = Modifier.align(Alignment.BottomStart).padding(8.dp))
            } else {
                AsyncImage(
                    model = ImageRequest.Builder(LocalContext.current).data(photo.url).crossfade(true).build(),
                    contentDescription = photo.caption.ifBlank { "Hike photo" },
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            }
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
            speciesName?.takeIf { it.isNotBlank() } ?: photo.caption.ifBlank {
                if (photo.isVideo) "Field Video" else formatTakenAt(photo.takenAt)
            },
            style = MaterialTheme.typography.bodyMedium,
            color = if (speciesName.isNullOrBlank()) InkMuted else Moss,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 7.dp, bottom = 8.dp),
        )
    }
}

@Composable
private fun VideoThumbnail(photo: Photo) {
    val context = LocalContext.current
    val imageLoader = remember(context) {
        ImageLoader.Builder(context)
            .components { add(VideoFrameDecoder.Factory()) }
            .build()
    }
    AsyncImage(
        model = ImageRequest.Builder(context)
            .data(photo.url)
            .videoFrameMillis(750)
            .crossfade(true)
            .build(),
        imageLoader = imageLoader,
        contentDescription = photo.caption.ifBlank { "Field Video" },
        contentScale = ContentScale.Crop,
        modifier = Modifier.fillMaxSize(),
    )
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
private fun PhotoSourceSheet(
    onDismiss: () -> Unit,
    onAlbums: () -> Unit,
    onRecent: () -> Unit,
    onOriginalFiles: () -> Unit,
    onManageCloudMedia: (() -> Unit)?,
) {
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Paper) {
        Column(
            Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = 20.dp)
                .padding(bottom = 28.dp),
        ) {
            Text("ADD TRAIL MEDIA", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text("Choose where to browse", style = MaterialTheme.typography.headlineLarge, color = Ink)
            Text(
                "Open an album in Google Photos, then select the photos and videos to add.",
                style = MaterialTheme.typography.bodyMedium,
                color = InkMuted,
                modifier = Modifier.padding(top = 6.dp, bottom = 20.dp),
            )
            Button(
                onClick = onAlbums,
                modifier = Modifier.fillMaxWidth().height(54.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Moss),
            ) {
                Icon(Icons.Rounded.PhotoAlbum, null)
                Spacer(Modifier.width(8.dp))
                Text("Open Google Photos albums")
            }
            OutlinedButton(
                onClick = onRecent,
                modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(54.dp),
            ) {
                Icon(Icons.Rounded.Image, null)
                Spacer(Modifier.width(8.dp))
                Text("Choose from recent photos")
            }
            OutlinedButton(
                onClick = onOriginalFiles,
                modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(54.dp),
            ) {
                Icon(Icons.Rounded.LocationOn, null)
                Spacer(Modifier.width(8.dp))
                Text("Choose original files · preserve GPS")
            }
            Text(
                "For exact map coordinates, download the originals from Google Photos first, then choose them from Downloads or DCIM.",
                style = MaterialTheme.typography.bodySmall,
                color = InkMuted,
                modifier = Modifier.padding(top = 8.dp),
            )
            onManageCloudMedia?.let { manage ->
                TextButton(
                    onClick = manage,
                    modifier = Modifier.align(Alignment.CenterHorizontally).padding(top = 8.dp),
                ) {
                    Icon(Icons.Rounded.Settings, null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(7.dp))
                    Text("Manage Google Photos access")
                }
            }
            Text(
                "If an album is missing, enable Google Photos as the cloud media provider in Android’s photo picker settings.",
                style = MaterialTheme.typography.bodySmall,
                color = InkMuted,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
    }
}

@Composable
private fun UploadSheet(
    photoCount: Int,
    source: PhotoSelectionSource,
    locationSummary: MediaLocationSummary?,
    checkingLocations: Boolean,
    onDismiss: () -> Unit,
    onChooseOriginalFiles: () -> Unit,
    onUpload: (String, Boolean) -> Unit,
) {
    var caption by remember { mutableStateOf("") }
    var queueForReview by remember { mutableStateOf(false) }
    val missingLocations = locationSummary?.missingCount ?: 0
    val locationsReady = locationSummary?.allGeotagged == true
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Paper) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
            Text("$photoCount FILE${if (photoCount == 1) "" else "S"} SELECTED", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text("Add to this journal", style = MaterialTheme.typography.headlineLarge, color = Ink)
            Text(
                "HikeJournal checks embedded coordinates before saving so map and species tools do not silently lose their location context.",
                style = MaterialTheme.typography.bodyMedium,
                color = InkMuted,
                modifier = Modifier.padding(top = 6.dp),
            )
            Row(
                Modifier.fillMaxWidth().padding(top = 18.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (checkingLocations || locationSummary == null) {
                    CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp, color = Trail)
                    Column(Modifier.padding(start = 12.dp)) {
                        Text("Checking embedded GPS", style = MaterialTheme.typography.titleMedium, color = Ink)
                        Text("Reading $photoCount selected file${if (photoCount == 1) "" else "s"}", style = MaterialTheme.typography.bodySmall, color = InkMuted)
                    }
                } else if (locationsReady) {
                    Icon(Icons.Rounded.LocationOn, null, tint = Moss)
                    Column(Modifier.padding(start = 10.dp)) {
                        Text("GPS ready on every file", style = MaterialTheme.typography.titleMedium, color = Moss)
                        Text("Exact coordinates will be saved with the journal.", style = MaterialTheme.typography.bodySmall, color = InkMuted)
                    }
                } else {
                    Icon(Icons.Rounded.LocationOn, null, tint = TrailText)
                    Column(Modifier.padding(start = 10.dp)) {
                        Text(
                            "GPS missing from $missingLocations file${if (missingLocations == 1) "" else "s"}",
                            style = MaterialTheme.typography.titleMedium,
                            color = TrailText,
                        )
                        Text(
                            if (source == PhotoSelectionSource.GooglePhotos) {
                                "Google Photos did not share the location metadata. Its Info screen can still show a private or estimated place."
                            } else {
                                "These files do not contain readable embedded coordinates."
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = InkMuted,
                        )
                    }
                }
            }
            OutlinedTextField(caption, { caption = it }, Modifier.fillMaxWidth().padding(top = 18.dp), label = { Text("Shared caption · optional") })
            Row(Modifier.fillMaxWidth().padding(vertical = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Queue for species review", style = MaterialTheme.typography.titleMedium)
                    Text("Review in Android or the web workspace", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
                }
                Switch(queueForReview, { queueForReview = it })
            }
            if (locationSummary != null && !locationsReady) {
                Button(
                    onClick = onChooseOriginalFiles,
                    modifier = Modifier.fillMaxWidth().height(54.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Moss),
                ) {
                    Icon(Icons.Rounded.LocationOn, null)
                    Spacer(Modifier.width(8.dp))
                    Text("Choose original files")
                }
                TextButton(
                    onClick = { onUpload(caption, queueForReview) },
                    modifier = Modifier.align(Alignment.CenterHorizontally).padding(top = 4.dp),
                ) {
                    Text("Save without GPS")
                }
            } else {
                Button(
                    onClick = { onUpload(caption, queueForReview) },
                    enabled = locationsReady && !checkingLocations,
                    modifier = Modifier.fillMaxWidth().height(54.dp),
                ) {
                    if (checkingLocations || locationSummary == null) {
                        CircularProgressIndicator(Modifier.size(19.dp), strokeWidth = 2.dp, color = Paper)
                        Spacer(Modifier.width(8.dp))
                        Text("Checking GPS…")
                    } else {
                        Icon(Icons.Rounded.CameraAlt, null)
                        Spacer(Modifier.width(8.dp))
                        Text("Save $photoCount file${if (photoCount == 1) "" else "s"}")
                    }
                }
            }
        }
    }
}

@Composable
private fun PhotoViewer(
    photo: Photo,
    position: Int,
    total: Int,
    queuingReview: Boolean,
    onDismiss: () -> Unit,
    onPrevious: (() -> Unit)?,
    onNext: (() -> Unit)?,
    onSaveCaption: (String) -> Unit,
    onDelete: () -> Unit,
    onQueueReview: () -> Unit,
    onViewMap: (() -> Unit)?,
) {
    var caption by remember(photo.id) { mutableStateOf(photo.caption) }
    var confirmDelete by remember { mutableStateOf(false) }
    var videoFullscreen by remember(photo.id) { mutableStateOf(false) }
    var horizontalDragDistance by remember(photo.id) { mutableFloatStateOf(0f) }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Column(Modifier.fillMaxSize().background(Color(0xFF101511)).statusBarsPadding()) {
            Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onDismiss) { Icon(Icons.Rounded.Close, "Close", tint = Paper) }
                Text("HikeJournal", style = MaterialTheme.typography.headlineSmall, color = Paper, modifier = Modifier.weight(1f))
                Text("$position OF $total", style = MaterialTheme.typography.labelSmall, color = Color(0xFFBFD2B9))
                IconButton(onClick = { confirmDelete = true }) { Icon(Icons.Rounded.DeleteOutline, "Delete", tint = Color(0xFFE8A18F)) }
            }
            Box(
                Modifier.fillMaxWidth().weight(1f).pointerInput(photo.id) {
                    detectHorizontalDragGestures(
                        onHorizontalDrag = { _, dragAmount -> horizontalDragDistance += dragAmount },
                        onDragEnd = {
                            when {
                                horizontalDragDistance > 72f -> onPrevious?.invoke()
                                horizontalDragDistance < -72f -> onNext?.invoke()
                            }
                            horizontalDragDistance = 0f
                        },
                        onDragCancel = { horizontalDragDistance = 0f },
                    )
                },
            ) {
                if (photo.isVideo) {
                    VideoPlayer(photo.url, photo.caption)
                    FilledIconButton(
                        onClick = { videoFullscreen = true },
                        modifier = Modifier.align(Alignment.TopEnd).padding(12.dp),
                        colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(containerColor = Color(0xB018221C)),
                    ) { Icon(Icons.Rounded.Fullscreen, "Open full-screen video", tint = Paper) }
                } else AsyncImage(photo.url, photo.caption, Modifier.fillMaxSize(), contentScale = ContentScale.Fit)
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
                if (onViewMap != null) {
                    OutlinedButton(
                        onClick = onViewMap,
                        modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(48.dp),
                        border = BorderStroke(1.dp, Color(0xFF91AA8C)),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = Paper),
                    ) {
                        Icon(Icons.Rounded.Map, null)
                        Spacer(Modifier.width(8.dp))
                        Text("View on map")
                    }
                }
                if (photo.isVideo) {
                    Text("Field Video", style = MaterialTheme.typography.titleMedium, color = Paper, modifier = Modifier.padding(top = 10.dp))
                    Text("Tap the expand icon for player-only viewing. Videos are not eligible for species review.", style = MaterialTheme.typography.bodyMedium, color = Color(0xFFBFD2B9), modifier = Modifier.padding(top = 4.dp))
                } else {
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
                                    Text(if (photo.syncState == "synced") "Ready in the shared Review workspace." else "Saved on this phone and will sync automatically.", style = MaterialTheme.typography.bodyMedium, color = Color(0xFFBFD2B9))
                                }
                            }
                        } else {
                            Column {
                                OutlinedButton(onClick = onQueueReview, enabled = !queuingReview, modifier = Modifier.fillMaxWidth().height(50.dp), border = BorderStroke(1.dp, Color(0xFF91AA8C)), colors = ButtonDefaults.outlinedButtonColors(contentColor = Paper)) {
                                    if (queuingReview) CircularProgressIndicator(Modifier.size(18.dp), color = Paper, strokeWidth = 2.dp)
                                    else Icon(Icons.AutoMirrored.Rounded.FactCheck, null)
                                    Spacer(Modifier.width(8.dp))
                                    Text(if (queuingReview) "Adding to review…" else "Send to species review")
                                }
                                Text("Shared with Android and Streamlit; syncs automatically.", style = MaterialTheme.typography.bodyMedium, color = Color(0xFFBFD2B9), modifier = Modifier.padding(top = 7.dp))
                            }
                        }
                    }
                }
                HorizontalDivider(color = Color(0xFF405148), modifier = Modifier.padding(vertical = 13.dp))
                OutlinedTextField(
                    caption,
                    { caption = it },
                    Modifier.fillMaxWidth(),
                    label = { Text(if (photo.isVideo) "Video note" else "Photo note") },
                    placeholder = { Text(if (photo.isVideo) "Enter video note…" else "Enter photo note…") },
                    textStyle = MaterialTheme.typography.bodyLarge.copy(color = Paper),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Paper,
                        unfocusedTextColor = Paper,
                        focusedPlaceholderColor = Color(0xFFD3E0CF),
                        unfocusedPlaceholderColor = Color(0xFFD3E0CF),
                    ),
                )
                Button(onClick = { onSaveCaption(caption) }, Modifier.fillMaxWidth().padding(top = 10.dp)) { Text("Save note") }
            }
        }
    }
    if (videoFullscreen) {
        Dialog(onDismissRequest = { videoFullscreen = false }, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
            Box(Modifier.fillMaxSize().background(Color.Black)) {
                VideoPlayer(photo.url, photo.caption)
                FilledIconButton(
                    onClick = { videoFullscreen = false },
                    modifier = Modifier.align(Alignment.TopEnd).statusBarsPadding().padding(12.dp),
                    colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(containerColor = Color(0xB018221C)),
                ) { Icon(Icons.Rounded.Close, "Exit full-screen video", tint = Paper) }
            }
        }
    }
    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text(if (photo.isVideo) "Delete this video?" else "Delete this photo?") },
            text = { Text("This removes the database record and stored media. This cannot be undone.") },
            confirmButton = { TextButton(onClick = onDelete) { Text("Delete", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Keep photo") } },
        )
    }
}

private val Photo.isVideo: Boolean
    get() = contentType.startsWith("video/", ignoreCase = true) ||
        url.substringBefore('?').substringAfterLast('.', "").lowercase() in setOf("mp4", "mov", "m4v", "3gp", "webm")

@Composable
private fun VideoPlayer(url: String, contentDescription: String) {
    val context = LocalContext.current
    val player = remember(url) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(MediaItem.fromUri(url))
            prepare()
        }
    }
    DisposableEffect(player) { onDispose { player.release() } }
    AndroidView(
        factory = { PlayerView(it).apply { this.player = player; useController = true; this.contentDescription = contentDescription.ifBlank { "Hike video" } } },
        modifier = Modifier.fillMaxSize(),
    )
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
