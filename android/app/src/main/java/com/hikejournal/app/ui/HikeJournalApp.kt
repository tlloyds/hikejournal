@file:OptIn(
    androidx.compose.animation.ExperimentalAnimationApi::class,
    androidx.compose.foundation.ExperimentalFoundationApi::class,
    androidx.compose.material3.ExperimentalMaterial3Api::class,
)

package com.hikejournal.app.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
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
import androidx.compose.foundation.lazy.rememberLazyListState
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
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.CloudOff
import androidx.compose.material.icons.rounded.CloudQueue
import androidx.compose.material.icons.rounded.CloudSync
import androidx.compose.material.icons.rounded.Cloud
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.Edit
import androidx.compose.material.icons.rounded.Fullscreen
import androidx.compose.material.icons.rounded.Image
import androidx.compose.material.icons.rounded.LocationOn
import androidx.compose.material.icons.rounded.KeyboardArrowUp
import androidx.compose.material.icons.rounded.Map
import androidx.compose.material.icons.rounded.MoreVert
import androidx.compose.material.icons.rounded.PlayCircle
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Unarchive
import androidx.compose.material.icons.rounded.WorkspacePremium
import androidx.compose.material.icons.rounded.WaterDrop
import androidx.compose.material.icons.rounded.WbSunny
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
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
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
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.core.app.NotificationManagerCompat
import androidx.core.location.LocationManagerCompat
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
import com.hikejournal.app.data.ReviewCandidate
import com.hikejournal.app.data.ReviewItem
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.data.SpeciesLabel
import com.hikejournal.app.data.SyncAttention
import com.hikejournal.app.data.WeatherSnapshot
import com.hikejournal.app.data.localMediaAccess
import com.hikejournal.app.data.requiredLocalMediaPermissions
import com.hikejournal.app.tracking.TrackingStatus
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
import java.net.URI
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale
import kotlin.math.roundToInt
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private data class HikeMapRequest(
    val hike: Hike?,
    val focusedPhoto: Photo? = null,
    val returnToPhoto: Boolean = false,
)

private data class SpeciesBrowseContext(
    val species: List<SpeciesRecord>,
    val label: String,
)

private enum class TrackingPreflightIssue {
    PreciseLocation,
    Notifications,
    LocationDisabled,
}

