@file:OptIn(
    androidx.compose.animation.ExperimentalAnimationApi::class,
    androidx.compose.foundation.ExperimentalFoundationApi::class,
    androidx.compose.material3.ExperimentalMaterial3Api::class,
)

package com.hikejournal.app.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.DisposableEffect
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts.OpenDocument
import androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions
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
import androidx.compose.foundation.selection.toggleable
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
import androidx.compose.material.icons.rounded.Check
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
import androidx.compose.material.icons.rounded.MoreVert
import androidx.compose.material.icons.rounded.PlayCircle
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Unarchive
import androidx.compose.material.icons.rounded.WorkspacePremium
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
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
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
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
import com.hikejournal.app.data.HikeLocation
import com.hikejournal.app.data.LocalMediaAccess
import com.hikejournal.app.data.MediaLocationSummary
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.data.SyncAttention
import com.hikejournal.app.data.localMediaAccess
import com.hikejournal.app.data.requiredLocalMediaPermissions
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

@Composable
fun HikeJournalApp(viewModel: AppViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var destination by remember { mutableStateOf(TopDestination.Archive) }
    var editingHike by remember { mutableStateOf<Hike?>(null) }
    var creatingHike by remember { mutableStateOf(false) }
    var createEntryOpen by remember { mutableStateOf(false) }
    var pendingEverydayUpload by remember { mutableStateOf(false) }
    var settingsOpen by remember { mutableStateOf(false) }
    var badgesOpen by remember { mutableStateOf(false) }
    var selectedPhoto by remember { mutableStateOf<Photo?>(null) }
    var speciesAssignmentPhoto by remember { mutableStateOf<Photo?>(null) }
    var localMediaPickerOpen by remember { mutableStateOf(false) }
    var localMediaPermissionError by remember { mutableStateOf<String?>(null) }
    var grantedLocalMediaAccess by remember { mutableStateOf<LocalMediaAccess?>(null) }
    var pendingUpload by remember { mutableStateOf<List<Uri>>(emptyList()) }
    var mediaLocationSummary by remember { mutableStateOf<MediaLocationSummary?>(null) }
    var checkingMediaLocations by remember { mutableStateOf(false) }
    var syncAttentionOpen by remember { mutableStateOf(false) }
    var speciesEntryAreaName by remember { mutableStateOf<String?>(null) }
    var hikeMapRequest by remember { mutableStateOf<HikeMapRequest?>(null) }
    var openingPhotoMapId by remember { mutableStateOf<String?>(null) }
    var selectedRouteUri by remember { mutableStateOf<Uri?>(null) }
    var pendingHikeDelete by remember { mutableStateOf<Hike?>(null) }

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
    LaunchedEffect(state.error) {
        if (state.error != null) {
            openingPhotoMapId = null
        }
    }
    LaunchedEffect(selectedPhoto?.id) {
        val photo = selectedPhoto
        if (photo != null && !photo.isVideo && photo.species.none { it.isPrimary }) {
            viewModel.loadSpecies()
        }
    }

    val localMediaPermissions = rememberLauncherForActivityResult(RequestMultiplePermissions()) {
        val access = localMediaAccess(context)
        grantedLocalMediaAccess = access
        when {
            !access.canReadMedia -> {
                localMediaPermissionError =
                    "Allow HikeJournal to read photos and videos so it can browse originals stored on this phone."
            }
            !access.canReadLocations -> {
                localMediaPermissionError =
                    "Media access is on, but location details are still off. Enable them to preserve each photo or video’s GPS coordinates."
            }
            else -> localMediaPickerOpen = true
        }
    }
    val routePicker = rememberLauncherForActivityResult(OpenDocument()) { uri ->
        selectedRouteUri = uri
    }
    val launchLocalMediaPicker: () -> Unit = {
        val access = localMediaAccess(context)
        grantedLocalMediaAccess = access
        if (access.readyForOriginals && access.hasFullLibraryAccess) {
            localMediaPickerOpen = true
        } else {
            localMediaPermissions.launch(requiredLocalMediaPermissions())
        }
    }
    LaunchedEffect(pendingEverydayUpload, state.journal?.id) {
        if (pendingEverydayUpload && state.journal?.isStandalone == true) {
            pendingEverydayUpload = false
            launchLocalMediaPicker()
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
        enabled = hikeMapRequest != null || selectedPhoto != null || syncAttentionOpen || settingsOpen ||
            pendingUpload.isNotEmpty() ||
            pendingHikeDelete != null || createEntryOpen || creatingHike || editingHike != null || badgesOpen || state.journal != null ||
            state.speciesDetail != null || state.questMapQuest != null,
    ) {
        when {
            pendingHikeDelete != null -> {
                if (state.deletingHikeId == null) pendingHikeDelete = null
            }
            createEntryOpen -> createEntryOpen = false
            hikeMapRequest != null -> closeHikeMap()
            selectedPhoto != null -> selectedPhoto = null
            syncAttentionOpen -> syncAttentionOpen = false
            settingsOpen -> settingsOpen = false
            pendingUpload.isNotEmpty() -> pendingUpload = emptyList()
            creatingHike || editingHike != null -> {
                creatingHike = false
                editingHike = null
                selectedRouteUri = null
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
                        onEdit = if (journal.isStandalone) null else ({
                            viewModel.loadHikeLocations()
                            editingHike = journal
                        }),
                        onArchive = if (journal.isStandalone) null else ({ viewModel.setArchived(journal) }),
                        onDelete = if (journal.isStandalone || state.uploadTotal > 0) null else ({ pendingHikeDelete = journal }),
                        onExploreSpecies = if (journal.isStandalone) null else ({
                            speciesEntryAreaName = journal.locationName
                            viewModel.closeJournal()
                            destination = TopDestination.Species
                        }),
                        onAddPhotos = launchLocalMediaPicker,
                        onViewMap = {
                            hikeMapRequest = HikeMapRequest(hike = journal)
                        },
                        onPhoto = { selectedPhoto = it },
                        onQueueReview = viewModel::queuePhotosForSpeciesReview,
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
                    onConnectInat = viewModel::connectInat,
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
                    onCreate = { createEntryOpen = true },
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
        AnimatedVisibility(
            visible = state.notice != null && state.error == null,
            modifier = Modifier.align(Alignment.BottomCenter),
            enter = slideInVertically { it } + fadeIn(),
            exit = fadeOut(),
        ) {
            NoticeBanner(message = state.notice.orEmpty(), onDismiss = viewModel::clearNotice)
        }
    }

    if (creatingHike || editingHike != null) {
        HikeEditorSheet(
            hike = editingHike,
            locations = state.hikeLocations,
            saving = state.isRefreshing,
            routeUri = selectedRouteUri,
            onChooseRoute = { routePicker.launch(arrayOf("application/vnd.garmin.tcx+xml", "application/xml", "text/xml", "text/plain")) },
            onDismiss = {
                creatingHike = false
                editingHike = null
                selectedRouteUri = null
            },
            onSave = { draft ->
                viewModel.saveHike(draft, selectedRouteUri.takeIf { editingHike == null }, editingHike?.id) {
                    creatingHike = false
                    editingHike = null
                    selectedRouteUri = null
                }
            },
        )
    }

    if (createEntryOpen) {
        CreateEntrySheet(
            onDismiss = { createEntryOpen = false },
            onCreateHike = {
                createEntryOpen = false
                viewModel.loadHikeLocations()
                creatingHike = true
            },
            onCreateEverydaySighting = {
                createEntryOpen = false
                pendingEverydayUpload = true
                viewModel.openHike("everyday")
            },
        )
    }

    pendingHikeDelete?.let { hike ->
        DeleteHikeDialog(
            hike = hike,
            deleting = state.deletingHikeId == hike.id,
            connected = state.syncStatus.connected,
            onDismiss = { pendingHikeDelete = null },
            onDelete = {
                viewModel.deleteHike(hike) {
                    pendingHikeDelete = null
                    editingHike = null
                    selectedRouteUri = null
                }
            },
        )
    }

    if (pendingUpload.isNotEmpty() && state.journal != null) {
        UploadSheet(
            photoCount = pendingUpload.size,
            isEverydaySighting = state.journal!!.isStandalone,
            locationSummary = mediaLocationSummary,
            checkingLocations = checkingMediaLocations,
            onDismiss = { pendingUpload = emptyList() },
            onChooseDifferentPhotos = {
                pendingUpload = emptyList()
                launchLocalMediaPicker()
            },
            onUpload = { caption, queueForReview ->
                viewModel.uploadPhotos(
                    state.journal!!.id,
                    pendingUpload,
                    caption,
                    queueForReview,
                )
                pendingUpload = emptyList()
            },
        )
    }

    if (localMediaPickerOpen && state.journal != null) {
        LocalMediaPickerDialog(
            access = grantedLocalMediaAccess ?: localMediaAccess(context),
            onDismiss = { localMediaPickerOpen = false },
            onConfirm = { uris ->
                pendingUpload = uris
                localMediaPickerOpen = false
            },
        )
    }

    localMediaPermissionError?.let { message ->
        AlertDialog(
            onDismissRequest = { localMediaPermissionError = null },
            title = { Text("Phone originals need permission") },
            text = { Text(message) },
            confirmButton = {
                TextButton(
                    onClick = {
                        localMediaPermissionError = null
                        context.startActivity(
                            Intent(
                                android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.parse("package:${context.packageName}"),
                            )
                        )
                    },
                ) {
                    Text("Open app settings")
                }
            },
            dismissButton = {
                TextButton(onClick = { localMediaPermissionError = null }) {
                    Text("Not now")
                }
            },
        )
    }

    if (photoViewerVisible(selectedPhoto, hikeMapRequest != null)) selectedPhoto?.let { selected ->
        val photo = state.journal?.photos?.firstOrNull { it.id == selected.id } ?: selected
        val photos = state.journal?.photos.orEmpty()
        val photoIndex = photos.indexOfFirst { it.id == photo.id }
        PhotoViewer(
            photo = photo,
            position = photoIndex.takeIf { it >= 0 }?.plus(1) ?: 1,
            total = photos.size.coerceAtLeast(1),
            updatingReview = state.reviewUpdateId == photo.id,
            isCoverPhoto = state.journal?.coverPhotoId == photo.id,
            updatingCover = state.coverUpdateId == photo.id,
            assigningSpecies = state.speciesAssignmentId == photo.id,
            openingMap = openingPhotoMapId == photo.id,
            onDismiss = {
                if (openingPhotoMapId == photo.id) {
                    openingPhotoMapId = null
                }
                selectedPhoto = null
            },
            onPrevious = photoIndex.takeIf { it > 0 }?.let { index -> { selectedPhoto = photos[index - 1] } },
            onNext = photoIndex.takeIf { it >= 0 && it < photos.lastIndex }?.let { index -> { selectedPhoto = photos[index + 1] } },
            onSaveCaption = { caption ->
                viewModel.updateCaption(photo, caption)
                selectedPhoto = null
            },
            onDelete = {
                viewModel.deletePhoto(photo)
                selectedPhoto = null
            },
            onSetReview = { queued ->
                selectedPhoto = photo.copy(
                    processingStatus = if (queued) "in_review" else "ready",
                    syncState = if (photo.syncState == "synced") "queued" else photo.syncState,
                )
                viewModel.setSpeciesReview(photo, queued)
            },
            onSetCover = state.journal?.takeUnless { it.isStandalone || photo.isVideo }?.let {
                { selected: Boolean -> viewModel.setHikeCover(photo, selected) }
            },
            onAssignSpecies = if (!photo.isVideo && photo.species.none { it.isPrimary }) {
                { speciesAssignmentPhoto = photo }
            } else {
                null
            },
            onViewMap = if (photo.latitude != null && photo.longitude != null) {
                {
                    val currentJournal = state.journal?.takeIf { it.isStandalone || it.id == photo.hikeId }
                    if (currentJournal != null || photo.hikeId == null) {
                        openingPhotoMapId = null
                        selectedPhoto = null
                        hikeMapRequest = HikeMapRequest(
                            hike = currentJournal,
                            focusedPhoto = photo,
                            returnToPhoto = true,
                        )
                    } else {
                        openingPhotoMapId = photo.id
                        viewModel.loadHikeForMap(photo.hikeId) { loadedHike ->
                            if (openingPhotoMapId != photo.id) {
                                return@loadHikeForMap
                            }
                            openingPhotoMapId = null
                            selectedPhoto = null
                            hikeMapRequest = HikeMapRequest(
                                hike = loadedHike,
                                focusedPhoto = photo,
                                returnToPhoto = true,
                            )
                        }
                    }
                }
            } else {
                null
            },
        )
    }

    speciesAssignmentPhoto?.let { photo ->
        KnownSpeciesAssignmentDialog(
            species = state.species,
            loading = state.isSpeciesLoading,
            assigning = state.speciesAssignmentId == photo.id,
            onDismiss = { speciesAssignmentPhoto = null },
            onRefresh = { viewModel.loadSpecies(force = true) },
            onAssign = { species ->
                viewModel.assignKnownSpecies(photo, species) {
                    speciesAssignmentPhoto = null
                }
            },
        )
    }

    if (settingsOpen) {
        SettingsDialog(
            currentUrl = viewModel.serverUrl,
            currentKey = viewModel.pairingKey,
            inatConnected = state.publishQueue.connected,
            onDismiss = { settingsOpen = false },
            onSave = { url, key ->
                viewModel.updateConnection(url, key)
                settingsOpen = false
            },
            onConnectInat = viewModel::connectInat,
        )
    }

    if (syncAttentionOpen) {
        SyncAttentionSheet(
            items = state.syncStatus.attentionItems,
            onRetry = viewModel::retrySyncAttention,
            onDiscard = viewModel::discardSyncAttention,
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
    val everyday = state.hikes.firstOrNull { it.isStandalone }?.takeIf { hike ->
        query.isBlank() || listOf(hike.title, hike.notes).any { it.contains(query, ignoreCase = true) }
    }
    val visibleHikes = state.hikes.filterNot { it.isStandalone }.filter { hike ->
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
            ) { Icon(Icons.Rounded.Add, contentDescription = "Add hike or everyday sighting") }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = padding.calculateBottomPadding() + 96.dp),
        ) {
            item {
                LibraryHeader(
                    hikeCount = state.hikes.count { !it.isArchived && !it.isStandalone },
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
            everyday?.let { journal ->
                item {
                    EverydayRow(
                        journal = journal,
                        opening = state.openingHikeId == journal.id,
                        onOpen = onOpenHike,
                    )
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
private fun EverydayRow(journal: Hike, opening: Boolean, onOpen: (String) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(enabled = !opening) { onOpen(journal.id) }
            .background(Paper)
            .padding(horizontal = 20.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(74.dp).background(Moss)) {
            if (journal.coverUrl.isNotBlank()) {
                AsyncImage(journal.coverUrl, "Latest everyday sighting", Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
            } else {
                MountainField(Modifier.fillMaxSize())
            }
        }
        Column(Modifier.weight(1f).padding(start = 14.dp)) {
            Text("EVERYDAY SIGHTINGS", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text(
                if (journal.photoCount == 0) "Add a quick observation" else "${journal.photoCount} field record${if (journal.photoCount == 1) "" else "s"}",
                style = MaterialTheme.typography.titleMedium,
                color = Ink,
            )
            Text(
                "Photos and videos outside a hike",
                style = MaterialTheme.typography.bodyMedium,
                color = InkMuted,
            )
        }
        if (opening) {
            CircularProgressIndicator(Modifier.size(22.dp), color = Trail, strokeWidth = 2.dp)
        } else {
            Icon(Icons.Rounded.ChevronRight, "Open everyday sightings", tint = Fern)
        }
    }
    HorizontalDivider(color = Line)
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
    onDiscard: () -> Unit,
    onDismiss: () -> Unit,
) {
    var confirmDiscard by remember(items.size) { mutableStateOf(false) }
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Paper) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).navigationBarsPadding().padding(horizontal = 20.dp).padding(bottom = 28.dp),
        ) {
            Text("SYNC ATTENTION", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text("Changes that could not sync", style = MaterialTheme.typography.headlineLarge, color = Ink)
            Text(
                "These changes remain on this phone. Review the message below, then retry when you’re ready.",
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
                onClick = { confirmDiscard = true },
                modifier = Modifier.fillMaxWidth().padding(top = 9.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
            ) {
                Text("Discard unsynced changes")
            }
            TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth().padding(top = 3.dp)) { Text("Close") }
        }
    }
    if (confirmDiscard) {
        AlertDialog(
            onDismissRequest = { confirmDiscard = false },
            title = { Text("Discard these changes?") },
            text = {
                Text(
                    "${items.size} unsynced change${if (items.size == 1) "" else "s"} will be permanently removed from this phone.",
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        onDiscard()
                        confirmDiscard = false
                        onDismiss()
                    },
                ) {
                    Text("Discard", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmDiscard = false }) { Text("Keep changes") }
            },
        )
    }
}

private fun syncOperationLabel(kind: String): String = when (kind) {
    "create_hike" -> "Create outing"
    "update_hike" -> "Update outing"
    "archive_hike" -> "Archive outing"
    "delete_hike" -> "Delete outing"
    "upload_photo" -> "Upload photo"
    "upload_route" -> "Upload route"
    "set_hike_cover" -> "Set hike cover"
    "update_caption" -> "Save photo note"
    "delete_photo" -> "Delete photo"
    "queue_species_review" -> "Update species review"
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
    onEdit: (() -> Unit)?,
    onArchive: (() -> Unit)?,
    onDelete: (() -> Unit)?,
    onExploreSpecies: (() -> Unit)?,
    onAddPhotos: () -> Unit,
    onViewMap: () -> Unit,
    onPhoto: (Photo) -> Unit,
    onQueueReview: (List<Photo>) -> Unit,
) {
    val opening = state.openingHikeId == hike.id
    var selectingForReview by remember(hike.id) { mutableStateOf(false) }
    var selectedReviewIds by remember(hike.id) { mutableStateOf<Set<String>>(emptySet()) }
    val reviewEligiblePhotos = hike.photos.filter { !it.isVideo && it.processingStatus != "in_review" }
    LaunchedEffect(hike.photos) {
        val availableIds = reviewEligiblePhotos.mapTo(hashSetOf()) { it.id }
        selectedReviewIds = selectedReviewIds.intersect(availableIds)
        if (selectingForReview && availableIds.isEmpty()) selectingForReview = false
    }
    Box(Modifier.fillMaxSize().background(Parchment)) {
        LazyColumn(
            Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(
                bottom = if (selectingForReview) 142.dp else 64.dp,
            ),
        ) {
        item { JournalHero(hike, onBack, onEdit, onArchive, onDelete) }
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
                                "Loading ${hike.photoCount} capture${if (hike.photoCount == 1) "" else "s"}…",
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
                        Text("Upload photos")
                    }
                    if (onEdit != null) {
                        OutlinedButton(onClick = onEdit) {
                            Icon(Icons.Rounded.Edit, null, Modifier.size(18.dp))
                            Spacer(Modifier.width(7.dp))
                            Text("Edit notes")
                        }
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
                if (onExploreSpecies != null) {
                    TextButton(onClick = onExploreSpecies, modifier = Modifier.padding(top = 6.dp)) {
                        Icon(Icons.AutoMirrored.Rounded.FactCheck, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(7.dp))
                        Text("Explore species near this outing")
                    }
                }
                if (state.uploadTotal > 0) {
                    Column(Modifier.fillMaxWidth().padding(top = 18.dp)) {
                        Text(
                            "Saving ${state.uploadCurrent.coerceAtLeast(1)} of ${state.uploadTotal} on this phone",
                            style = MaterialTheme.typography.labelMedium,
                            color = Moss,
                        )
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
                    Text("Field journal", style = MaterialTheme.typography.headlineMedium, color = Ink)
                }
                Text(
                    "${if (opening) hike.photoCount else hike.photos.size} frames",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                )
            }
            if (!opening && reviewEligiblePhotos.isNotEmpty()) {
                TextButton(
                    onClick = {
                        selectingForReview = !selectingForReview
                        selectedReviewIds = emptySet()
                    },
                    modifier = Modifier.padding(horizontal = 8.dp),
                ) {
                    Icon(Icons.AutoMirrored.Rounded.FactCheck, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(7.dp))
                    Text(if (selectingForReview) "Cancel selection" else "Select for species review")
                }
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
                        PhotoTile(
                            photo = photo,
                            modifier = Modifier.weight(1f),
                            selectedForReview = photo.id in selectedReviewIds,
                            selectionEnabled = selectingForReview && photo in reviewEligiblePhotos,
                            onPhoto = { selected ->
                                if (selectingForReview) {
                                    if (selected in reviewEligiblePhotos) {
                                        selectedReviewIds = if (selected.id in selectedReviewIds) {
                                            selectedReviewIds - selected.id
                                        } else {
                                            selectedReviewIds + selected.id
                                        }
                                    }
                                } else {
                                    onPhoto(selected)
                                }
                            },
                        )
                    }
                    if (rowPhotos.size == 1) Spacer(Modifier.weight(1f))
                }
            }
        }
        }
        AnimatedVisibility(
            visible = selectingForReview,
            modifier = Modifier.align(Alignment.BottomCenter),
            enter = slideInVertically { it } + fadeIn(),
            exit = fadeOut(),
        ) {
            Surface(color = Paper, shadowElevation = 12.dp) {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .navigationBarsPadding()
                        .padding(horizontal = 20.dp, vertical = 14.dp),
                ) {
                    Text(
                        "${selectedReviewIds.size} selected for review",
                        style = MaterialTheme.typography.labelMedium,
                        color = if (selectedReviewIds.isEmpty()) InkMuted else Moss,
                    )
                    Button(
                        onClick = {
                            onQueueReview(hike.photos.filter { it.id in selectedReviewIds })
                            selectedReviewIds = emptySet()
                            selectingForReview = false
                        },
                        enabled = selectedReviewIds.isNotEmpty() && state.reviewUpdateId == null,
                        modifier = Modifier.fillMaxWidth().padding(top = 7.dp).height(52.dp),
                    ) {
                        Icon(Icons.AutoMirrored.Rounded.FactCheck, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(8.dp))
                        Text(
                            if (selectedReviewIds.isEmpty()) "Choose photos"
                            else "Add ${selectedReviewIds.size} to species review",
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun JournalHero(
    hike: Hike,
    onBack: () -> Unit,
    onEdit: (() -> Unit)?,
    onArchive: (() -> Unit)?,
    onDelete: (() -> Unit)?,
) {
    var actionsOpen by remember(hike.id) { mutableStateOf(false) }
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
            if (onEdit != null) {
                FilledIconButton(onClick = onEdit, colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(containerColor = Color(0x99172820))) {
                    Icon(Icons.Rounded.Edit, "Edit hike", tint = Paper)
                }
            }
            if (onArchive != null || onDelete != null) {
                Spacer(Modifier.width(6.dp))
                Box {
                    FilledIconButton(
                        onClick = { actionsOpen = true },
                        colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(containerColor = Color(0x99172820)),
                    ) {
                        Icon(Icons.Rounded.MoreVert, "Hike actions", tint = Paper)
                    }
                    DropdownMenu(
                        expanded = actionsOpen,
                        onDismissRequest = { actionsOpen = false },
                        containerColor = Paper,
                    ) {
                        if (onArchive != null) {
                            DropdownMenuItem(
                                text = { Text(if (hike.isArchived) "Restore outing" else "Archive outing") },
                                leadingIcon = {
                                    Icon(if (hike.isArchived) Icons.Rounded.Unarchive else Icons.Rounded.Archive, null)
                                },
                                onClick = {
                                    actionsOpen = false
                                    onArchive()
                                },
                            )
                        }
                        if (onDelete != null) {
                            DropdownMenuItem(
                                text = { Text("Delete hike", color = MaterialTheme.colorScheme.error) },
                                leadingIcon = {
                                    Icon(Icons.Rounded.DeleteOutline, null, tint = MaterialTheme.colorScheme.error)
                                },
                                onClick = {
                                    actionsOpen = false
                                    onDelete()
                                },
                            )
                        }
                    }
                }
            }
        }
        Text("HikeJournal", style = MaterialTheme.typography.headlineSmall, color = Paper, modifier = Modifier.align(Alignment.BottomStart).padding(20.dp))
    }
}

@Composable
private fun DeleteHikeDialog(
    hike: Hike,
    deleting: Boolean,
    connected: Boolean,
    onDismiss: () -> Unit,
    onDelete: () -> Unit,
) {
    var understood by remember(hike.id) { mutableStateOf(false) }
    val mediaLabel = when (hike.photoCount) {
        0 -> "No photos or videos"
        1 -> "1 photo or video"
        else -> "${hike.photoCount} photos and videos"
    }
    val speciesLabel = when (hike.speciesCount) {
        0 -> "No species"
        1 -> "1 species represented"
        else -> "${hike.speciesCount} species represented"
    }
    AlertDialog(
        onDismissRequest = { if (!deleting) onDismiss() },
        title = { Text("Delete this hike?") },
        text = {
            Column {
                Text(
                    "“${hike.title}” will be permanently removed from HikeJournal.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = Ink,
                )
                Text(
                    buildString {
                        append(mediaLabel)
                        append(" · ")
                        append(speciesLabel)
                        if (hike.routeSegments.isNotEmpty()) append(" · Saved route")
                        append(" · Notes and associated data")
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 10.dp),
                )
                Text(
                    "Already-published observations remain on iNaturalist.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 12.dp),
                )
                Text(
                    if (connected) {
                        "HikeJournal will verify the full deletion with the companion service."
                    } else {
                        "Connect HikeJournal to delete this hike and its stored files."
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = if (connected) InkMuted else MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(top = 6.dp),
                )
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(top = 14.dp)
                        .toggleable(
                            value = understood,
                            enabled = !deleting,
                            role = Role.Checkbox,
                            onValueChange = { understood = it },
                        ),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Checkbox(
                        checked = understood,
                        onCheckedChange = null,
                        enabled = !deleting,
                    )
                    Text(
                        "I understand this cannot be undone.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Ink,
                        modifier = Modifier.padding(start = 6.dp),
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDelete, enabled = understood && connected && !deleting) {
                if (deleting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(18.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.error,
                    )
                } else {
                    Text("Delete hike", color = MaterialTheme.colorScheme.error)
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !deleting) { Text("Keep hike") }
        },
    )
}

@Composable
private fun PhotoTile(
    photo: Photo,
    modifier: Modifier,
    selectedForReview: Boolean,
    selectionEnabled: Boolean,
    onPhoto: (Photo) -> Unit,
) {
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
            if (selectionEnabled) {
                Box(
                    Modifier
                        .align(Alignment.TopStart)
                        .padding(8.dp)
                        .size(28.dp)
                        .clip(CircleShape)
                        .background(if (selectedForReview) Trail else Color(0xCCFFFFFF)),
                    contentAlignment = Alignment.Center,
                ) {
                    if (selectedForReview) {
                        Icon(Icons.Rounded.Check, "Selected for review", tint = Paper, modifier = Modifier.size(19.dp))
                    }
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
private fun CreateEntrySheet(
    onDismiss: () -> Unit,
    onCreateHike: () -> Unit,
    onCreateEverydaySighting: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = Paper,
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = 20.dp)
                .padding(bottom = 28.dp),
        ) {
            Text("NEW FIELD NOTE", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text("What did you find?", style = MaterialTheme.typography.headlineLarge, color = Ink)
            Text(
                "Start a full outing, or add a quick sighting that is not attached to a hike.",
                style = MaterialTheme.typography.bodyMedium,
                color = InkMuted,
                modifier = Modifier.padding(top = 6.dp, bottom = 20.dp),
            )
            Button(
                onClick = onCreateHike,
                modifier = Modifier.fillMaxWidth().height(56.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Moss),
            ) {
                Icon(Icons.Rounded.Map, null)
                Spacer(Modifier.width(9.dp))
                Text("Create a hike")
            }
            OutlinedButton(
                onClick = onCreateEverydaySighting,
                modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(56.dp),
            ) {
                Icon(Icons.Rounded.CameraAlt, null)
                Spacer(Modifier.width(9.dp))
                Text("Add everyday sighting")
            }
        }
    }
}

@Composable
private fun HikeEditorSheet(
    hike: Hike?,
    locations: List<HikeLocation>,
    saving: Boolean,
    routeUri: Uri?,
    onChooseRoute: () -> Unit,
    onDismiss: () -> Unit,
    onSave: (HikeDraft) -> Unit,
) {
    var title by remember(hike?.id) { mutableStateOf(hike?.title.orEmpty()) }
    var date by remember(hike?.id) { mutableStateOf(hike?.hikeDate ?: LocalDate.now().toString()) }
    var location by remember(hike?.id) { mutableStateOf(hike?.locationName.orEmpty()) }
    var locationMenuOpen by remember(hike?.id) { mutableStateOf(false) }
    var distance by remember(hike?.id) { mutableStateOf(hike?.distanceMiles?.toString().orEmpty()) }
    var notes by remember(hike?.id) { mutableStateOf(hike?.notes.orEmpty()) }
    var validation by remember { mutableStateOf<String?>(null) }
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val matchingLocations = locations
        .filter { location.isBlank() || it.name.contains(location, ignoreCase = true) }
        .take(6)

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
            ExposedDropdownMenuBox(
                expanded = locationMenuOpen && matchingLocations.isNotEmpty(),
                onExpandedChange = { locationMenuOpen = it },
            ) {
                OutlinedTextField(
                    value = location,
                    onValueChange = {
                        location = it
                        locationMenuOpen = true
                    },
                    modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryEditable),
                    label = { Text("Location") },
                    placeholder = { Text("Search the imported location library") },
                    trailingIcon = {
                        androidx.compose.material3.ExposedDropdownMenuDefaults.TrailingIcon(
                            expanded = locationMenuOpen,
                        )
                    },
                    singleLine = true,
                )
                ExposedDropdownMenu(
                    expanded = locationMenuOpen && matchingLocations.isNotEmpty(),
                    onDismissRequest = { locationMenuOpen = false },
                ) {
                    matchingLocations.forEach { savedLocation ->
                        DropdownMenuItem(
                            text = { Text(savedLocation.name) },
                            leadingIcon = { Icon(Icons.Rounded.LocationOn, null) },
                            onClick = {
                                location = savedLocation.name
                                locationMenuOpen = false
                            },
                        )
                    }
                }
            }
            Text(
                "Choose a saved location to connect this hike to the imported library.",
                style = MaterialTheme.typography.bodySmall,
                color = InkMuted,
                modifier = Modifier.padding(top = 5.dp),
            )
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
            if (hike == null) {
                Spacer(Modifier.height(12.dp))
                OutlinedButton(onClick = onChooseRoute, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Rounded.Map, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(if (routeUri == null) "Add TCX route (optional)" else "TCX route selected")
                }
                Text(
                    if (routeUri == null) "Import a .tcx or MapMyRun .tcx.txt file to draw this hike on the map." else "The route will upload with this hike and appear on its map after sync.",
                    style = MaterialTheme.typography.bodySmall,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
            validation?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 10.dp)) }
            Button(
                onClick = {
                    when {
                        title.isBlank() -> validation = "Give this outing a title."
                        !isValidDate(date) -> validation = "Use a date like 2026-07-12."
                        distance.isNotBlank() && (distance.toDoubleOrNull()?.takeIf { it.isFinite() && it >= 0.0 } == null) ->
                            validation = "Enter a distance like 3.5, or leave it blank."
                        else -> {
                            val selectedLocation = locations.firstOrNull {
                                it.name.equals(location.trim(), ignoreCase = true)
                            }
                            onSave(
                                HikeDraft(
                                    title = title.trim(),
                                    hikeDate = date,
                                    distanceMiles = distance.toDoubleOrNull(),
                                    locationName = location.trim(),
                                    notes = notes.trim(),
                                    locationId = selectedLocation?.id,
                                ),
                            )
                        }
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
private fun UploadSheet(
    photoCount: Int,
    isEverydaySighting: Boolean,
    locationSummary: MediaLocationSummary?,
    checkingLocations: Boolean,
    onDismiss: () -> Unit,
    onChooseDifferentPhotos: () -> Unit,
    onUpload: (String, Boolean) -> Unit,
) {
    var caption by remember { mutableStateOf("") }
    var queueForReview by remember(isEverydaySighting) {
        mutableStateOf(defaultQueueForReview(isEverydaySighting))
    }
    val missingLocations = locationSummary?.missingCount ?: 0
    val locationsReady = locationSummary?.allGeotagged == true
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Paper) {
        Column(
            Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .imePadding()
                .navigationBarsPadding()
                .padding(horizontal = 20.dp)
                .padding(bottom = 28.dp),
        ) {
            Text("$photoCount FILE${if (photoCount == 1) "" else "S"} SELECTED", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text("Add to this journal", style = MaterialTheme.typography.headlineLarge, color = Ink)
            Text(
                "HikeJournal checks for embedded coordinates so each entry can appear accurately on maps and in species tools.",
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
                            "These local originals do not contain readable embedded coordinates. Check that location tagging was enabled in the Camera app.",
                            style = MaterialTheme.typography.bodySmall,
                            color = InkMuted,
                        )
                    }
                }
            }
            OutlinedTextField(caption, { caption = it }, Modifier.fillMaxWidth().padding(top = 18.dp), label = { Text("Note · optional") })
            if (isEverydaySighting) {
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("Send to species review", style = MaterialTheme.typography.titleMedium, color = Ink)
                        Text(
                            "On by default for everyday sightings. Turn this off to save without review.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = InkMuted,
                        )
                    }
                    Switch(
                        checked = queueForReview,
                        onCheckedChange = { queueForReview = it },
                    )
                }
            } else {
                Text(
                    "After upload, use Select for species review in the journal to choose one or more photos.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(vertical = 16.dp),
                )
            }
            if (locationSummary != null && !locationsReady) {
                Button(
                    onClick = onChooseDifferentPhotos,
                    modifier = Modifier.fillMaxWidth().height(54.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Moss),
                ) {
                    Icon(Icons.Rounded.LocationOn, null)
                    Spacer(Modifier.width(8.dp))
                    Text("Choose different photos")
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
    updatingReview: Boolean,
    isCoverPhoto: Boolean,
    updatingCover: Boolean,
    assigningSpecies: Boolean,
    openingMap: Boolean,
    onDismiss: () -> Unit,
    onPrevious: (() -> Unit)?,
    onNext: (() -> Unit)?,
    onSaveCaption: (String) -> Unit,
    onDelete: () -> Unit,
    onSetReview: (Boolean) -> Unit,
    onSetCover: ((Boolean) -> Unit)?,
    onAssignSpecies: (() -> Unit)?,
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
                        enabled = !openingMap,
                        modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(48.dp),
                        border = BorderStroke(1.dp, Color(0xFF91AA8C)),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = Paper),
                    ) {
                        if (openingMap) {
                            CircularProgressIndicator(Modifier.size(18.dp), color = Paper, strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Rounded.Map, null)
                        }
                        Spacer(Modifier.width(8.dp))
                        Text(if (openingMap) "Opening map..." else "View on map")
                    }
                }
                if (photo.isVideo) {
                    Text("Field Video", style = MaterialTheme.typography.titleMedium, color = Paper, modifier = Modifier.padding(top = 10.dp))
                    Text("Tap the expand icon for player-only viewing. Videos are not eligible for species review.", style = MaterialTheme.typography.bodyMedium, color = Color(0xFFBFD2B9), modifier = Modifier.padding(top = 4.dp))
                } else {
                    if (onAssignSpecies != null) {
                        OutlinedButton(
                            onClick = onAssignSpecies,
                            enabled = !assigningSpecies,
                            modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(48.dp),
                            border = BorderStroke(1.dp, Color(0xFF91AA8C)),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Paper),
                        ) {
                            if (assigningSpecies) {
                                CircularProgressIndicator(Modifier.size(18.dp), color = Paper, strokeWidth = 2.dp)
                            } else {
                                Icon(Icons.AutoMirrored.Rounded.FactCheck, null)
                            }
                            Spacer(Modifier.width(8.dp))
                            Text(if (assigningSpecies) "Assigning species..." else "Assign known species")
                        }
                    }
                    PhotoSettingRow(
                        checked = photo.processingStatus == "in_review",
                        updating = updatingReview,
                        title = "Species review",
                        detail = if (photo.processingStatus == "in_review") {
                            if (photo.syncState == "synced") "Included in your identification queue." else "Saved and will update when connected."
                        } else {
                            "Include this photo for identification."
                        },
                        onCheckedChange = onSetReview,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                    if (onSetCover != null) {
                        PhotoSettingRow(
                            checked = isCoverPhoto,
                            updating = updatingCover,
                            title = "Hike cover",
                            detail = if (isCoverPhoto) "Shown in your archive and journal." else "Use this photo as the hike cover.",
                            onCheckedChange = onSetCover,
                            modifier = Modifier.padding(top = 2.dp),
                        )
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
        val mediaName = if (photo.isVideo) "video" else "photo"
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text(if (photo.isVideo) "Delete this video?" else "Delete this photo?") },
            text = { Text("This permanently removes this $mediaName from HikeJournal.") },
            confirmButton = { TextButton(onClick = onDelete) { Text("Delete", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Keep $mediaName") } },
        )
    }
}

@Composable
private fun KnownSpeciesAssignmentDialog(
    species: List<SpeciesRecord>,
    loading: Boolean,
    assigning: Boolean,
    onDismiss: () -> Unit,
    onRefresh: () -> Unit,
    onAssign: (SpeciesRecord) -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var selected by remember { mutableStateOf<SpeciesRecord?>(null) }
    val filtered = filterKnownSpecies(species, query)
    AlertDialog(
        onDismissRequest = { if (!assigning) onDismiss() },
        title = { Text("Assign known species") },
        text = {
            Column {
                Text(
                    "Choose a species already in your Field Guide. This confirms the photo and makes it ready to publish.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                )
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth().padding(top = 14.dp),
                    label = { Text("Common or scientific name") },
                    leadingIcon = { Icon(Icons.Rounded.Search, null) },
                    singleLine = true,
                )
                when {
                    loading && species.isEmpty() -> {
                        Row(
                            Modifier.fillMaxWidth().padding(vertical = 36.dp),
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                            Text("Loading Field Guide…", modifier = Modifier.padding(start = 10.dp))
                        }
                    }
                    filtered.isEmpty() -> {
                        Column(
                            Modifier.fillMaxWidth().padding(vertical = 24.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(
                                if (species.isEmpty()) "No saved species are available yet." else "No species match that search.",
                                color = InkMuted,
                            )
                            if (species.isEmpty()) TextButton(onClick = onRefresh) { Text("Refresh Field Guide") }
                        }
                    }
                    else -> LazyColumn(Modifier.fillMaxWidth().heightIn(max = 360.dp).padding(top = 8.dp)) {
                        items(filtered, key = { it.key }) { item ->
                            Row(
                                Modifier
                                    .fillMaxWidth()
                                    .clickable(enabled = !assigning) { selected = item }
                                    .padding(vertical = 11.dp, horizontal = 4.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column(Modifier.weight(1f)) {
                                    Text(
                                        item.commonName.ifBlank { item.scientificName },
                                        style = MaterialTheme.typography.titleSmall,
                                        color = Ink,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                    Text(
                                        buildString {
                                            if (item.scientificName.isNotBlank() && item.scientificName != item.commonName) {
                                                append(item.scientificName)
                                                append(" · ")
                                            }
                                            append(item.encounterCount)
                                            append(if (item.encounterCount == 1) " prior record" else " prior records")
                                        },
                                        style = MaterialTheme.typography.bodySmall,
                                        color = InkMuted,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                }
                                if (selected?.key == item.key) {
                                    Icon(Icons.Rounded.Check, "Selected", tint = Moss)
                                }
                            }
                            HorizontalDivider(color = Line)
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { selected?.let(onAssign) },
                enabled = selected != null && !assigning,
            ) {
                if (assigning) {
                    CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                }
                Text(if (assigning) "Assigning…" else "Assign species")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !assigning) { Text("Cancel") }
        },
    )
}

internal fun filterKnownSpecies(species: List<SpeciesRecord>, query: String): List<SpeciesRecord> {
    val normalized = query.trim()
    if (normalized.isEmpty()) return species
    return species.filter { item ->
        item.commonName.contains(normalized, ignoreCase = true) ||
            item.scientificName.contains(normalized, ignoreCase = true)
    }
}

internal fun photoViewerVisible(selectedPhoto: Photo?, mapRequestOpen: Boolean): Boolean =
    selectedPhoto != null && !mapRequestOpen

@Composable
private fun PhotoSettingRow(
    checked: Boolean,
    updating: Boolean,
    title: String,
    detail: String,
    onCheckedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier
            .fillMaxWidth()
            .toggleable(
                value = checked,
                enabled = !updating,
                role = Role.Checkbox,
                onValueChange = onCheckedChange,
            )
            .padding(vertical = 7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(checked = checked, onCheckedChange = null, enabled = !updating)
        Column(Modifier.weight(1f).padding(start = 8.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = Paper)
            Text(detail, style = MaterialTheme.typography.bodyMedium, color = Color(0xFFBFD2B9))
        }
        if (updating) {
            CircularProgressIndicator(
                modifier = Modifier.size(18.dp),
                color = Paper,
                strokeWidth = 2.dp,
            )
        }
    }
}

private val Photo.isVideo: Boolean
    get() = contentType.startsWith("video/", ignoreCase = true) ||
        url.substringBefore('?').substringAfterLast('.', "").lowercase() in setOf("mp4", "mov", "m4v", "3gp", "webm")

internal fun defaultQueueForReview(isEverydaySighting: Boolean): Boolean = isEverydaySighting

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
    inatConnected: Boolean,
    onDismiss: () -> Unit,
    onSave: (String, String) -> Unit,
    onConnectInat: () -> Unit,
) {
    var url by remember(currentUrl) { mutableStateOf(currentUrl) }
    var key by remember(currentKey) { mutableStateOf(currentKey) }
    var validation by remember { mutableStateOf<String?>(null) }
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
                validation?.let {
                    Text(
                        it,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
                TextButton(
                    onClick = { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(BuildConfig.DEFAULT_WEB_URL))) },
                    modifier = Modifier.padding(top = 8.dp),
                ) {
                    Icon(Icons.AutoMirrored.Rounded.OpenInNew, null)
                    Spacer(Modifier.width(7.dp))
                    Text("Open HikeJournal on the web")
                }
                HorizontalDivider(Modifier.padding(top = 12.dp))
                Text("iNaturalist", style = MaterialTheme.typography.titleMedium, color = Ink, modifier = Modifier.padding(top = 16.dp))
                Text(
                    if (inatConnected) "Connected for species recommendations and publishing."
                    else "Connect to get species recommendations and publish sightings.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 4.dp),
                )
                if (!inatConnected) {
                    Button(
                        onClick = onConnectInat,
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                    ) {
                        Text("Connect iNaturalist")
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val cleanUrl = url.trim()
                    when {
                        cleanUrl.isBlank() -> validation = "Enter the HikeJournal connection address."
                        !cleanUrl.startsWith("https://", ignoreCase = true) &&
                            !cleanUrl.startsWith("http://", ignoreCase = true) ->
                            validation = "Start the address with https:// or http://."
                        key.isBlank() -> validation = "Enter the pairing key."
                        else -> onSave(cleanUrl, key.trim())
                    }
                },
            ) {
                Text("Reconnect")
            }
        },
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
private fun NoticeBanner(message: String, onDismiss: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().background(Moss).navigationBarsPadding().clickable(onClick = onDismiss).padding(horizontal = 18.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Rounded.Check, null, tint = Paper, modifier = Modifier.size(20.dp))
        Text(
            message,
            color = Paper,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f).padding(start = 10.dp),
        )
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
        Text("Create your first outing, or start with a quick everyday sighting.", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
        Button(onClick = onCreate, modifier = Modifier.padding(top = 18.dp)) { Text("Add an entry") }
    }
}

@Composable
private fun EmptyPhotos(onAdd: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 42.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(Icons.Rounded.Image, null, tint = Fern, modifier = Modifier.size(48.dp))
        Text("The first frame is waiting", style = MaterialTheme.typography.headlineSmall, color = Ink, modifier = Modifier.padding(top = 12.dp))
        TextButton(onClick = onAdd) { Text("Upload photos") }
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
    if (hike.photoCount > 0) parts += "${hike.photoCount} captures"
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