@Composable
fun HikeJournalApp(viewModel: AppViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var destination by rememberSaveable { mutableStateOf(TopDestination.Archive) }
    var editingHike by remember { mutableStateOf<Hike?>(null) }
    var creatingHike by remember { mutableStateOf(false) }
    var createEntryOpen by remember { mutableStateOf(false) }
    var pendingEverydayUpload by remember { mutableStateOf(false) }
    var settingsOpen by remember { mutableStateOf(false) }
    var badgesOpen by remember { mutableStateOf(false) }
    var comparisonBaseHike by remember { mutableStateOf<Hike?>(null) }
    var selectedPhoto by remember { mutableStateOf<Photo?>(null) }
    var directReviewItem by remember { mutableStateOf<ReviewItem?>(null) }
    var identifyAfterUpload by remember { mutableStateOf(false) }
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
    var openingMapPhotoId by remember { mutableStateOf<String?>(null) }
    var selectedRouteUri by remember { mutableStateOf<Uri?>(null) }
    var pendingHikeDelete by remember { mutableStateOf<Hike?>(null) }
    var speciesBrowseContext by remember { mutableStateOf<SpeciesBrowseContext?>(null) }
    var speciesCollectionPreferences by remember { mutableStateOf(SpeciesCollectionPreferences()) }
    var trackingVisible by rememberSaveable { mutableStateOf(false) }
    var trackingEndConfirmationRequested by rememberSaveable { mutableStateOf(false) }
    var pendingTrackingStart by rememberSaveable { mutableStateOf(false) }
    var trackingIssue by remember { mutableStateOf<TrackingPreflightIssue?>(null) }

    val activeTracking = state.tracking?.takeUnless { it.status == TrackingStatus.FINISHED }
    val trackingUi = activeTracking?.toTrackingUiModel()

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
            openingMapPhotoId = null
        }
    }
    LaunchedEffect(selectedPhoto?.id) {
        val photo = selectedPhoto
        if (photo != null && !photo.isVideo && photo.species.none { it.isPrimary }) {
            viewModel.loadSpecies()
        }
    }
    LaunchedEffect(state.notice) {
        if (state.notice != null) {
            delay(if (state.notice.orEmpty().length > 180) 8_000 else 4_000)
            viewModel.clearNotice()
        }
    }
    LaunchedEffect(state.trackingOpenRequestToken, activeTracking?.sessionId) {
        val token = state.trackingOpenRequestToken
        if (token > 0L && activeTracking != null) {
            trackingVisible = true
            viewModel.consumeTrackingOpenRequest(token)
        }
    }
    LaunchedEffect(state.trackingEndRequestToken, activeTracking?.sessionId) {
        val token = state.trackingEndRequestToken
        if (token > 0L && activeTracking != null) {
            trackingVisible = true
            if (activeTracking.status == TrackingStatus.PAUSED) {
                trackingEndConfirmationRequested = true
            }
            viewModel.consumeTrackingEndRequest(token)
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
    val trackingPermissions = rememberLauncherForActivityResult(RequestMultiplePermissions()) {
        if (!pendingTrackingStart) return@rememberLauncherForActivityResult
        pendingTrackingStart = false
        val issue = trackingPreflightIssue(context)
        if (issue == null) {
            trackingVisible = true
            viewModel.startTracking()
        } else {
            trackingIssue = issue
        }
    }
    val beginTracking: () -> Unit = {
        val missingPermissions = missingTrackingPermissions(context)
        if (missingPermissions.isNotEmpty()) {
            pendingTrackingStart = true
            trackingPermissions.launch(missingPermissions)
        } else {
            val issue = trackingPreflightIssue(context)
            if (issue == null) {
                trackingVisible = true
                viewModel.startTracking()
            } else {
                trackingIssue = issue
            }
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
        enabled = (trackingVisible && activeTracking != null) || hikeMapRequest != null || selectedPhoto != null || syncAttentionOpen || settingsOpen ||
            pendingUpload.isNotEmpty() ||
            pendingHikeDelete != null || createEntryOpen || creatingHike || editingHike != null || badgesOpen || state.journal != null ||
            state.speciesDetail != null || state.questMapQuest != null,
    ) {
        when {
            trackingVisible && activeTracking != null -> {
                trackingVisible = false
                trackingEndConfirmationRequested = false
            }
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
            state.questMapQuest != null -> viewModel.closeQuestSightingsMap()
            state.hikeComparison != null -> viewModel.closeHikeComparison()
            state.fieldBriefing != null -> viewModel.closeFieldBriefing()
            state.placeProfile != null -> viewModel.closePlaceProfile()
            state.journal != null -> viewModel.closeJournal()
            state.speciesDetail != null -> {
                speciesBrowseContext = null
                viewModel.closeSpecies()
            }
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
        trackingVisible && trackingUi != null -> "tracking:${trackingUi.sessionId}"
        hikeMapRequest != null -> "hike-map:${hikeMapRequest?.hike?.id}:${hikeMapRequest?.focusedPhoto?.id}"
        state.questMapQuest != null && state.questMapTaxon != null -> "quest-map:${state.questMapTaxon?.taxonId}"
        state.hikeComparison != null || state.isLongitudinalLoading && comparisonBaseHike != null -> "comparison"
        state.fieldBriefing != null -> "briefing:${state.fieldBriefing?.targetDate}"
        state.placeProfile != null -> "place:${state.placeProfile?.locationId}"
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
                key.startsWith("tracking:") && trackingUi != null -> {
                    HikeTrackingScreen(
                        tracking = trackingUi,
                        fieldMarks = state.trackingMarks,
                        onBack = {
                            trackingVisible = false
                            trackingEndConfirmationRequested = false
                        },
                        onPause = viewModel::pauseTracking,
                        onResume = {
                            val issue = trackingPreflightIssue(context)
                            if (issue == null) viewModel.resumeTracking() else trackingIssue = issue
                        },
                        onEnd = {
                            viewModel.finishTracking { finishedHike ->
                                trackingVisible = false
                                trackingEndConfirmationRequested = false
                                viewModel.loadHikeLocations()
                                editingHike = finishedHike
                            }
                        },
                        onDiscard = {
                            viewModel.discardTracking {
                                trackingVisible = false
                                trackingEndConfirmationRequested = false
                            }
                        },
                        onAddFieldMark = viewModel::addFieldMark,
                        requestEndConfirmation = trackingEndConfirmationRequested,
                        onEndConfirmationShown = { trackingEndConfirmationRequested = false },
                    )
                }
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
                key.startsWith("quest-map:") && state.questMapQuest != null && state.questMapTaxon != null -> {
                    QuestSightingsMapScreen(
                        quest = state.questMapQuest!!,
                        taxon = state.questMapTaxon!!,
                        mapData = state.questSightingsMap,
                        loading = state.isQuestMapLoading,
                        notice = state.questMapNotice,
                        onBack = viewModel::closeQuestSightingsMap,
                        onRefresh = viewModel::refreshQuestSightingsMap,
                    )
                }
                key == "comparison" -> HikeComparisonScreen(
                    comparison = state.hikeComparison,
                    loading = state.isLongitudinalLoading,
                    onBack = {
                        comparisonBaseHike = null
                        viewModel.closeHikeComparison()
                    },
                )
                key.startsWith("briefing:") -> FieldBriefingScreen(
                    briefing = state.fieldBriefing,
                    loading = state.isLongitudinalLoading,
                    onBack = viewModel::closeFieldBriefing,
                    onOpenSpecies = { key ->
                        viewModel.closeFieldBriefing()
                        viewModel.openSpecies(key)
                    },
                    onOpenSightings = viewModel::openBriefingSightingsMap,
                )
                key.startsWith("place:") -> PlaceProfileScreen(
                    profile = state.placeProfile,
                    loading = state.isLongitudinalLoading,
                    onBack = viewModel::closePlaceProfile,
                    onOpenHike = { hikeId ->
                        viewModel.closePlaceProfile()
                        viewModel.openHike(hikeId)
                    },
                )
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
                        onOpenPlace = journal.primaryLocationId?.let { locationId ->
                            { viewModel.openPlaceProfile(locationId) }
                        },
                        onOpenBriefing = journal.primaryLocationId?.let { locationId ->
                            { viewModel.openFieldBriefing(locationId) }
                        },
                        onCompare = if (journal.isStandalone) null else ({ comparisonBaseHike = journal }),
                        onRefreshWeather = if (journal.isStandalone) null else ({
                            viewModel.enrichHikeWeather(journal.id, force = journal.weather != null)
                        }),
                        onPhoto = { selectedPhoto = it },
                        onQueueReview = viewModel::queuePhotosForSpeciesReview,
                    )
                }
                key.startsWith("species:") && state.speciesDetail != null -> {
                    SpeciesDetailScreen(
                        species = state.speciesDetail!!,
                        allSpecies = speciesBrowseContext?.species ?: state.species,
                        browseContext = speciesBrowseContext?.label,
                        loading = state.isSpeciesLoading,
                        onBack = {
                            speciesBrowseContext = null
                            viewModel.closeSpecies()
                        },
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
                    onSaveQuest = { title, hikeId, focusIds, onSaved ->
                        viewModel.saveNearbyQuest(title, hikeId, focusIds, onSaved)
                    },
                    onSaveQuestFocus = viewModel::saveQuestFocus,
                    onRenameQuest = viewModel::renameQuest,
                    onArchiveQuest = viewModel::archiveQuest,
                    onDeleteQuest = viewModel::deleteQuest,
                    onOpenNearbyMap = viewModel::openNearbySightingsMap,
                    onOpenQuestMap = viewModel::openQuestSightingsMap,
                    onRefreshQuestMap = viewModel::refreshQuestSightingsMap,
                    onCloseQuestMap = viewModel::closeQuestSightingsMap,
                    onInitialAreaConsumed = { speciesEntryAreaName = null },
                    collectionPreferences = speciesCollectionPreferences,
                    onCollectionPreferencesChange = { speciesCollectionPreferences = it },
                    onOpenSpecies = { key, filteredSpecies, context ->
                        speciesBrowseContext = SpeciesBrowseContext(filteredSpecies, context)
                        viewModel.openSpecies(key)
                    },
                )
                destination == TopDestination.Review -> SpeciesReviewScreen(
                    queue = state.reviewQueue,
                    loading = state.isReviewLoading,
                    decidingId = state.decidingReviewId,
                    identifyingId = state.identifyingReviewId,
                    batchIdentifying = state.isBatchIdentifying,
                    batchProgress = state.batchProgress,
                    offline = state.isOffline,
                    onRefresh = { viewModel.loadReviewQueue(force = true) },
                    onDecision = viewModel::decideReview,
                    onRequestRecommendation = viewModel::requestReviewRecommendation,
                    onConnectInat = viewModel::connectInat,
                    onSubmitBatch = viewModel::submitReviewBatch,
                    onBatchFinished = {
                        viewModel.clearBatchProgress()
                    },
                )
                destination == TopDestination.Publish -> PublishingScreen(
                    queue = state.publishQueue,
                    hikes = state.hikes,
                    loading = state.isPublishLoading,
                    publishingId = state.publishingId,
                    batchPublishing = state.isBatchPublishing,
                    publishBatchProgress = state.publishBatchProgress,
                    notice = state.publishNotice,
                    offline = state.isOffline,
                    onRefresh = { viewModel.loadPublishQueue(force = true) },
                    onPublish = viewModel::publishObservation,
                    onSubmitBatch = viewModel::submitPublishBatch,
                    onBatchFinished = viewModel::clearPublishBatchProgress,
                    onConnectInat = viewModel::connectInat,
                    onClearNotice = viewModel::clearPublishNotice,
                )
                destination == TopDestination.Map -> SightingsMapScreen(
                    sightings = state.sightings,
                    routeSegments = state.mapRouteSegments,
                    loading = state.isMapLoading,
                    openingPhotoId = openingMapPhotoId,
                    onRefresh = { viewModel.loadSightings(force = true) },
                    onOpenHike = viewModel::openEncounterHike,
                    onOpenPhoto = { sighting ->
                        openingMapPhotoId = sighting.id
                        viewModel.openEncounterPhoto(sighting.hikeId, sighting.id) { photo ->
                            if (openingMapPhotoId == sighting.id) {
                                openingMapPhotoId = null
                                selectedPhoto = photo
                            }
                        }
                    },
                )
                else -> LibraryScreen(
                    state = state,
                    tracking = trackingUi,
                    onOpenHike = viewModel::openHike,
                    onOpenTracking = { trackingVisible = true },
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
            !(trackingVisible && activeTracking != null) &&
            !badgesOpen
        ) {
            TopNavigation(
                selected = destination,
                onSelect = { destination = it },
                modifier = Modifier.align(Alignment.BottomCenter),
            )
        }

        Column(
            Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp)
                .navigationBarsPadding(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            AnimatedVisibility(
                visible = !state.error.isNullOrBlank(),
                enter = slideInVertically { it } + fadeIn(),
                exit = fadeOut(),
            ) {
                ErrorBanner(message = state.error.orEmpty(), onDismiss = viewModel::clearError)
            }
            AnimatedVisibility(
                visible = state.notice != null && state.error.isNullOrBlank(),
                enter = slideInVertically { it } + fadeIn(),
                exit = fadeOut(),
            ) {
                NoticeBanner(message = state.notice.orEmpty(), onDismiss = viewModel::clearNotice)
            }
            AnimatedVisibility(
                visible = destination != TopDestination.Publish &&
                    !state.publishNotice.isNullOrBlank() &&
                    state.error.isNullOrBlank(),
                enter = slideInVertically { it } + fadeIn(),
                exit = fadeOut(),
            ) {
                NoticeBanner(message = state.publishNotice.orEmpty(), onDismiss = viewModel::clearPublishNotice)
            }
        }
    }

    comparisonBaseHike?.takeIf { state.hikeComparison == null && !state.isLongitudinalLoading }?.let { base ->
        HikeComparisonPickerDialog(
            base = base,
            hikes = state.hikes.filterNot { it.id == base.id || it.isStandalone || it.isArchived },
            onDismiss = { comparisonBaseHike = null },
            onSelect = { other -> viewModel.openHikeComparison(base.id, other.id) },
        )
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
            trackingInProgress = trackingUi != null,
            onDismiss = { createEntryOpen = false },
            onStartHike = {
                createEntryOpen = false
                if (trackingUi != null) trackingVisible = true else beginTracking()
            },
            onCreateManualHike = {
                createEntryOpen = false
                viewModel.loadHikeLocations()
                creatingHike = true
            },
            onCreateEverydaySighting = {
                createEntryOpen = false
                pendingEverydayUpload = true
                identifyAfterUpload = true
                viewModel.openHike("everyday")
            },
        )
    }

    trackingIssue?.let { issue ->
        TrackingPreflightDialog(
            issue = issue,
            onDismiss = { trackingIssue = null },
            onOpenSettings = {
                trackingIssue = null
                val intent = when (issue) {
                    TrackingPreflightIssue.LocationDisabled -> Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
                    TrackingPreflightIssue.PreciseLocation,
                    TrackingPreflightIssue.Notifications -> Intent(
                        Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.parse("package:${context.packageName}"),
                    )
                }
                context.startActivity(intent)
            },
        )
    }

    pendingHikeDelete?.let { hike ->
        DeleteHikeDialog(
            hike = hike,
            deleting = state.deletingHikeId == hike.id,
            connected = state.syncStatus.connected,
            isLocalDraft = hike.id in state.syncStatus.pendingCreateHikeIds,
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
            onUpload = { caption, identify ->
                identifyAfterUpload = identify
                viewModel.uploadPhotos(
                    state.journal!!.id,
                    pendingUpload,
                    caption,
                    queueForReview = false,
                    prioritizeForIdentification = identify,
                    onUploaded = { photo ->
                        if (identifyAfterUpload && !photo.isVideo && selectedPhoto == null) {
                            selectedPhoto = photo
                        }
                    },
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
            identifying = state.identifyingReviewId == photo.id,
            resolvingSpeciesInfo = state.resolvingSpeciesInfoPhotoId == photo.id,
            savingForRecommendation = state.prioritizingPhotoId == photo.id,
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
            onRequestRecommendation = {
                viewModel.requestPhotoRecommendation(photo) { recommended ->
                    directReviewItem = recommended
                }
            },
            onSetCover = state.journal?.takeUnless { it.isStandalone || photo.isVideo }?.let {
                { selected: Boolean -> viewModel.setHikeCover(photo, selected) }
            },
            onAssignSpecies = if (!photo.isVideo && photo.species.none { it.isPrimary }) {
                { speciesAssignmentPhoto = photo }
            } else {
                null
            },
            onEditNaturalHistory = photo.species.firstOrNull { it.isPrimary }?.observationId?.let { observationId ->
                { confidence, phenophases ->
                    viewModel.updateObservationNaturalHistory(
                        photo,
                        observationId,
                        confidence,
                        phenophases,
                    )
                }
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

    directReviewItem?.let { item ->
        DirectPhotoReviewDialog(
            item = item,
            deciding = state.decidingReviewId == item.id,
            onDismiss = { directReviewItem = null },
            onDecision = { action, candidate ->
                viewModel.decideReview(item, action, candidate)
                directReviewItem = null
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
            webUrl = state.companionConfig.webUrl,
            companionVersion = state.companionConfig.apiVersion,
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
    tracking: TrackingUiModel?,
    onOpenHike: (String) -> Unit,
    onOpenTracking: () -> Unit,
    onRefresh: () -> Unit,
    onCreate: () -> Unit,
    onSettings: () -> Unit,
    onBadges: () -> Unit,
    onSync: () -> Unit,
    onRetrySync: () -> Unit,
    onShowSyncAttention: () -> Unit,
) {
    var query by rememberSaveable { mutableStateOf("") }
    var showArchived by rememberSaveable { mutableStateOf(false) }
    val everyday = remember(state.hikes, query) {
        state.hikes.firstOrNull { it.isStandalone }?.takeIf { hike ->
            query.isBlank() || listOf(hike.title, hike.notes).any { it.contains(query, ignoreCase = true) }
        }
    }
    val visibleHikes = remember(state.hikes, query, showArchived) {
        state.hikes.filterNot { it.isStandalone }.filter { hike ->
            (showArchived || !hike.isArchived) && listOf(hike.title, hike.locationName, hike.notes)
                .any { it.contains(query, ignoreCase = true) }
        }
    }
    val currentHikeCount = remember(state.hikes) {
        state.hikes.count { !it.isArchived && !it.isStandalone }
    }
    val totalMiles = remember(state.hikes) {
        state.hikes
            .filterNot { it.isStandalone }
            .sumOf { (it.distanceMiles ?: 0.0).coerceAtLeast(0.0) }
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
                    hikeCount = currentHikeCount,
                    totalMiles = totalMiles,
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
            tracking?.let { active ->
                item(key = "active-hike:${active.sessionId}") {
                    ActiveHikeRow(tracking = active, onOpen = onOpenTracking)
                }
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
private fun ActiveHikeRow(tracking: TrackingUiModel, onOpen: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .background(Color(0xFFE2E9DC))
            .clickable(onClick = onOpen)
            .padding(horizontal = 20.dp, vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(42.dp)
                .background(if (tracking.isPaused) Trail else Moss, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                if (tracking.isPaused) Icons.Rounded.PlayCircle else Icons.Rounded.Map,
                contentDescription = null,
                tint = Paper,
                modifier = Modifier.size(24.dp),
            )
        }
        Column(Modifier.weight(1f).padding(start = 13.dp)) {
            Text(
                if (tracking.isPaused) "HIKE PAUSED" else "HIKE IN PROGRESS",
                style = MaterialTheme.typography.labelSmall,
                color = if (tracking.isPaused) TrailText else Moss,
            )
            Text(
                "${formatTrackingDuration(tracking.elapsedSeconds)} active · ${formatTrackingDistance(tracking.distanceMiles)}",
                style = MaterialTheme.typography.titleMedium,
                color = Ink,
            )
        }
        Text("OPEN", style = MaterialTheme.typography.labelSmall, color = TrailText)
        Spacer(Modifier.width(5.dp))
        Icon(Icons.Rounded.ChevronRight, "Open active hike", tint = Fern)
    }
    HorizontalDivider(color = Line)
}

@Composable
private fun EverydayRow(journal: Hike, opening: Boolean, onOpen: (String) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(enabled = !opening) { onOpen(journal.id) }
            .padding(horizontal = 20.dp, vertical = 15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(88.dp).background(Moss)) {
            if (journal.coverUrl.isNotBlank()) {
                AsyncImage(journal.coverUrl, "Latest everyday sighting", Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
            } else {
                MountainField(Modifier.fillMaxSize())
            }
        }
        Column(Modifier.weight(1f).padding(start = 16.dp)) {
            Text("VARIOUS DATES", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text(
                "Everyday Sightings",
                style = MaterialTheme.typography.titleLarge,
                color = Ink,
            )
            Text(
                "Various Locations · ${journal.photoCount} photos",
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
    HorizontalDivider(color = Line, modifier = Modifier.padding(start = 124.dp))
}

@Composable
private fun LibraryHeader(
    hikeCount: Int,
    totalMiles: Double,
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
                        "$hikeCount OUTINGS · ${String.format(Locale.US, "%.1f", totalMiles)} MI HIKED · FIELD ARCHIVE",
                        style = MaterialTheme.typography.labelSmall,
                        color = Color(0xFFE1E9DD),
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
            Text(
                formatDate(hike.hikeDate).uppercase(Locale.US),
                style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold),
                color = Color(0xFFF1F3EE),
            )
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
                    HikeCardMetadata(hike = hike, color = Color(0xFFE4E9DF))
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
                HikeCardMetadata(hike = hike, color = InkMuted)
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
private fun HikeComparisonPickerDialog(
    base: Hike,
    hikes: List<Hike>,
    onDismiss: () -> Unit,
    onSelect: (Hike) -> Unit,
) {
    val ordered = hikes.sortedWith(
        compareByDescending<Hike> {
            base.primaryLocationId != null && it.primaryLocationId == base.primaryLocationId
        }.thenByDescending { it.hikeDate },
    )
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Compare field journals") },
        text = {
            if (ordered.isEmpty()) {
                Text("Record another hike before comparing visits.")
            } else {
                LazyColumn(Modifier.fillMaxWidth().heightIn(max = 420.dp)) {
                    item {
                        Text(
                            "Choose an outing to compare with ${base.title}.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = InkMuted,
                            modifier = Modifier.padding(bottom = 10.dp),
                        )
                    }
                    items(ordered, key = { it.id }) { hike ->
                        Row(
                            Modifier.fillMaxWidth().clickable { onSelect(hike) }.padding(vertical = 13.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(hike.hikeDate, style = MaterialTheme.typography.labelSmall, color = TrailText)
                                Text(hike.title, style = MaterialTheme.typography.titleMedium, color = Ink)
                                Text(
                                    hike.primaryLocationName.ifBlank { hike.locationName },
                                    style = MaterialTheme.typography.bodySmall,
                                    color = InkMuted,
                                )
                            }
                            Icon(Icons.Rounded.ChevronRight, contentDescription = null, tint = Fern)
                        }
                        HorizontalDivider(color = Line)
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
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
    onOpenPlace: (() -> Unit)?,
    onOpenBriefing: (() -> Unit)?,
    onCompare: (() -> Unit)?,
    onRefreshWeather: (() -> Unit)?,
    onPhoto: (Photo) -> Unit,
    onQueueReview: (List<Photo>) -> Unit,
) {
    val opening = state.openingHikeId == hike.id
    var selectingForReview by remember(hike.id) { mutableStateOf(false) }
    var selectedReviewIds by remember(hike.id) { mutableStateOf<Set<String>>(emptySet()) }
    val journalListState = rememberLazyListState()
    val journalScrollScope = rememberCoroutineScope()
    val reviewEligiblePhotos = hike.photos.filter { !it.isVideo && it.processingStatus != "in_review" }
    LaunchedEffect(hike.photos) {
        val availableIds = reviewEligiblePhotos.mapTo(hashSetOf()) { it.id }
        selectedReviewIds = selectedReviewIds.intersect(availableIds)
        if (selectingForReview && availableIds.isEmpty()) selectingForReview = false
    }
    Box(Modifier.fillMaxSize().background(Parchment)) {
        LazyColumn(
            Modifier.fillMaxSize(),
            state = journalListState,
            contentPadding = androidx.compose.foundation.layout.PaddingValues(
                bottom = if (selectingForReview) 142.dp else 64.dp,
            ),
        ) {
        item { JournalHero(hike, onBack, onEdit, onArchive, onDelete) }
        item {
            Column(Modifier.padding(horizontal = 20.dp, vertical = 24.dp)) {
                Text(formatDate(hike.hikeDate).uppercase(Locale.US), style = MaterialTheme.typography.labelSmall, color = TrailText)
                Text(hike.title, style = MaterialTheme.typography.displayMedium, color = Ink)
                if (journalHikeMeta(hike).isNotBlank()) {
                    Row(Modifier.padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            if (hike.locationName.isNotBlank()) Icons.Rounded.LocationOn else Icons.Rounded.Map,
                            null,
                            tint = Fern,
                            modifier = Modifier.size(18.dp),
                        )
                        Text(
                            journalHikeMeta(hike),
                            style = MaterialTheme.typography.bodyMedium,
                            color = InkMuted,
                            modifier = Modifier.padding(start = 5.dp),
                        )
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
                if (onRefreshWeather != null) {
                    JournalWeather(
                        weather = hike.weather,
                        loading = state.weatherUpdateId == hike.id,
                        onRefresh = onRefreshWeather,
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
                                "Loading journal photos",
                                style = MaterialTheme.typography.titleMedium,
                                color = Ink,
                            )
                            Text(
                                if (hike.photos.isEmpty()) {
                                    "Loading ${hike.photoCount} photo${if (hike.photoCount == 1) "" else "s"}…"
                                } else {
                                    "${hike.photos.size} of ${hike.photoCount} ready"
                                },
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
                if (onOpenPlace != null || onOpenBriefing != null || onCompare != null) {
                    Column(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                        onOpenPlace?.let { action ->
                            TextButton(onClick = action) {
                                Icon(Icons.Rounded.LocationOn, null, Modifier.size(18.dp))
                                Spacer(Modifier.width(7.dp))
                                Text("Open Place Profile")
                            }
                        }
                        onOpenBriefing?.let { action ->
                            TextButton(onClick = action) {
                                Icon(Icons.AutoMirrored.Rounded.FactCheck, null, Modifier.size(18.dp))
                                Spacer(Modifier.width(7.dp))
                                Text("Field Briefing for today")
                            }
                        }
                        onCompare?.let { action ->
                            TextButton(onClick = action) {
                                Icon(Icons.Rounded.CalendarMonth, null, Modifier.size(18.dp))
                                Spacer(Modifier.width(7.dp))
                                Text("Compare with another hike")
                            }
                        }
                    }
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
                    if (opening && hike.photos.isNotEmpty()) {
                        "${hike.photos.size} of ${hike.photoCount} photos"
                    } else {
                        "${if (opening) hike.photoCount else hike.photos.size} photos"
                    },
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
        if (opening && hike.photos.isEmpty()) {
            item { Spacer(Modifier.height(12.dp)) }
        } else if (!opening && hike.photos.isEmpty()) {
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
        if (!opening && hike.photos.isNotEmpty()) {
            item(key = "journal-back-to-top") {
                OutlinedButton(
                    onClick = {
                        journalScrollScope.launch { journalListState.animateScrollToItem(0) }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(start = 20.dp, end = 20.dp, top = 24.dp, bottom = 12.dp)
                        .height(50.dp),
                ) {
                    Icon(Icons.Rounded.KeyboardArrowUp, null, Modifier.size(20.dp))
                    Spacer(Modifier.width(7.dp))
                    Text("Back to top")
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
private fun JournalWeather(
    weather: WeatherSnapshot?,
    loading: Boolean,
    onRefresh: () -> Unit,
) {
    val uriHandler = LocalUriHandler.current
    Column(
        Modifier.fillMaxWidth().padding(top = 22.dp).background(Color(0xFFE2E9DC)).padding(16.dp),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Icon(
                when {
                    weather?.conditionLabel?.contains("Clear", ignoreCase = true) == true -> Icons.Rounded.WbSunny
                    weather?.precipitationTotalMm?.let { it > 0.05 } == true -> Icons.Rounded.WaterDrop
                    else -> Icons.Rounded.Cloud
                },
                contentDescription = null,
                tint = Trail,
                modifier = Modifier.size(28.dp),
            )
            Column(Modifier.weight(1f).padding(start = 12.dp)) {
                Text("CONDITIONS", style = MaterialTheme.typography.labelSmall, color = TrailText)
                Text(
                    weather?.let(::weatherHeadline) ?: "Add historical weather",
                    style = MaterialTheme.typography.titleLarge,
                    color = Ink,
                )
            }
            if (loading) {
                CircularProgressIndicator(Modifier.size(22.dp), color = Trail, strokeWidth = 2.dp)
            } else {
                TextButton(onClick = onRefresh) { Text(if (weather == null) "Add" else "Refresh") }
            }
        }
        if (weather != null) {
            val details = buildList {
                weather.precipitationTotalMm?.let { add("${String.format(Locale.US, "%.2f", it / 25.4)} in rain") }
                weather.relativeHumidityMeanPercent?.let { add("${it.roundToInt()}% humidity") }
                weather.windSpeedMeanKph?.let { add("${(it / 1.609344).roundToInt()} mph wind") }
                weather.cloudCoverMeanPercent?.let { add("${it.roundToInt()}% cloud cover") }
            }
            if (details.isNotEmpty()) {
                Text(details.joinToString(" · "), style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 7.dp))
            }
            Text(
                "Hike time/place summary · Open-Meteo weather data (CC BY 4.0)",
                style = MaterialTheme.typography.labelSmall,
                color = InkMuted,
                modifier = Modifier.padding(top = 9.dp).clickable {
                    uriHandler.openUri("https://open-meteo.com/")
                },
            )
        } else {
            Text(
                "Uses the route interval when available, otherwise the saved place and local hike date. Saving never waits for weather.",
                style = MaterialTheme.typography.bodySmall,
                color = InkMuted,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
    }
}

private fun weatherHeadline(weather: WeatherSnapshot): String {
    fun fahrenheit(value: Double): Int = (value * 9 / 5 + 32).roundToInt()
    val temperatures = when {
        weather.temperatureMinC != null && weather.temperatureMaxC != null ->
            "${fahrenheit(weather.temperatureMinC)}–${fahrenheit(weather.temperatureMaxC)}°F"
        weather.temperatureMeanC != null -> "${fahrenheit(weather.temperatureMeanC)}°F"
        else -> ""
    }
    return listOf(temperatures, weather.conditionLabel).filter(String::isNotBlank).joinToString(" · ")
        .ifBlank { "Historical conditions" }
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
    isLocalDraft: Boolean,
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
                    when {
                        connected -> "HikeJournal will verify the full deletion with the companion service."
                        isLocalDraft ->
                            "This unsynced draft will be removed from this phone now. Cleanup will sync when connected."
                        else -> "Connect HikeJournal to delete this hike and its stored files."
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = if (connected || isLocalDraft) InkMuted else MaterialTheme.colorScheme.error,
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
            TextButton(
                onClick = onDelete,
                enabled = understood && canConfirmHikeDeletion(connected, isLocalDraft) && !deleting,
            ) {
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

internal fun canConfirmHikeDeletion(connected: Boolean, isLocalDraft: Boolean): Boolean =
    connected || isLocalDraft

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
    trackingInProgress: Boolean,
    onDismiss: () -> Unit,
    onStartHike: () -> Unit,
    onCreateManualHike: () -> Unit,
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
            Text("NEW OUTING", style = MaterialTheme.typography.labelSmall, color = TrailText)
            Text(if (trackingInProgress) "Your hike is still going" else "Start a hike", style = MaterialTheme.typography.headlineLarge, color = Ink)
            Text(
                if (trackingInProgress) {
                    "Return to the live route, timer, and distance without losing a step."
                } else {
                    "Track your route, active time, and distance while you walk—even when the trail has no signal."
                },
                style = MaterialTheme.typography.bodyMedium,
                color = InkMuted,
                modifier = Modifier.padding(top = 6.dp, bottom = 20.dp),
            )
            Button(
                onClick = onStartHike,
                modifier = Modifier.fillMaxWidth().height(62.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Trail),
            ) {
                Icon(Icons.Rounded.PlayCircle, null)
                Spacer(Modifier.width(9.dp))
                Text(if (trackingInProgress) "Return to hike" else "Start tracking")
            }
            OutlinedButton(
                onClick = onCreateManualHike,
                modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(56.dp),
            ) {
                Icon(Icons.Rounded.Map, null)
                Spacer(Modifier.width(9.dp))
                Text("Create hike manually")
            }
            TextButton(
                onClick = onCreateEverydaySighting,
                modifier = Modifier.fillMaxWidth().padding(top = 6.dp).height(48.dp),
            ) {
                Icon(Icons.Rounded.CameraAlt, null)
                Spacer(Modifier.width(9.dp))
                Text("Add everyday sighting")
            }
        }
    }
}

@Composable
private fun TrackingPreflightDialog(
    issue: TrackingPreflightIssue,
    onDismiss: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    val title = when (issue) {
        TrackingPreflightIssue.PreciseLocation -> "Precise location is needed"
        TrackingPreflightIssue.Notifications -> "Keep hike tracking visible"
        TrackingPreflightIssue.LocationDisabled -> "Turn on device location"
    }
    val message = when (issue) {
        TrackingPreflightIssue.PreciseLocation ->
            "Allow precise location while using HikeJournal so your route and distance can be recorded accurately."
        TrackingPreflightIssue.Notifications ->
            "Allow notifications so the timer, distance, and hike controls stay available while the screen is locked or another app is open."
        TrackingPreflightIssue.LocationDisabled ->
            "Device location is off. Turn it on before starting so HikeJournal can find the trail and record your route."
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Rounded.LocationOn, contentDescription = null, tint = Trail) },
        title = { Text(title) },
        text = { Text(message) },
        confirmButton = {
            TextButton(onClick = onOpenSettings) {
                Text(if (issue == TrackingPreflightIssue.LocationDisabled) "Open location settings" else "Open app settings")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Not now") } },
    )
}

private fun missingTrackingPermissions(context: Context): Array<String> = buildList {
    if (context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
        // Android 12+ ignores a precise-only request. Ask for both location levels together.
        add(Manifest.permission.ACCESS_COARSE_LOCATION)
        add(Manifest.permission.ACCESS_FINE_LOCATION)
    }
    if (
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
        context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
    ) {
        add(Manifest.permission.POST_NOTIFICATIONS)
    }
}.toTypedArray()

private fun trackingPreflightIssue(context: Context): TrackingPreflightIssue? {
    if (context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
        return TrackingPreflightIssue.PreciseLocation
    }
    if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) {
        return TrackingPreflightIssue.Notifications
    }
    val locationManager = context.getSystemService(LocationManager::class.java)
    if (!LocationManagerCompat.isLocationEnabled(locationManager)) return TrackingPreflightIssue.LocationDisabled
    return null
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
    var distance by remember(hike?.id) {
        mutableStateOf(hike?.distanceMiles?.let { String.format(Locale.US, "%.2f", it) }.orEmpty())
    }
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
                Text(
                    "After saving, the first photo opens so you can ask iNaturalist for a recommendation and choose the best match.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(vertical = 16.dp),
                )
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
                    onClick = { onUpload(caption, isEverydaySighting) },
                    modifier = Modifier.align(Alignment.CenterHorizontally).padding(top = 4.dp),
                ) {
                    Text("Save without GPS")
                }
            } else {
                Button(
                    onClick = { onUpload(caption, isEverydaySighting) },
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
                        Text(if (isEverydaySighting) "Save & identify" else "Save $photoCount file${if (photoCount == 1) "" else "s"}")
                    }
                }
                if (isEverydaySighting) {
                    TextButton(
                        onClick = { onUpload(caption, false) },
                        modifier = Modifier.align(Alignment.CenterHorizontally).padding(top = 4.dp),
                    ) { Text("Save without identifying") }
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
    identifying: Boolean,
    resolvingSpeciesInfo: Boolean,
    savingForRecommendation: Boolean,
    onDismiss: () -> Unit,
    onPrevious: (() -> Unit)?,
    onNext: (() -> Unit)?,
    onSaveCaption: (String) -> Unit,
    onDelete: () -> Unit,
    onSetReview: (Boolean) -> Unit,
    onRequestRecommendation: () -> Unit,
    onSetCover: ((Boolean) -> Unit)?,
    onAssignSpecies: (() -> Unit)?,
    onEditNaturalHistory: ((String, List<String>) -> Unit)?,
    onViewMap: (() -> Unit)?,
) {
    val identifiedSpecies = photo.species.firstOrNull { it.isPrimary }
    val uriHandler = LocalUriHandler.current
    var caption by remember(photo.id) { mutableStateOf(photo.caption) }
    var confirmDelete by remember { mutableStateOf(false) }
    var photoFullscreen by remember { mutableStateOf(false) }
    var videoFullscreen by remember(photo.id) { mutableStateOf(false) }
    var horizontalDragDistance by remember(photo.id) { mutableFloatStateOf(0f) }
    var editingNaturalHistory by remember(photo.id) { mutableStateOf(false) }
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
                } else {
                    AsyncImage(photo.url, photo.caption, Modifier.fillMaxSize(), contentScale = ContentScale.Fit)
                    FilledIconButton(
                        onClick = { photoFullscreen = true },
                        modifier = Modifier.align(Alignment.TopEnd).padding(12.dp),
                        colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(containerColor = Color(0xB018221C)),
                    ) { Icon(Icons.Rounded.Fullscreen, "Open full-screen photo", tint = Paper) }
                }
            }
            Column(
                Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .background(Color(0xFF18221C)),
            ) {
                Column(
                    Modifier
                        .fillMaxSize()
                        .imePadding()
                        .navigationBarsPadding()
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = 16.dp)
                        .padding(top = 16.dp, bottom = 32.dp),
                ) {
                identifiedSpecies?.let { species ->
                    Text(species.commonName.ifBlank { species.scientificName }, style = MaterialTheme.typography.titleMedium, color = Color(0xFFBFD2B9))
                    if (species.observationId != null) {
                        Text(
                            "${friendlyConfidence(species.confidence)} · ${friendlyProvenance(species.provenance)}",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFF91AA8C),
                            modifier = Modifier.padding(top = 4.dp),
                        )
                        if (species.phenophases.isNotEmpty()) {
                            Text(
                                species.phenophases.joinToString(" · ") { it.replace('_', ' ').replaceFirstChar(Char::uppercase) },
                                style = MaterialTheme.typography.bodyMedium,
                                color = Paper,
                                modifier = Modifier.padding(top = 5.dp),
                            )
                        }
                        if (species.identificationHistory.isNotEmpty()) {
                            Text(
                                "IDENTIFICATION HISTORY",
                                style = MaterialTheme.typography.labelSmall,
                                color = Color(0xFF91AA8C),
                                modifier = Modifier.padding(top = 14.dp),
                            )
                            species.identificationHistory.take(3).forEach { event ->
                                Text(
                                    "${event.createdAt?.take(10).orEmpty()} · ${friendlyProvenance(event.source)} → " +
                                        event.commonName.ifBlank { event.scientificName },
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Color(0xFFBFD2B9),
                                    modifier = Modifier.padding(top = 3.dp),
                                )
                            }
                        }
                        if (onEditNaturalHistory != null) {
                            OutlinedButton(
                                onClick = { editingNaturalHistory = true },
                                modifier = Modifier.fillMaxWidth().padding(top = 12.dp).height(46.dp),
                                border = BorderStroke(1.dp, Color(0xFF91AA8C)),
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = Paper),
                            ) {
                                Text("Confidence & phenophase")
                            }
                        }
                    }
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
                } else if (identifiedSpecies != null) {
                    if (resolvingSpeciesInfo) {
                        Button(
                            onClick = {},
                            enabled = false,
                            modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(48.dp),
                        ) {
                            CircularProgressIndicator(Modifier.size(18.dp), color = Paper, strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                            Text("Loading species information…")
                        }
                    } else if (identifiedSpecies.wikipediaSummary.isNotBlank()) {
                        Text(
                            "FROM WIKIPEDIA",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFF91AA8C),
                            modifier = Modifier.padding(top = 14.dp),
                        )
                        Text(
                            identifiedSpecies.wikipediaSummary,
                            style = MaterialTheme.typography.bodyMedium,
                            color = Paper,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                    }
                    if (!resolvingSpeciesInfo && identifiedSpecies.wikipediaUrl.isNotBlank()) {
                        TextButton(
                            onClick = { uriHandler.openUri(identifiedSpecies.wikipediaUrl) },
                            modifier = Modifier.padding(top = 4.dp),
                            colors = ButtonDefaults.textButtonColors(contentColor = Color(0xFFE5F1DF)),
                        ) {
                            Text(
                                "Read on Wikipedia",
                                style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.SemiBold),
                            )
                            Spacer(Modifier.width(4.dp))
                            Icon(Icons.AutoMirrored.Rounded.OpenInNew, null, modifier = Modifier.size(16.dp))
                        }
                    }
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
                    Button(
                        onClick = onRequestRecommendation,
                        enabled = !identifying && !savingForRecommendation && photo.syncState == "synced" && !photo.url.startsWith("file:"),
                        modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(48.dp),
                    ) {
                        if (identifying || savingForRecommendation) CircularProgressIndicator(Modifier.size(18.dp), color = Paper, strokeWidth = 2.dp)
                        else Icon(Icons.Rounded.Refresh, null)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            when {
                                savingForRecommendation -> "Saving photo for iNaturalist..."
                                identifying -> "Asking iNaturalist..."
                                else -> "Get iNaturalist recommendation"
                            },
                        )
                    }
                    if (!savingForRecommendation && (photo.syncState != "synced" || photo.url.startsWith("file:"))) {
                        Text(
                            "Available once this photo finishes saving.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFBFD2B9),
                            modifier = Modifier.padding(top = 5.dp),
                        )
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
                }
                if (onSetCover != null) {
                    PhotoSettingRow(
                        checked = isCoverPhoto,
                        updating = updatingCover,
                        title = "Hike cover",
                        detail = if (isCoverPhoto) "Shown in your archive and journal." else "Use this photo as the hike cover.",
                        onCheckedChange = onSetCover,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
                HorizontalDivider(color = Color(0xFF405148), modifier = Modifier.padding(top = 13.dp))
                    OutlinedTextField(
                        caption,
                        { caption = it },
                        Modifier.fillMaxWidth(),
                        label = { Text(if (photo.isVideo) "Video note" else "Photo note", color = Color(0xFFE5F1DF)) },
                        placeholder = { Text(if (photo.isVideo) "Enter video note…" else "Enter photo note…", color = Color(0xFFD3E0CF)) },
                        textStyle = MaterialTheme.typography.bodyLarge.copy(color = Paper),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = Paper,
                            unfocusedTextColor = Paper,
                            focusedPlaceholderColor = Color(0xFFD3E0CF),
                            unfocusedPlaceholderColor = Color(0xFFD3E0CF),
                        ),
                    )
                    Button(
                        onClick = { onSaveCaption(caption) },
                        modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(52.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF315844), contentColor = Paper),
                    ) { Text("Save note") }
                    Spacer(Modifier.height(16.dp))
                }
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
    if (photoFullscreen) {
        FullscreenPhotoViewer(
            photo = photo,
            onDismiss = { photoFullscreen = false },
            onPrevious = onPrevious,
            onNext = onNext,
        )
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
    if (editingNaturalHistory && identifiedSpecies != null && onEditNaturalHistory != null) {
        NaturalHistoryDialog(
            species = identifiedSpecies,
            onDismiss = { editingNaturalHistory = false },
            onSave = { confidence, phenophases ->
                editingNaturalHistory = false
                onEditNaturalHistory(confidence, phenophases)
            },
        )
    }
}

@Composable
private fun NaturalHistoryDialog(
    species: SpeciesLabel,
    onDismiss: () -> Unit,
    onSave: (String, List<String>) -> Unit,
) {
    var confidence by remember(species.observationId) { mutableStateOf(species.confidence) }
    var phenophases by remember(species.observationId) { mutableStateOf(species.phenophases.toSet()) }
    val confidenceOptions = listOf(
        "tentative" to "Tentative",
        "likely" to "Likely",
        "confident" to "Confident",
        "externally_confirmed" to "Externally confirmed",
    )
    val phenophaseOptions = listOf(
        "vegetative" to "Vegetative",
        "budding" to "Budding",
        "flowering" to "Flowering",
        "fruiting" to "Fruiting",
        "senescent" to "Senescent",
    )
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Natural-history detail") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text("IDENTIFICATION CONFIDENCE", style = MaterialTheme.typography.labelSmall, color = TrailText)
                confidenceOptions.forEach { (value, label) ->
                    Row(
                        Modifier.fillMaxWidth().clickable { confidence = value }.padding(vertical = 5.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = confidence == value, onClick = { confidence = value })
                        Text(label, style = MaterialTheme.typography.bodyLarge, color = Ink)
                    }
                }
                if (species.iconicTaxonName == "Plantae") {
                    Text(
                        "PLANT PHENOPHASE · OPTIONAL",
                        style = MaterialTheme.typography.labelSmall,
                        color = TrailText,
                        modifier = Modifier.padding(top = 12.dp),
                    )
                    phenophaseOptions.forEach { (value, label) ->
                        Row(
                            Modifier.fillMaxWidth().clickable {
                                phenophases = if (value in phenophases) phenophases - value else phenophases + value
                            }.padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Checkbox(
                                checked = value in phenophases,
                                onCheckedChange = { checked ->
                                    phenophases = if (checked) phenophases + value else phenophases - value
                                },
                            )
                            Text(label, style = MaterialTheme.typography.bodyLarge, color = Ink)
                        }
                    }
                }
                Text(
                    "These labels describe your observation; they do not claim a species-wide season.",
                    style = MaterialTheme.typography.bodySmall,
                    color = InkMuted,
                    fontStyle = FontStyle.Italic,
                    modifier = Modifier.padding(top = 10.dp),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(confidence, phenophases.sorted()) }) { Text("Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun DirectPhotoReviewDialog(
    item: ReviewItem,
    deciding: Boolean,
    onDismiss: () -> Unit,
    onDecision: (String, ReviewCandidate?) -> Unit,
) {
    var selectedIndex by remember(item.id) { mutableStateOf(0) }
    val selected = item.candidates.getOrNull(selectedIndex)
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Column(
            Modifier
                .fillMaxWidth()
                .background(Paper, RoundedCornerShape(24.dp))
                .padding(20.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Choose the best match", style = MaterialTheme.typography.headlineSmall, color = Ink)
                    Text("iNaturalist’s suggestion for this photo", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
                }
                IconButton(onClick = onDismiss) { Icon(Icons.Rounded.Close, "Close", tint = Ink) }
            }
            item.candidates.forEachIndexed { index, candidate ->
                Row(
                    Modifier.fillMaxWidth().clickable { selectedIndex = index }.padding(vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RadioButton(selected = selectedIndex == index, onClick = { selectedIndex = index })
                    Column(Modifier.weight(1f).padding(start = 6.dp)) {
                        Text(candidate.commonName, style = MaterialTheme.typography.titleMedium, color = Ink)
                        if (candidate.scientificName.isNotBlank()) {
                            Text(candidate.scientificName, style = MaterialTheme.typography.bodyMedium, color = InkMuted, fontStyle = FontStyle.Italic)
                        }
                    }
                    candidate.confidence?.let { confidence ->
                        Text("${(confidence * if (confidence <= 1) 100 else 1).toInt()}%", style = MaterialTheme.typography.labelMedium, color = Moss)
                    }
                }
            }
            Button(
                onClick = { onDecision("confirm", selected) },
                enabled = selected != null && !deciding,
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp).height(52.dp),
            ) {
                if (deciding) CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                else Icon(Icons.Rounded.Check, null)
                Spacer(Modifier.width(8.dp))
                Text(if (selectedIndex == 0) "Confirm ID" else "Use this ID")
            }
            Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = onDismiss, enabled = !deciding, modifier = Modifier.weight(1f)) { Text("Skip") }
                OutlinedButton(
                    onClick = { onDecision("reject", null) },
                    enabled = !deciding,
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Trail),
                    modifier = Modifier.weight(1f),
                ) { Text("Reject") }
            }
            Text(
                "Reject removes this suggestion but keeps the photo ready for another recommendation.",
                style = MaterialTheme.typography.bodySmall,
                color = InkMuted,
                modifier = Modifier.padding(top = 9.dp),
            )
        }
    }
}

@Composable
private fun FullscreenPhotoViewer(
    photo: Photo,
    onDismiss: () -> Unit,
    onPrevious: (() -> Unit)?,
    onNext: (() -> Unit)?,
) {
    var horizontalDragDistance by remember { mutableFloatStateOf(0f) }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Box(
            Modifier.fillMaxSize().background(Color.Black).pointerInput(photo.id) {
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
            AsyncImage(photo.url, photo.caption, Modifier.fillMaxSize(), contentScale = ContentScale.Fit)
            FilledIconButton(
                onClick = onDismiss,
                modifier = Modifier.align(Alignment.TopEnd).statusBarsPadding().padding(12.dp),
                colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(containerColor = Color(0xB018221C)),
            ) { Icon(Icons.Rounded.Close, "Exit full-screen photo", tint = Paper) }
        }
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
    webUrl: String,
    companionVersion: String?,
    inatConnected: Boolean,
    onDismiss: () -> Unit,
    onSave: (String, String) -> Unit,
    onConnectInat: () -> Unit,
) {
    var url by remember(currentUrl) { mutableStateOf(currentUrl) }
    var key by remember(currentKey) { mutableStateOf(currentKey) }
    var validation by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    val openWebUrl = remember(webUrl) { validSettingsWebUrl(webUrl) }
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
                if (openWebUrl != null) {
                    TextButton(
                        onClick = { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(openWebUrl))) },
                        modifier = Modifier.padding(top = 8.dp),
                    ) {
                        Icon(Icons.AutoMirrored.Rounded.OpenInNew, null)
                        Spacer(Modifier.width(7.dp))
                        Text("Open HikeJournal on the web")
                    }
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
                Text(
                    buildString {
                        append("HikeJournal ${BuildConfig.VERSION_NAME}")
                        companionVersion?.takeIf(String::isNotBlank)?.let { append(" · Companion $it") }
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = InkMuted,
                    modifier = Modifier.fillMaxWidth().padding(top = 20.dp),
                    textAlign = TextAlign.Center,
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val cleanUrl = url.trim()
                    when (val urlError = connectionUrlError(cleanUrl, allowCleartext = BuildConfig.DEBUG)) {
                        null -> if (key.isBlank()) {
                            validation = "Enter the pairing key."
                        } else {
                            onSave(cleanUrl, key.trim())
                        }
                        else -> validation = urlError
                    }
                },
            ) {
                Text("Reconnect")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

internal fun connectionUrlError(value: String, allowCleartext: Boolean): String? {
    val clean = value.trim()
    if (clean.isBlank()) return "Enter the HikeJournal connection address."
    val uri = runCatching { URI(clean) }.getOrNull()
    val scheme = uri?.scheme?.lowercase()
    if (
        scheme !in setOf("http", "https") ||
        uri?.host.isNullOrBlank() ||
        uri?.userInfo != null ||
        uri?.rawQuery != null ||
        uri?.rawFragment != null
    ) {
        return "Enter a complete https:// base address without credentials, a query, or a fragment."
    }
    if (!allowCleartext && scheme != "https") {
        return "Personal releases require an https:// companion address."
    }
    return null
}

internal fun validSettingsWebUrl(value: String): String? {
    val clean = value.trim().trimEnd('/')
    val uri = runCatching { URI(clean) }.getOrNull()
    return clean.takeIf {
        uri?.scheme?.lowercase() in setOf("http", "https") &&
            !uri?.host.isNullOrBlank() &&
            uri?.userInfo == null &&
            uri?.rawQuery == null &&
            uri?.rawFragment == null
    }
}

@Composable
private fun ErrorBanner(message: String, onDismiss: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onDismiss),
        color = Color(0xFF8F3D32),
        shape = RoundedCornerShape(18.dp),
        shadowElevation = 8.dp,
    ) {
        Row(
            Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Text(message, color = Paper, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            Icon(Icons.Rounded.Close, "Dismiss", tint = Paper, modifier = Modifier.padding(start = 12.dp))
        }
    }
}

@Composable
private fun NoticeBanner(message: String, onDismiss: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onDismiss),
        color = Moss,
        shape = RoundedCornerShape(18.dp),
        shadowElevation = 8.dp,
    ) {
        Row(
            Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Icon(Icons.Rounded.Check, "Complete", tint = Paper, modifier = Modifier.size(20.dp))
            Text(
                message,
                color = Paper,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f).padding(start = 10.dp),
            )
            Icon(Icons.Rounded.Close, "Dismiss", tint = Paper, modifier = Modifier.padding(start = 12.dp))
        }
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
        Text("The first photo is waiting", style = MaterialTheme.typography.headlineSmall, color = Ink, modifier = Modifier.padding(top = 12.dp))
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

@Composable
private fun HikeCardMetadata(hike: Hike, color: Color) {
    // AnimatedContent positions each direct child in the same content area. Keep the
    // location and stats in one vertical layout so featured-card metadata can never overlap.
    Column {
        if (hike.locationName.isNotBlank()) {
            Text(
                hike.locationName,
                style = MaterialTheme.typography.bodyMedium,
                color = color,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }

        val stats = mutableListOf<String>()
        hike.distanceMiles?.let { stats += String.format(Locale.US, "%.1f mi", it) }
        if (hike.photoCount > 0) stats += "${hike.photoCount} photos"
        Text(
            stats.joinToString(" · ").ifBlank { "Field journal" },
            style = MaterialTheme.typography.bodyMedium,
            color = color,
        )
    }
}

private fun journalHikeMeta(hike: Hike): String {
    val parts = mutableListOf<String>()
    if (hike.locationName.isNotBlank()) parts += hike.locationName
    hike.distanceMiles?.let { parts += String.format(Locale.US, "%.2f mi", it) }
    hike.durationSeconds?.let { parts += "${formatTrackingDuration(it)} active" }
    return parts.joinToString(" · ")
}

private fun formatDate(raw: String): String = try {
    LocalDate.parse(raw).format(DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US))
} catch (_: Exception) {
    raw
}

private fun friendlyConfidence(value: String): String = when (value) {
    "externally_confirmed" -> "Externally confirmed"
    "confident" -> "Confident"
    "likely" -> "Likely"
    else -> "Tentative"
}

private fun friendlyProvenance(value: String): String = when (value) {
    "user" -> "You"
    "inat_computer_vision" -> "iNaturalist suggestion"
    "inat_lookup" -> "iNaturalist taxon lookup"
    "inat_community" -> "iNaturalist community"
    "external_expert" -> "External expert"
    "imported_record" -> "Imported record"
    else -> "Legacy record"
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
