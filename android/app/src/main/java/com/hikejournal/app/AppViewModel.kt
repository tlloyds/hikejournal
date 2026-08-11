package com.hikejournal.app

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.HikeDraft
import com.hikejournal.app.data.HikeDeletionResult
import com.hikejournal.app.data.HikeJournalRepository
import com.hikejournal.app.data.HikeLocation
import com.hikejournal.app.data.HikeLocationSuggestion
import com.hikejournal.app.data.MediaLocationSummary
import com.hikejournal.app.data.BadgeMetric
import com.hikejournal.app.data.CompanionConfig
import com.hikejournal.app.data.DiscoveryArea
import com.hikejournal.app.data.DiscoveryProgress
import com.hikejournal.app.data.DiscoveryTaxon
import com.hikejournal.app.data.BriefingItem
import com.hikejournal.app.data.FieldQuest
import com.hikejournal.app.data.FieldBriefing
import com.hikejournal.app.data.FieldMark
import com.hikejournal.app.data.FieldCelebration
import com.hikejournal.app.data.HikeComparison
import com.hikejournal.app.data.NearbySpecies
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.PlaceProfile
import com.hikejournal.app.data.PublishBatchStatus
import com.hikejournal.app.data.PublishBatchRequest
import com.hikejournal.app.data.PublishBatchWork
import com.hikejournal.app.data.PublishItem
import com.hikejournal.app.data.PublishOptions
import com.hikejournal.app.data.PublishQueue
import com.hikejournal.app.data.ReviewCandidate
import com.hikejournal.app.data.ReviewItem
import com.hikejournal.app.data.ReviewBatchStatus
import com.hikejournal.app.data.RecordedRouteUpload
import com.hikejournal.app.data.RoutePoint
import com.hikejournal.app.data.QuestSightingsMap
import com.hikejournal.app.data.Sighting
import com.hikejournal.app.data.SpeciesLabel
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.data.SpeciesReviewBatchWork
import com.hikejournal.app.data.SyncStatus
import com.hikejournal.app.data.SyncScheduler
import com.hikejournal.app.data.calculateTrailBadges
import com.hikejournal.app.data.buildConfirmedSpeciesCelebration
import com.hikejournal.app.data.buildHikeMilestoneCelebration
import com.hikejournal.app.data.buildKnownSpeciesRediscoveryCelebration
import com.hikejournal.app.data.buildReviewBatchCelebration
import com.hikejournal.app.data.speciesTypeCounts
import com.hikejournal.app.data.withoutHikes
import com.hikejournal.app.data.toDiscoveryTaxon
import com.hikejournal.app.data.suggestHikeLocation
import com.hikejournal.app.tracking.HikeTrackingService
import com.hikejournal.app.tracking.TrackingRepository
import com.hikejournal.app.tracking.TrackingSnapshot
import com.hikejournal.app.tracking.TrackingStatus
import java.time.Instant
import java.util.Locale
import java.util.UUID
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class LongitudinalDestination { PlaceProfile, FieldBriefing, Comparison }

internal fun shouldRefreshReviewQueueAfterSync(
    reviewQueueRequested: Boolean,
    previousOutstandingSyncCount: Int,
    outstandingSyncCount: Int,
    connected: Boolean,
): Boolean = reviewQueueRequested &&
    previousOutstandingSyncCount > 0 &&
    outstandingSyncCount == 0 &&
    connected

data class AppState(
    val hikes: List<Hike> = emptyList(),
    val hikeLocations: List<HikeLocation> = emptyList(),
    val journal: Hike? = null,
    val species: List<SpeciesRecord> = emptyList(),
    val speciesDetail: SpeciesRecord? = null,
    val placeProfile: PlaceProfile? = null,
    val fieldBriefing: FieldBriefing? = null,
    val hikeComparison: HikeComparison? = null,
    val discoveryAreas: List<DiscoveryArea> = emptyList(),
    val nearbySpecies: NearbySpecies? = null,
    val speciesQuests: List<FieldQuest> = emptyList(),
    val questMapQuest: FieldQuest? = null,
    val questMapNearby: NearbySpecies? = null,
    val questMapTaxon: DiscoveryTaxon? = null,
    val questSightingsMap: QuestSightingsMap? = null,
    val sightings: List<Sighting> = emptyList(),
    val mapRouteSegments: List<List<com.hikejournal.app.data.RoutePoint>> = emptyList(),
    val reviewQueue: List<ReviewItem> = emptyList(),
    val publishQueue: PublishQueue = PublishQueue(false, 0, 0, 0, emptyList()),
    val companionConfig: CompanionConfig = CompanionConfig(webUrl = BuildConfig.DEFAULT_WEB_URL),
    val isLoading: Boolean = true,
    val openingHikeId: String? = null,
    val isRefreshing: Boolean = false,
    val isOffline: Boolean = false,
    val error: String? = null,
    val notice: String? = null,
    val celebration: FieldCelebration? = null,
    val uploadCurrent: Int = 0,
    val uploadTotal: Int = 0,
    val isSpeciesLoading: Boolean = false,
    val isBadgeLoading: Boolean = false,
    val badgesHydrated: Boolean = false,
    val badgeNotice: String? = null,
    val isDiscoveryLoading: Boolean = false,
    val isSavingQuest: Boolean = false,
    val discoveryNotice: String? = null,
    val isQuestMapLoading: Boolean = false,
    val questMapNotice: String? = null,
    val isMapLoading: Boolean = false,
    val isReviewLoading: Boolean = false,
    val decidingReviewId: String? = null,
    val identifyingReviewId: String? = null,
    val isBatchIdentifying: Boolean = false,
    val batchProgress: ReviewBatchStatus? = null,
    val resolvingSpeciesInfoPhotoId: String? = null,
    val prioritizingPhotoId: String? = null,
    val inatAuthorizationUrl: String? = null,
    val reviewUpdateId: String? = null,
    val speciesAssignmentId: String? = null,
    val coverUpdateId: String? = null,
    val weatherUpdateId: String? = null,
    val deletingHikeId: String? = null,
    val isPublishLoading: Boolean = false,
    val publishingId: String? = null,
    val isBatchPublishing: Boolean = false,
    val publishBatchProgress: PublishBatchStatus? = null,
    val publishNotice: String? = null,
    val syncStatus: SyncStatus = SyncStatus(),
    val isSyncing: Boolean = false,
    val tracking: TrackingSnapshot? = null,
    val trackingMarks: List<FieldMark> = emptyList(),
    val isLongitudinalLoading: Boolean = false,
    val longitudinalDestination: LongitudinalDestination? = null,
    val trackingOpenRequestToken: Long = 0L,
    val trackingEndRequestToken: Long = 0L,
    val isFinalizingTracking: Boolean = false,
)

class AppViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = HikeJournalRepository(application)
    private val trackingRepository = TrackingRepository.get(application)
    private val appContext = application.applicationContext
    private val _state = MutableStateFlow(AppState())
    val state: StateFlow<AppState> = _state.asStateFlow()
    private var observedSpeciesBatchWorkId: UUID? = null
    private var observedPublishBatchWorkId: UUID? = null
    private var handledSpeciesBatchWorkId: UUID? = null
    private var handledPublishBatchWorkId: UUID? = null
    private var mapDataValidated = false
    private var loadedTrackingMarksForHikeId: String? = null
    private var reviewQueueRequested = false

    val serverUrl: String get() = repository.serverUrl
    val pairingKey: String get() = repository.pairingKey

    init {
        // Reconcile any durable operation whose enqueue completed just before the process died.
        SyncScheduler.schedule(appContext)
        viewModelScope.launch {
            try {
                val recovered = trackingRepository.recover()
                if (recovered?.status in setOf(TrackingStatus.STARTING, TrackingStatus.RECORDING)) {
                    // An Activity launch is a foreground-safe opportunity to restore a service
                    // that may have been killed while its durable recording remained active.
                    HikeTrackingService.start(appContext)
                }
            } catch (error: Exception) {
                runCatching {
                    trackingRepository.pauseAfterServiceFailure(
                        "Hike tracking paused because Android could not restore the GPS service.",
                    )
                }
                _state.update { it.copy(error = error.userMessage()) }
            }
            trackingRepository.snapshots.collect { snapshot ->
                _state.update {
                    it.copy(
                        tracking = snapshot?.takeUnless { current -> current.status == TrackingStatus.FINISHED },
                        isFinalizingTracking = snapshot?.status == TrackingStatus.FINALIZING,
                    )
                }
                val activeHikeId = snapshot?.hikeId
                if (activeHikeId != null && activeHikeId != loadedTrackingMarksForHikeId) {
                    loadedTrackingMarksForHikeId = activeHikeId
                    val marks = runCatching { repository.loadLocalFieldMarks(activeHikeId) }.getOrDefault(emptyList())
                    _state.update { it.copy(trackingMarks = marks) }
                } else if (activeHikeId == null) {
                    loadedTrackingMarksForHikeId = null
                    _state.update { it.copy(trackingMarks = emptyList()) }
                }
            }
        }
        viewModelScope.launch {
            var previousOutstandingSyncCount = 0
            repository.syncStatus.collect { syncStatus ->
                val outstandingSyncCount = syncStatus.pendingCount +
                    syncStatus.syncingCount +
                    syncStatus.needsAttentionCount
                val reviewUploadsSettled = shouldRefreshReviewQueueAfterSync(
                    reviewQueueRequested = reviewQueueRequested,
                    previousOutstandingSyncCount = previousOutstandingSyncCount,
                    outstandingSyncCount = outstandingSyncCount,
                    connected = syncStatus.connected,
                )
                previousOutstandingSyncCount = outstandingSyncCount
                val journalNeedsRemoteUrls = syncStatus.connected &&
                    syncStatus.pendingCount == 0 &&
                    syncStatus.syncingCount == 0 &&
                    _state.value.journal?.photos.orEmpty().any { photo ->
                        photo.syncState != "synced" || photo.url.startsWith("file:")
                    }
                val journalCoverNeedsRemoteUrl = syncStatus.connected &&
                    _state.value.coverUpdateId == null &&
                    _state.value.journal?.let { journal ->
                        journal.coverUrl.startsWith("file:") && journal.id !in syncStatus.coverSyncHikeIds
                    } == true
                val archiveNeedsRemoteCoverUrls = syncStatus.connected &&
                    _state.value.coverUpdateId == null &&
                    _state.value.hikes.any { hike ->
                        hike.coverPhotoId != null &&
                            hike.coverUrl.startsWith("file:") &&
                            hike.id !in syncStatus.coverSyncHikeIds
                    }
                _state.update {
                    it.copy(
                        syncStatus = syncStatus,
                        isOffline = !syncStatus.connected || it.isOffline && syncStatus.pendingCount > 0,
                    )
                }
                if (journalNeedsRemoteUrls || journalCoverNeedsRemoteUrl) {
                    refreshJournalAfterSync(_state.value.journal?.id ?: return@collect)
                }
                if (archiveNeedsRemoteCoverUrls) {
                    // Successful upload sync removes its temporary local file. Replace any
                    // archive covers that still point to that file with the permanent URL.
                    refreshLibrary(showRefreshIndicator = false)
                }
                if (reviewUploadsSettled) {
                    loadReviewQueue(force = true)
                }
            }
        }
        observeSpeciesReviewBatchWork()
        observePublishBatchWork()
        refreshCompanionConfig()
        primeMapData()
        loadInitialLibrary()
    }

    /**
     * Capability discovery is deliberately fail-open. Older companions can omit this endpoint
     * and offline startup continues to use the build's existing web-link fallback.
     */
    private fun refreshCompanionConfig() {
        val requestedServerUrl = repository.serverUrl
        viewModelScope.launch {
            runCatching { repository.loadCompanionConfig() }
                .onSuccess { config ->
                    if (repository.serverUrl == requestedServerUrl) {
                        _state.update { it.copy(companionConfig = config) }
                    }
                }
        }
    }

    private fun observeSpeciesReviewBatchWork() {
        viewModelScope.launch {
            WorkManager.getInstance(appContext)
                .getWorkInfosForUniqueWorkFlow(SpeciesReviewBatchWork.WorkName)
                .collect { workInfos ->
                    val work = workInfos.firstOrNull() ?: return@collect
                    if (!adoptSpeciesBatchWork(work)) return@collect
                    val status = if (work.state.isFinished) {
                        SpeciesReviewBatchWork.statusFromData(work.outputData)
                            ?: SpeciesReviewBatchWork.statusFromData(work.progress)
                    } else {
                        SpeciesReviewBatchWork.statusFromData(work.progress)
                    }
                    when (work.state) {
                        WorkInfo.State.ENQUEUED, WorkInfo.State.RUNNING, WorkInfo.State.BLOCKED -> {
                            _state.update { current ->
                                current.copy(
                                    isBatchIdentifying = true,
                                    batchProgress = status ?: current.batchProgress,
                                )
                            }
                        }
                        WorkInfo.State.SUCCEEDED, WorkInfo.State.FAILED, WorkInfo.State.CANCELLED -> {
                            if (handledSpeciesBatchWorkId == work.id) return@collect
                            handledSpeciesBatchWorkId = work.id
                            finishSpeciesReviewBatch(work, status)
                        }
                        else -> Unit
                    }
                }
        }
    }

    private fun adoptSpeciesBatchWork(work: WorkInfo): Boolean {
        if (observedSpeciesBatchWorkId == null) {
            if (work.state.isFinished) return false
            observedSpeciesBatchWorkId = work.id
        }
        return observedSpeciesBatchWorkId == work.id
    }

    private fun adoptPublishBatchWork(work: WorkInfo): Boolean {
        if (observedPublishBatchWorkId == null) {
            if (work.state.isFinished) return false
            observedPublishBatchWorkId = work.id
        }
        return observedPublishBatchWorkId == work.id
    }

    private fun finishSpeciesReviewBatch(work: WorkInfo, status: ReviewBatchStatus?) {
        val completed = work.state == WorkInfo.State.SUCCEEDED && status?.state == "completed"
        val terminalStatus = status ?: ReviewBatchStatus(
            jobId = "",
            state = if (completed) "completed" else "failed",
            totalPhotos = 0,
            processedCount = 0,
            processedPhotoIds = emptyList(),
            currentPhotoNumber = 0,
            currentPhotoId = null,
            totalGroups = 0,
            currentGroup = 0,
            groupedCount = 0,
            individualCount = 0,
            warnings = emptyList(),
            error = work.outputData.getString(SpeciesReviewBatchWork.ProgressError)
                ?.takeIf(String::isNotBlank),
            items = emptyList(),
        )
        if (completed) {
            _state.update { current ->
                current.copy(
                    isBatchIdentifying = false,
                    batchProgress = terminalStatus,
                    isOffline = false,
                    error = null,
                    notice = buildSpeciesReviewBatchNotice(
                        status = terminalStatus,
                        species = current.species,
                    ),
                )
            }
            val batchPhotoIds = SpeciesReviewBatchWork.loadRequest(appContext)
                ?.groups
                .orEmpty()
                .flatten()
                .toSet()
            viewModelScope.launch {
                val speciesResult = runCatching { repository.loadSpecies() }.getOrNull()
                val reviewResult = runCatching { repository.loadReviewQueue() }.getOrNull()
                val updatedSpecies = speciesResult?.value
                val updatedReviewQueue = reviewResult?.value
                val suggestionCount = updatedReviewQueue
                    ?.filter { it.id in batchPhotoIds }
                    ?.mapNotNull { item ->
                        item.candidates.firstOrNull()?.let { candidate ->
                            candidate.taxonId?.toString()
                                ?: candidate.scientificName.ifBlank { candidate.commonName }.lowercase()
                        }
                    }
                    ?.distinct()
                    ?.size
                _state.update { current ->
                    val refreshedSpecies = updatedSpecies ?: current.species
                    val celebrationStatus = terminalStatus.copy(
                        items = updatedReviewQueue
                            ?.filter { it.id in batchPhotoIds }
                            ?.takeIf { it.isNotEmpty() }
                            ?: terminalStatus.items,
                    )
                    val celebration = buildReviewBatchCelebration(
                        status = celebrationStatus,
                        existingSpecies = refreshedSpecies,
                    )
                    current.copy(
                        species = refreshedSpecies,
                        reviewQueue = updatedReviewQueue ?: current.reviewQueue,
                        isOffline = speciesResult?.fromCache ?: reviewResult?.fromCache ?: current.isOffline,
                        badgesHydrated = if (updatedSpecies != null) false else current.badgesHydrated,
                        notice = if (celebration != null) null else buildSpeciesReviewBatchNotice(
                            status = terminalStatus,
                            species = refreshedSpecies,
                            suggestionCount = suggestionCount,
                        ),
                        celebration = celebration ?: current.celebration,
                    )
                }
                if (updatedReviewQueue == null) loadReviewQueue(force = true)
            }
        } else {
            _state.update { current ->
                current.copy(
                    isBatchIdentifying = false,
                    batchProgress = terminalStatus.copy(state = "failed"),
                    isReviewLoading = true,
                    error = terminalStatus.error
                        ?: "The species review batch could not complete. Refresh the review queue to see any IDs that were saved.",
                )
            }
            viewModelScope.launch {
                val reviewResult = runCatching { repository.loadReviewQueue() }.getOrNull()
                _state.update { current ->
                    current.copy(
                        reviewQueue = reviewResult?.value ?: current.reviewQueue,
                        isReviewLoading = false,
                        isOffline = reviewResult?.fromCache ?: current.isOffline,
                    )
                }
            }
        }
    }

    private fun buildSpeciesReviewBatchNotice(
        status: ReviewBatchStatus,
        species: List<SpeciesRecord>,
        suggestionCount: Int? = null,
    ): String = buildString {
        append("Species ID complete · ${status.processedCount} photo")
        if (status.processedCount != 1) append('s')
        append(" · ${status.totalGroups} request")
        if (status.totalGroups != 1) append('s')
        val counts = speciesTypeCounts(species)
        append(". Field Guide: ${counts.total} confirmed species")
        suggestionCount?.takeIf { it > 0 }?.let { count ->
            append(" · $count suggestion")
            if (count != 1) append('s')
            append(" ready")
        }
        if (status.warnings.isNotEmpty()) append(". ${status.warnings.first()}")
    }

    private fun badgeMetricProgress(badges: List<com.hikejournal.app.data.TrailBadge>, metric: BadgeMetric): String {
        val series = badges.filter { it.definition.metric == metric }
        val current = series.firstOrNull()?.current ?: 0.0
        val next = series.firstOrNull { !it.earned }
        fun format(value: Double): String = if (metric == BadgeMetric.TotalMiles || metric == BadgeMetric.LongestHike) {
            String.format(Locale.US, "%.1f", value)
        } else {
            value.toInt().toString()
        }
        return next?.let { "${format(current)}/${format(it.definition.target)}" } ?: format(current)
    }

    private fun buildHikeSaveNotice(
        hike: Hike,
        hikes: List<Hike>,
        species: List<SpeciesRecord>,
        quests: List<FieldQuest>,
    ): String {
        val badges = calculateTrailBadges(hikes, species, quests)
        val title = hike.title.trim().ifBlank { "Untitled hike" }
        return "\"$title\" saved. Trail progress: " +
            "${badgeMetricProgress(badges, BadgeMetric.HikeCount)} hikes · " +
            "${badgeMetricProgress(badges, BadgeMetric.TotalMiles)} lifetime miles · " +
            "${badgeMetricProgress(badges, BadgeMetric.LongestHike)} longest hike"
    }

    private fun observePublishBatchWork() {
        viewModelScope.launch {
            WorkManager.getInstance(appContext)
                .getWorkInfosForUniqueWorkFlow(PublishBatchWork.WorkName)
                .collect { workInfos ->
                    val work = workInfos.firstOrNull() ?: return@collect
                    if (!adoptPublishBatchWork(work)) return@collect
                    val status = if (work.state.isFinished) {
                        PublishBatchWork.statusFromData(work.outputData)
                            ?: PublishBatchWork.statusFromData(work.progress)
                    } else {
                        PublishBatchWork.statusFromData(work.progress)
                    }
                    when (work.state) {
                        WorkInfo.State.ENQUEUED, WorkInfo.State.RUNNING, WorkInfo.State.BLOCKED -> {
                            _state.update { current ->
                                current.copy(
                                    isBatchPublishing = true,
                                    publishBatchProgress = status ?: current.publishBatchProgress,
                                )
                            }
                        }
                        WorkInfo.State.SUCCEEDED, WorkInfo.State.FAILED, WorkInfo.State.CANCELLED -> {
                            if (handledPublishBatchWorkId == work.id) return@collect
                            handledPublishBatchWorkId = work.id
                            finishPublishBatch(work, status)
                        }
                        else -> Unit
                    }
                }
        }
    }

    private fun finishPublishBatch(work: WorkInfo, status: PublishBatchStatus?) {
        val completed = work.state == WorkInfo.State.SUCCEEDED && status?.state == "completed"
        val terminalStatus = status ?: PublishBatchStatus(
            jobId = "",
            state = if (completed) "completed" else "failed",
            totalGroups = 0,
            processedGroupCount = 0,
            postedGroupCount = 0,
            failedGroupCount = 0,
            partialGroupCount = 0,
            totalPhotos = 0,
            processedPhotoCount = 0,
            currentGroup = 0,
            currentGroupPhotoCount = 0,
            processedObservationIds = emptyList(),
            processedPhotoIds = emptyList(),
            errors = emptyList(),
            error = work.outputData.getString(PublishBatchWork.ProgressError)
                ?.takeIf(String::isNotBlank),
        )
        if (completed) {
            _state.update { current ->
                current.copy(
                    isBatchPublishing = false,
                    publishBatchProgress = terminalStatus,
                    isOffline = false,
                    error = null,
                    publishNotice = buildPublishBatchNotice(terminalStatus),
                )
            }
            loadPublishQueue(force = true)
        } else {
            _state.update { current ->
                current.copy(
                    isBatchPublishing = false,
                    publishBatchProgress = terminalStatus.copy(state = "failed"),
                    error = terminalStatus.error
                        ?: "The iNaturalist publish batch could not complete. Refresh the publishing queue to see any posts that were saved.",
                )
            }
        }
    }

    private fun buildPublishBatchNotice(status: PublishBatchStatus): String = buildString {
        append("iNaturalist publish complete · ${status.postedGroupCount} observation")
        if (status.postedGroupCount != 1) append('s')
        append(" · ${status.processedPhotoCount} photo")
        if (status.processedPhotoCount != 1) append('s')
        if (status.failedGroupCount > 0 || status.partialGroupCount > 0) {
            append(". ${status.failedGroupCount} could not be created and ${status.partialGroupCount} need photo attention")
        }
        status.errors.firstOrNull()?.let { append(". $it") }
    }

    private fun loadInitialLibrary() {
        viewModelScope.launch {
            val cachedHikes = runCatching { repository.loadCachedHikes() }.getOrNull()
            if (cachedHikes != null) {
                _state.update {
                    it.copy(
                        hikes = cachedHikes,
                        isLoading = false,
                        isOffline = true,
                        error = null,
                    )
                }
            }
            // Revalidate after the cached archive is on screen. Do not turn this background
            // refresh into a loading state; the existing archive remains useful meanwhile.
            refreshLibrary(initial = cachedHikes == null, showRefreshIndicator = false)
        }
    }

    private fun primeMapData() {
        viewModelScope.launch {
            runCatching { repository.loadCachedMapData() }
                .onSuccess { cached ->
                    if (!cached.available) return@onSuccess
                    _state.update { state ->
                        if (state.sightings.isNotEmpty() || state.mapRouteSegments.isNotEmpty()) {
                            state
                        } else {
                            state.copy(
                                sightings = cached.sightings,
                                mapRouteSegments = cached.routeSegments,
                            )
                        }
                    }
                }
        }
    }

    fun refreshLibrary(initial: Boolean = false, showRefreshIndicator: Boolean = !initial) {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    isLoading = initial && it.hikes.isEmpty(),
                    isRefreshing = showRefreshIndicator,
                    error = null,
                )
            }
            runCatching { repository.loadHikes() }
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            hikes = result.value,
                            isLoading = false,
                            isRefreshing = false,
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update {
                        it.copy(
                            isLoading = false,
                            isRefreshing = false,
                            error = error.userMessage(),
                        )
                    }
                }
        }
    }

    fun loadHikeLocations() {
        if (_state.value.hikeLocations.any { it.latitude != null && it.longitude != null }) return
        viewModelScope.launch {
            runCatching { repository.loadHikeLocations() }
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            hikeLocations = result.value,
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(error = error.userMessage()) }
                }
        }
    }

    private suspend fun refreshJournalAfterSync(hikeId: String) {
        runCatching { repository.loadHike(hikeId) }
            .onSuccess { result ->
                _state.update { state ->
                    if (state.journal?.id == hikeId) {
                        state.copy(
                            journal = result.value,
                            isOffline = result.fromCache,
                            resolvingSpeciesInfoPhotoId = state.resolvingSpeciesInfoPhotoId?.takeUnless { photoId ->
                                result.value.photos.any { photo ->
                                    photo.id == photoId && photo.species.any { it.isPrimary }
                                }
                            },
                        )
                    } else {
                        state
                    }
                }
            }
    }

    fun openHike(hikeId: String) {
        val current = _state.value
        if (current.openingHikeId == hikeId) return
        val summary = current.hikes.firstOrNull { it.id == hikeId }
        _state.update {
            it.copy(
                journal = summary ?: it.journal,
                openingHikeId = hikeId,
                error = null,
            )
        }
        viewModelScope.launch {
            val cached = repository.loadCachedHike(
                hikeId = hikeId,
                expectedPhotoCount = summary?.photoCount,
            )
            if (cached != null) {
                _state.update {
                    if (it.openingHikeId == hikeId || it.journal?.id == hikeId) {
                        it.copy(journal = cached, openingHikeId = null)
                    } else {
                        it
                    }
                }
            }
            runCatching {
                repository.loadHike(hikeId, expectedPhotoCount = summary?.photoCount) { progress ->
                    _state.update {
                        if (it.openingHikeId == hikeId || it.journal?.id == hikeId) {
                            it.copy(journal = mergeHikeLoadProgress(it.journal, progress))
                        } else {
                            it
                        }
                    }
                }
            }
                .onSuccess { result ->
                    _state.update {
                        if (it.openingHikeId == hikeId || it.journal?.id == hikeId) {
                            it.copy(
                                journal = result.value,
                                openingHikeId = null,
                                isOffline = result.fromCache,
                            )
                        } else {
                            it
                        }
                    }
                    if (!result.fromCache && result.value.weather == null && result.value.routeSegments.isNotEmpty()) {
                        enrichHikeWeather(hikeId)
                    }
                }
                .onFailure { error ->
                    _state.update {
                        if (it.openingHikeId == hikeId) {
                            it.copy(
                                journal = null,
                                openingHikeId = null,
                                error = error.userMessage(),
                            )
                        } else {
                            it
                        }
                    }
                }
        }
    }

    fun closeJournal() {
        _state.update { it.copy(journal = null, openingHikeId = null, error = null) }
        refreshLibrary()
    }

    fun enrichHikeWeather(hikeId: String, force: Boolean = false) {
        if (_state.value.weatherUpdateId == hikeId) return
        if (_state.value.isOffline) {
            _state.update { it.copy(notice = "Weather enrichment needs a connection.") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(weatherUpdateId = hikeId, notice = null) }
            runCatching { repository.enrichHikeWeather(hikeId, force) }
                .onSuccess { weather ->
                    _state.update { current ->
                        current.copy(
                            journal = current.journal?.let { hike ->
                                if (hike.id == hikeId) hike.copy(weather = weather) else hike
                            },
                            weatherUpdateId = null,
                            notice = "Historical conditions added from Open-Meteo.",
                        )
                    }
                }
                .onFailure { error ->
                    _state.update {
                        it.copy(weatherUpdateId = null, notice = error.userMessage())
                    }
                }
        }
    }

    fun loadSpecies(force: Boolean = false) {
        if (_state.value.species.isNotEmpty() && !force) return
        viewModelScope.launch {
            _state.update { it.copy(isSpeciesLoading = true, error = null) }
            runCatching { repository.loadSpecies() }
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            species = result.value,
                            isSpeciesLoading = false,
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(isSpeciesLoading = false, error = error.userMessage()) }
                }
        }
    }

    fun loadBadgeProgress(force: Boolean = false) {
        if (_state.value.badgesHydrated && !force) return
        viewModelScope.launch {
            _state.update { it.copy(isBadgeLoading = true, badgeNotice = null) }
            runCatching {
                repository.loadSpecies() to repository.loadSpeciesQuests()
            }.onSuccess { (species, quests) ->
                _state.update {
                    it.copy(
                        species = species.value,
                        speciesQuests = quests.value,
                        isBadgeLoading = false,
                        badgesHydrated = true,
                        badgeNotice = null,
                        isOffline = species.fromCache || quests.fromCache,
                    )
                }
            }.onFailure { error ->
                _state.update {
                    it.copy(
                        isBadgeLoading = false,
                        badgeNotice = "Showing saved medal progress. Refresh when connected.",
                    )
                }
            }
        }
    }

    fun loadSpeciesDiscovery(force: Boolean = false) {
        if (_state.value.discoveryAreas.isNotEmpty() && _state.value.speciesQuests.isNotEmpty() && !force) return
        viewModelScope.launch {
            _state.update { it.copy(isDiscoveryLoading = true, discoveryNotice = null) }
            runCatching {
                repository.loadDiscoveryAreas() to repository.loadSpeciesQuests()
            }.onSuccess { (areas, quests) ->
                _state.update {
                    it.copy(
                        discoveryAreas = areas.value,
                        speciesQuests = quests.value,
                        isDiscoveryLoading = false,
                        badgesHydrated = true,
                        isOffline = areas.fromCache || quests.fromCache,
                    )
                }
            }.onFailure { error ->
                _state.update {
                    it.copy(
                        isDiscoveryLoading = false,
                        discoveryNotice = error.userMessage(),
                    )
                }
            }
        }
    }

    fun loadNearbySpecies(
        areaId: String?,
        targetDate: String,
        radiusKm: Int,
        iconicTaxa: List<String>,
        latitude: Double? = null,
        longitude: Double? = null,
        limit: Int = 50,
    ) {
        viewModelScope.launch {
            _state.update { it.copy(isDiscoveryLoading = true, discoveryNotice = null) }
            runCatching {
                repository.loadNearbySpecies(
                    areaId = areaId,
                    targetDate = targetDate,
                    radiusKm = radiusKm,
                    iconicTaxa = iconicTaxa,
                    latitude = latitude,
                    longitude = longitude,
                    limit = limit,
                )
            }.onSuccess { result ->
                _state.update {
                    it.copy(
                        nearbySpecies = result.value,
                        isDiscoveryLoading = false,
                        isOffline = result.fromCache,
                    )
                }
            }.onFailure { error ->
                _state.update {
                    it.copy(
                        isDiscoveryLoading = false,
                        discoveryNotice = error.userMessage(),
                    )
                }
            }
        }
    }

    fun saveNearbyQuest(
        title: String,
        linkedHikeId: String?,
        focusTaxonIds: List<Long>,
        onSaved: (FieldQuest) -> Unit = {},
    ) {
        val nearby = _state.value.nearbySpecies ?: return
        if (nearby.areaId.isBlank()) {
            _state.update { it.copy(discoveryNotice = "Choose a saved trail before saving a Field Quest.") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(isSavingQuest = true, discoveryNotice = null) }
            runCatching {
                repository.createSpeciesQuest(
                    areaId = nearby.areaId,
                    targetDate = nearby.targetDate,
                    radiusKm = nearby.radiusKm,
                    iconicTaxon = nearby.iconicTaxon,
                    title = title,
                    linkedHikeId = linkedHikeId,
                    focusTaxonIds = focusTaxonIds,
                    resultLimit = nearby.resultLimit,
                )
            }.onSuccess { quest ->
                _state.update {
                    it.copy(
                        speciesQuests = listOf(quest) + it.speciesQuests.filterNot { saved -> saved.id == quest.id },
                        isSavingQuest = false,
                        discoveryNotice = "Field Quest saved for offline use.",
                    )
                }
                onSaved(quest)
            }.onFailure { error ->
                _state.update {
                    it.copy(isSavingQuest = false, discoveryNotice = error.userMessage())
                }
            }
        }
    }

    fun renameQuest(quest: FieldQuest, title: String) {
        val cleanTitle = title.trim()
        if (cleanTitle.isEmpty() || cleanTitle == quest.title) return
        if (_state.value.isOffline) {
            _state.update { it.copy(discoveryNotice = "Renaming a quest needs a connection.") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(isSavingQuest = true, discoveryNotice = null) }
            runCatching {
                repository.updateSpeciesQuest(questId = quest.id, title = cleanTitle)
            }.onSuccess { updated ->
                _state.update {
                    it.copy(
                        speciesQuests = it.speciesQuests.map { existing ->
                            if (existing.id == updated.id) updated else existing
                        },
                        isSavingQuest = false,
                        discoveryNotice = "Quest renamed.",
                    )
                }
            }.onFailure { error ->
                _state.update { it.copy(isSavingQuest = false, discoveryNotice = error.userMessage()) }
            }
        }
    }

    fun openQuestSightingsMap(quest: FieldQuest, taxon: DiscoveryTaxon) {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    questMapQuest = quest,
                    questMapNearby = null,
                    questMapTaxon = taxon,
                    questSightingsMap = null,
                    isQuestMapLoading = true,
                    questMapNotice = null,
                )
            }
            runCatching { repository.loadQuestSightings(quest.id, taxon.taxonId) }
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            questSightingsMap = result.value,
                            isQuestMapLoading = false,
                            questMapNotice = if (result.fromCache) {
                                "Showing the last saved sighting map. Refresh when connected."
                            } else {
                                null
                            },
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update {
                        it.copy(
                            isQuestMapLoading = false,
                            questMapNotice = error.userMessage(),
                        )
                    }
                }
        }
    }

    fun openNearbySightingsMap(nearby: NearbySpecies, taxon: DiscoveryTaxon) {
        val mapContext = nearby.asMapContext()
        viewModelScope.launch {
            _state.update {
                it.copy(
                    questMapQuest = mapContext,
                    questMapNearby = nearby,
                    questMapTaxon = taxon,
                    questSightingsMap = null,
                    isQuestMapLoading = true,
                    questMapNotice = null,
                )
            }
            runCatching { repository.loadNearbySightings(nearby, taxon.taxonId) }
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            questSightingsMap = result.value,
                            isQuestMapLoading = false,
                            questMapNotice = if (result.fromCache) {
                                "Showing the last saved sighting map. Refresh when connected."
                            } else {
                                null
                            },
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update {
                        it.copy(
                            isQuestMapLoading = false,
                            questMapNotice = error.userMessage(),
                        )
                    }
                }
        }
    }

    fun refreshQuestSightingsMap() {
        val quest = _state.value.questMapQuest ?: return
        val taxon = _state.value.questMapTaxon ?: return
        val nearby = _state.value.questMapNearby
        if (nearby != null) {
            openNearbySightingsMap(nearby, taxon)
        } else {
            openQuestSightingsMap(quest, taxon)
        }
    }

    fun closeQuestSightingsMap() {
        _state.update {
            it.copy(
                questMapQuest = null,
                questMapNearby = null,
                questMapTaxon = null,
                questSightingsMap = null,
                isQuestMapLoading = false,
                questMapNotice = null,
            )
        }
    }

    fun saveQuestFocus(quest: FieldQuest, focusTaxonIds: List<Long>) {
        viewModelScope.launch {
            val updated = repository.queueQuestFocus(quest, focusTaxonIds)
            _state.update {
                it.copy(
                    speciesQuests = it.speciesQuests.map { existing ->
                        if (existing.id == updated.id) updated else existing
                    },
                    discoveryNotice = "Focus finds saved${if (it.isOffline) " and queued for sync" else ""}.",
                )
            }
        }
    }

    fun archiveQuest(quest: FieldQuest) {
        if (_state.value.isOffline) {
            _state.update { it.copy(discoveryNotice = "Archiving a quest needs a connection.") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(isSavingQuest = true, discoveryNotice = null) }
            runCatching {
                repository.updateSpeciesQuest(
                    questId = quest.id,
                    status = if (quest.status == "archived") "active" else "archived",
                )
            }.onSuccess { updated ->
                _state.update {
                    it.copy(
                        speciesQuests = it.speciesQuests.map { existing ->
                            if (existing.id == updated.id) updated else existing
                        },
                        isSavingQuest = false,
                    )
                }
            }.onFailure { error ->
                _state.update {
                    it.copy(isSavingQuest = false, discoveryNotice = error.userMessage())
                }
            }
        }
    }

    fun deleteQuest(quest: FieldQuest) {
        if (_state.value.isOffline) {
            _state.update { it.copy(discoveryNotice = "Deleting a quest needs a connection.") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(isSavingQuest = true, discoveryNotice = null) }
            runCatching {
                repository.deleteSpeciesQuest(quest.id)
            }.onSuccess {
                _state.update {
                    it.copy(
                        speciesQuests = it.speciesQuests.filterNot { saved -> saved.id == quest.id },
                        isSavingQuest = false,
                        discoveryNotice = "Field Quest deleted. Your observations were not changed.",
                    )
                }
            }.onFailure { error ->
                _state.update {
                    it.copy(isSavingQuest = false, discoveryNotice = error.userMessage())
                }
            }
        }
    }

    fun openSpecies(key: String) {
        viewModelScope.launch {
            _state.update { it.copy(isSpeciesLoading = true, error = null) }
            runCatching { repository.loadSpeciesDetail(key) }
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            speciesDetail = result.value,
                            isSpeciesLoading = false,
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(isSpeciesLoading = false, error = error.userMessage()) }
                }
        }
    }

    fun closeSpecies() {
        _state.update { it.copy(speciesDetail = null, error = null) }
    }

    fun openEncounterHike(hikeId: String) {
        _state.update { it.copy(speciesDetail = null) }
        openHike(hikeId)
    }

    fun openEncounterPhoto(hikeId: String?, photoId: String, onLoaded: (Photo) -> Unit) {
        val targetHikeId = hikeId ?: "everyday"
        val summary = _state.value.hikes.firstOrNull { it.id == targetHikeId }
        viewModelScope.launch {
            _state.update { it.copy(openingHikeId = targetHikeId, error = null) }
            var openedFromCache = false
            val cached = repository.loadCachedHike(
                hikeId = targetHikeId,
                expectedPhotoCount = summary?.photoCount,
            )
            cached?.photos?.firstOrNull { it.id == photoId }?.let { photo ->
                openedFromCache = true
                _state.update {
                    it.copy(journal = cached, openingHikeId = null, isOffline = true)
                }
                onLoaded(photo)
            }
            runCatching { repository.loadHike(targetHikeId) }
                .onSuccess { result ->
                    val photo = result.value.photos.firstOrNull { it.id == photoId }
                    _state.update {
                        it.copy(
                            journal = result.value,
                            openingHikeId = null,
                            isOffline = result.fromCache,
                        )
                    }
                    if (!openedFromCache) {
                        if (photo != null) {
                            onLoaded(photo)
                        } else {
                            _state.update { it.copy(error = "That photo is no longer in this journal.") }
                        }
                    }
                }
                .onFailure { error ->
                    if (!openedFromCache) {
                        _state.update { it.copy(openingHikeId = null, error = error.userMessage()) }
                    }
                }
        }
    }

    fun loadHikeForMap(hikeId: String, onLoaded: (Hike) -> Unit) {
        viewModelScope.launch {
            runCatching { repository.loadHike(hikeId).value }
                .onSuccess(onLoaded)
                .onFailure { error ->
                    _state.update { it.copy(error = error.userMessage()) }
                }
        }
    }

    fun loadSightings(force: Boolean = false) {
        if ((mapDataValidated && !force) || _state.value.isMapLoading) return
        viewModelScope.launch {
            if (_state.value.sightings.isEmpty() && _state.value.mapRouteSegments.isEmpty()) {
                runCatching { repository.loadCachedMapData() }
                    .onSuccess { cached ->
                        if (cached.available) {
                            _state.update {
                                it.copy(
                                    sightings = cached.sightings,
                                    mapRouteSegments = cached.routeSegments,
                                )
                            }
                        }
                    }
            }
            _state.update { it.copy(isMapLoading = true, error = null) }
            runCatching {
                repository.loadSightings() to repository.loadMapRouteSegments()
            }.onSuccess { (sightings, routes) ->
                    mapDataValidated = !sightings.fromCache && !routes.fromCache
                    _state.update {
                        it.copy(
                            sightings = sightings.value,
                            mapRouteSegments = routes.value,
                            isMapLoading = false,
                            isOffline = sightings.fromCache || routes.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(isMapLoading = false, error = error.userMessage()) }
                }
        }
    }

    fun loadReviewQueue(force: Boolean = false) {
        reviewQueueRequested = true
        if (_state.value.reviewQueue.isNotEmpty() && !force) return
        viewModelScope.launch {
            _state.update { it.copy(isReviewLoading = true, error = null) }
            runCatching { repository.loadReviewQueue() }
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            reviewQueue = result.value,
                            isReviewLoading = false,
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(isReviewLoading = false, error = error.userMessage()) }
                }
        }
    }

    fun decideReview(item: ReviewItem, action: String, candidate: ReviewCandidate?) {
        viewModelScope.launch {
            _state.update { it.copy(decidingReviewId = item.id, error = null) }
            val speciesBaseline = if (action == "confirm" && candidate != null) {
                _state.value.species.takeIf(List<SpeciesRecord>::isNotEmpty)
                    ?: runCatching { repository.loadSpecies().value }.getOrNull()
            } else {
                null
            }
            runCatching {
                repository.decideReview(item, action, candidate)
                repository.loadReviewQueue()
            }.onSuccess { result ->
                updatePhotoState(item.id) { photo ->
                    when (action) {
                        "confirm" -> photo.copy(
                            processingStatus = "ready",
                            syncState = if (photo.syncState == "synced") "queued" else photo.syncState,
                            species = candidate?.let {
                                listOf(
                                    SpeciesLabel(
                                        commonName = it.commonName,
                                        scientificName = it.scientificName,
                                        status = "confirmed",
                                        isPrimary = true,
                                    ),
                                )
                            } ?: photo.species,
                        )
                        "reject" -> photo.copy(processingStatus = "in_review")
                        else -> photo
                    }
                }
                _state.update { state ->
                    val celebration = speciesBaseline?.let { existingSpecies ->
                        candidate?.let { confirmed ->
                            buildConfirmedSpeciesCelebration(
                                candidate = confirmed,
                                photo = item.photo,
                                observedOn = item.photo.takenAt ?: item.hikeDate,
                                existingSpecies = existingSpecies,
                            )
                        }
                    }
                    state.copy(
                        reviewQueue = result.value,
                        decidingReviewId = null,
                        resolvingSpeciesInfoPhotoId = item.id.takeIf { action == "confirm" },
                        isOffline = result.fromCache,
                        species = emptyList(),
                        sightings = emptyList(),
                        badgesHydrated = false,
                        celebration = celebration ?: state.celebration,
                    )
                }
            }.onFailure { error ->
                _state.update { it.copy(decidingReviewId = null, error = error.userMessage()) }
            }
        }
    }

    fun requestReviewRecommendation(item: ReviewItem) {
        if (_state.value.isOffline) {
            _state.update { it.copy(error = "iNaturalist recommendations need a connection.") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(identifyingReviewId = item.id, error = null) }
            runCatching { repository.requestReviewRecommendation(item.id) }
                .onSuccess { recommended ->
                    _state.update { state ->
                        state.copy(
                            reviewQueue = state.reviewQueue.map { existing ->
                                if (existing.id == recommended.id) recommended else existing
                            },
                            identifyingReviewId = null,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(identifyingReviewId = null, error = error.userMessage()) }
                }
        }
    }

    fun submitReviewBatch(groups: List<List<String>>) {
        if (_state.value.isOffline) {
            _state.update { it.copy(error = "Batch identification needs a connection.") }
            return
        }
        if (groups.isEmpty()) return
        val totalPhotos = groups.sumOf(List<String>::size)
        _state.update {
            it.copy(
                isBatchIdentifying = true,
                batchProgress = ReviewBatchStatus(
                    jobId = "",
                    state = "queued",
                    totalPhotos = totalPhotos,
                    processedCount = 0,
                    processedPhotoIds = emptyList(),
                    currentPhotoNumber = 0,
                    currentPhotoId = null,
                    totalGroups = groups.size,
                    currentGroup = 0,
                    groupedCount = 0,
                    individualCount = 0,
                    warnings = emptyList(),
                    error = null,
                    items = emptyList(),
                ),
                error = null,
            )
        }
        runCatching { SpeciesReviewBatchWork.enqueue(appContext, groups) }
            .onSuccess { workId ->
                observedSpeciesBatchWorkId = workId
                handledSpeciesBatchWorkId = null
            }
            .onFailure { error ->
                _state.update {
                    it.copy(
                        isBatchIdentifying = false,
                        batchProgress = null,
                        error = error.message ?: "HikeJournal could not start the species review batch.",
                    )
                }
            }
    }

    fun clearBatchProgress() {
        _state.update { it.copy(batchProgress = null) }
    }

    fun requestPhotoRecommendation(photo: Photo, onRecommended: (ReviewItem) -> Unit) {
        if (_state.value.isOffline) {
            _state.update { it.copy(error = "iNaturalist recommendations need a connection.") }
            return
        }
        if (photo.syncState != "synced" || photo.url.startsWith("file:")) {
            _state.update { it.copy(error = "This photo is still saving. Try iNaturalist once its upload finishes.") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(identifyingReviewId = photo.id, error = null) }
            runCatching { repository.requestReviewRecommendation(photo.id) }
                .onSuccess { recommended ->
                    updatePhotoState(photo.id) { recommended.photo }
                    _state.update { it.copy(identifyingReviewId = null) }
                    onRecommended(recommended)
                }
                .onFailure { error ->
                    _state.update { it.copy(identifyingReviewId = null, error = error.userMessage()) }
                }
        }
    }

    fun connectInat() {
        if (_state.value.isOffline) {
            _state.update { it.copy(error = "Connecting iNaturalist needs a connection.") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(error = null) }
            runCatching { repository.getInatAuthorizationUrl() }
                .onSuccess { url -> _state.update { it.copy(inatAuthorizationUrl = url) } }
                .onFailure { error -> _state.update { it.copy(error = error.userMessage()) } }
        }
    }

    fun consumeInatAuthorizationUrl() {
        _state.update { it.copy(inatAuthorizationUrl = null) }
    }

    fun completeInatConnection(connected: Boolean) {
        if (connected) {
            _state.update { it.copy(error = null, publishQueue = it.publishQueue.copy(connected = true)) }
            loadReviewQueue(force = true)
            loadPublishQueue(force = true)
        } else {
            _state.update { it.copy(error = "iNaturalist authorization did not complete. Please try again.") }
        }
    }

    fun loadPublishQueue(force: Boolean = false) {
        if (_state.value.publishQueue.items.isNotEmpty() && !force) return
        viewModelScope.launch {
            _state.update { it.copy(isPublishLoading = true, error = null) }
            runCatching { repository.loadPublishQueue() }
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            publishQueue = result.value,
                            isPublishLoading = false,
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(isPublishLoading = false, error = error.userMessage()) }
                }
        }
    }

    fun publishObservation(item: PublishItem, options: PublishOptions) {
        if (_state.value.isOffline) {
            _state.update { it.copy(error = "Publishing needs a connection to iNaturalist.") }
            return
        }
        if (!_state.value.publishQueue.connected) {
            connectInat()
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(publishingId = item.id, publishNotice = null, error = null) }
            runCatching {
                val published = repository.publishObservation(item, options)
                published to repository.loadPublishQueue()
            }.onSuccess { (published, queueResult) ->
                _state.update {
                    it.copy(
                        publishQueue = queueResult.value,
                        publishingId = null,
                        isOffline = queueResult.fromCache,
                        publishNotice = if (published.state == "needs_attention") {
                            "Observation created; its photo still needs attention on iNaturalist."
                        } else {
                            "Published ${published.commonName} to iNaturalist."
                        },
                        species = emptyList(),
                        sightings = emptyList(),
                    )
                }
            }.onFailure { error ->
                _state.update { it.copy(publishingId = null, error = error.userMessage()) }
            }
        }
    }

    fun submitPublishBatch(
        groups: List<List<String>>,
        options: PublishOptions,
    ) {
        if (_state.value.isOffline) {
            _state.update { it.copy(error = "Publishing needs a connection to iNaturalist.") }
            return
        }
        if (!_state.value.publishQueue.connected) {
            connectInat()
            return
        }
        if (groups.isEmpty()) return
        _state.update {
            it.copy(
                isBatchPublishing = true,
                publishBatchProgress = PublishBatchWork.emptyStatus(
                    PublishBatchRequest("", groups, options),
                ),
                publishNotice = null,
                error = null,
            )
        }
        runCatching { PublishBatchWork.enqueue(appContext, groups, options) }
            .onSuccess { workId ->
                observedPublishBatchWorkId = workId
                handledPublishBatchWorkId = null
            }
            .onFailure { error ->
                _state.update {
                    it.copy(
                        isBatchPublishing = false,
                        publishBatchProgress = null,
                        error = error.message ?: "HikeJournal could not start the iNaturalist publish batch.",
                    )
                }
            }
    }

    fun clearPublishBatchProgress() {
        _state.update { it.copy(publishBatchProgress = null) }
    }

    fun clearPublishNotice() {
        _state.update { it.copy(publishNotice = null) }
    }

    fun startTracking() {
        loadHikeLocations()
        viewModelScope.launch {
            _state.update { it.copy(error = null, trackingMarks = emptyList()) }
            runCatching {
                trackingRepository.start()
            }.onSuccess {
                _state.update { state ->
                    state.copy(trackingOpenRequestToken = state.trackingOpenRequestToken + 1)
                }
            }.onFailure { error ->
                _state.update { it.copy(error = error.userMessage()) }
            }
        }
    }

    fun addFieldMark(markType: String, note: String = "") {
        val tracking = _state.value.tracking ?: return
        val point = tracking.routeSegments.lastOrNull { it.isNotEmpty() }?.lastOrNull()
        if (point == null) {
            _state.update { it.copy(error = "Wait for the first GPS fix before adding a Field Mark.") }
            return
        }
        val mark = FieldMark(
            id = UUID.randomUUID().toString(),
            hikeId = tracking.hikeId,
            recordingSessionId = tracking.sessionId,
            markedAt = Instant.now().toString(),
            latitude = point.latitude,
            longitude = point.longitude,
            accuracyMeters = tracking.lastAccuracyMeters?.toDouble(),
            markType = markType,
            note = note.trim(),
            syncState = "queued",
        )
        viewModelScope.launch {
            runCatching { repository.createFieldMark(mark) }
                .onSuccess { saved ->
                    _state.update { current ->
                        current.copy(
                            trackingMarks = (current.trackingMarks.filterNot { it.id == saved.id } + saved)
                                .sortedBy(FieldMark::markedAt),
                            notice = "${fieldMarkLabel(saved.markType)} marked at your current position.",
                            error = null,
                        )
                    }
                }
                .onFailure { error -> _state.update { it.copy(error = error.userMessage()) } }
        }
    }

    fun updateObservationNaturalHistory(
        photo: Photo,
        observationId: String,
        confidence: String,
        phenophases: List<String>,
    ) {
        viewModelScope.launch {
            runCatching {
                repository.updateObservationNaturalHistory(
                    observationId = observationId,
                    hikeId = photo.hikeId,
                    confidence = confidence,
                    phenophases = phenophases,
                )
            }.onSuccess {
                _state.update { current ->
                    val updatedJournal = current.journal?.copy(
                        photos = current.journal.photos.map { currentPhoto ->
                            if (currentPhoto.id != photo.id) currentPhoto else currentPhoto.copy(
                                syncState = if (currentPhoto.syncState == "synced") "queued" else currentPhoto.syncState,
                                species = currentPhoto.species.map { label ->
                                    if (label.observationId == observationId) {
                                        label.copy(
                                            confidence = confidence,
                                            provenance = "user",
                                            phenophases = phenophases,
                                        )
                                    } else label
                                },
                            )
                        },
                    )
                    current.copy(
                        journal = updatedJournal,
                        notice = "Natural-history details saved on this phone.",
                        error = null,
                    )
                }
            }.onFailure { error -> _state.update { it.copy(error = error.userMessage()) } }
        }
    }

    fun openPlaceProfile(locationId: String) {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    isLongitudinalLoading = true,
                    longitudinalDestination = LongitudinalDestination.PlaceProfile,
                    placeProfile = null,
                    fieldBriefing = null,
                    error = null,
                )
            }
            runCatching { repository.loadPlaceProfile(locationId) }
                .onSuccess { result ->
                    _state.update { current ->
                        if (current.longitudinalDestination != LongitudinalDestination.PlaceProfile) current else current.copy(
                            placeProfile = result.value,
                            isLongitudinalLoading = false,
                            longitudinalDestination = null,
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { current ->
                        if (current.longitudinalDestination != LongitudinalDestination.PlaceProfile) current else current.copy(
                            isLongitudinalLoading = false,
                            longitudinalDestination = null,
                            error = error.userMessage(),
                        )
                    }
                }
        }
    }

    fun closePlaceProfile() {
        _state.update {
            it.copy(
                placeProfile = null,
                fieldBriefing = null,
                isLongitudinalLoading = if (it.longitudinalDestination == LongitudinalDestination.PlaceProfile) false else it.isLongitudinalLoading,
                longitudinalDestination = it.longitudinalDestination
                    .takeUnless { target -> target == LongitudinalDestination.PlaceProfile },
            )
        }
    }

    fun openFieldBriefing(locationId: String) {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    isLongitudinalLoading = true,
                    longitudinalDestination = LongitudinalDestination.FieldBriefing,
                    fieldBriefing = null,
                    error = null,
                )
            }
            runCatching { repository.loadFieldBriefing(locationId) }
                .onSuccess { result ->
                    _state.update { current ->
                        if (current.longitudinalDestination != LongitudinalDestination.FieldBriefing) current else current.copy(
                            fieldBriefing = result.value,
                            isLongitudinalLoading = false,
                            longitudinalDestination = null,
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { current ->
                        if (current.longitudinalDestination != LongitudinalDestination.FieldBriefing) current else current.copy(
                            isLongitudinalLoading = false,
                            longitudinalDestination = null,
                            error = error.userMessage(),
                        )
                    }
                }
        }
    }

    fun closeFieldBriefing() {
        _state.update {
            it.copy(
                fieldBriefing = null,
                isLongitudinalLoading = if (it.longitudinalDestination == LongitudinalDestination.FieldBriefing) false else it.isLongitudinalLoading,
                longitudinalDestination = it.longitudinalDestination
                    .takeUnless { target -> target == LongitudinalDestination.FieldBriefing },
            )
        }
    }

    fun openBriefingSightingsMap(item: BriefingItem) {
        val briefing = _state.value.fieldBriefing ?: return
        val taxonId = item.taxonId ?: return
        val nearby = NearbySpecies(
            areaId = briefing.areaId,
            areaName = briefing.areaName,
            latitude = briefing.latitude,
            longitude = briefing.longitude,
            radiusKm = briefing.radiusKm,
            targetDate = briefing.targetDate,
            periodLabel = briefing.periodLabel,
            iconicTaxon = null,
            resultLimit = 50,
            dataDensity = "",
            dataDensityMessage = "",
            sourceGuidance = "Reporting frequency is not a probability of encounter.",
            fromCache = false,
            progress = DiscoveryProgress(0, 0, 0),
            taxa = emptyList(),
        )
        val taxon = item.toDiscoveryTaxon().copy(taxonId = taxonId)
        openNearbySightingsMap(nearby, taxon)
    }

    fun openHikeComparison(hikeId: String, otherHikeId: String) {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    isLongitudinalLoading = true,
                    longitudinalDestination = LongitudinalDestination.Comparison,
                    hikeComparison = null,
                    error = null,
                )
            }
            runCatching { repository.loadHikeComparison(hikeId, otherHikeId) }
                .onSuccess { result ->
                    _state.update { current ->
                        if (current.longitudinalDestination != LongitudinalDestination.Comparison) current else current.copy(
                            hikeComparison = result.value,
                            isLongitudinalLoading = false,
                            longitudinalDestination = null,
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { current ->
                        if (current.longitudinalDestination != LongitudinalDestination.Comparison) current else current.copy(
                            isLongitudinalLoading = false,
                            longitudinalDestination = null,
                            error = error.userMessage(),
                        )
                    }
                }
        }
    }

    fun closeHikeComparison() {
        _state.update {
            it.copy(
                hikeComparison = null,
                isLongitudinalLoading = if (it.longitudinalDestination == LongitudinalDestination.Comparison) false else it.isLongitudinalLoading,
                longitudinalDestination = it.longitudinalDestination
                    .takeUnless { target -> target == LongitudinalDestination.Comparison },
            )
        }
    }

    fun pauseTracking() {
        runCatching { HikeTrackingService.pause(appContext) }
            .onFailure { error -> _state.update { it.copy(error = error.userMessage()) } }
    }

    fun resumeTracking() {
        runCatching { HikeTrackingService.resume(appContext) }
            .onFailure { error -> _state.update { it.copy(error = error.userMessage()) } }
    }

    fun openTrackingFromNotification(confirmEnd: Boolean) {
        _state.update { state ->
            state.copy(
                trackingOpenRequestToken = state.trackingOpenRequestToken + 1,
                trackingEndRequestToken = if (confirmEnd) {
                    state.trackingEndRequestToken + 1
                } else {
                    state.trackingEndRequestToken
                },
            )
        }
    }

    fun consumeTrackingOpenRequest(token: Long) {
        _state.update { state ->
            if (state.trackingOpenRequestToken == token) {
                state.copy(trackingOpenRequestToken = 0L)
            } else {
                state
            }
        }
    }

    fun consumeTrackingEndRequest(token: Long) {
        _state.update { state ->
            if (state.trackingEndRequestToken == token) {
                state.copy(trackingEndRequestToken = 0L)
            } else {
                state
            }
        }
    }

    fun finishTracking(onFinished: (Hike, HikeLocationSuggestion?) -> Unit) {
        viewModelScope.launch {
            _state.update { it.copy(isFinalizingTracking = true, error = null) }
            runCatching {
                val paused = trackingRepository.current()
                    ?: error("There is no hike recording to finish.")
                check(paused.status == TrackingStatus.PAUSED) { "Pause the hike before ending it." }
                val finalizing = trackingRepository.markFinalizing()
                val tcxFile = if (finalizing.pointCount >= 2) {
                    trackingRepository.generateTcx(finalizing.sessionId)
                } else {
                    null
                }
                val allRouteSegments = finalizing.routeSegments.map { segment ->
                    segment.map { point -> RoutePoint(point.latitude, point.longitude) }
                }
                val routeSegments = allRouteSegments
                    .filter { it.size >= 2 }
                val cachedLocations = _state.value.hikeLocations
                val locations = if (cachedLocations.any { it.latitude != null && it.longitude != null }) {
                    cachedLocations
                } else {
                    runCatching { repository.loadHikeLocations() }
                        .getOrNull()
                        ?.also { result ->
                            _state.update { it.copy(hikeLocations = result.value, isOffline = result.fromCache) }
                        }
                        ?.value
                        .orEmpty()
                }
                val locationSuggestion = suggestHikeLocation(allRouteSegments, locations)
                val durationSeconds = ((finalizing.activeElapsedMs + 500L) / 1_000L).coerceAtLeast(0L)
                val distanceMiles = (finalizing.distanceMeters / 1_609.344).coerceAtLeast(0.0)
                val startedAt = Instant.ofEpochMilli(finalizing.startedAtEpochMs).toString()
                val route = tcxFile?.let { file ->
                    RecordedRouteUpload(
                        file = file,
                        startedAt = startedAt,
                        durationSeconds = durationSeconds,
                        distanceMiles = distanceMiles,
                        pointCount = finalizing.pointCount,
                        routeSegments = routeSegments,
                    )
                }
                val created = repository.createRecordedHike(
                    hikeId = finalizing.hikeId,
                    draft = HikeDraft(
                        title = "Untitled hike",
                        hikeDate = finalizing.hikeDate,
                        distanceMiles = distanceMiles,
                        locationName = "",
                        notes = "",
                    ),
                    route = route,
                ).copy(
                    durationSeconds = durationSeconds,
                    routeStartedAt = startedAt,
                    routeSegments = routeSegments,
                )
                trackingRepository.markFinished(tcxFile?.absolutePath)
                if (tcxFile == null) trackingRepository.clearFinished(finalizing.hikeId)
                created to locationSuggestion
            }.onSuccess { (created, locationSuggestion) ->
                _state.update { state ->
                    val updatedHikes = listOf(created) + state.hikes.filterNot { it.id == created.id }
                    val celebration = buildHikeMilestoneCelebration(
                        previousHikes = state.hikes,
                        updatedHikes = updatedHikes,
                        savedHike = created,
                    )
                    state.copy(
                        hikes = updatedHikes,
                        isFinalizingTracking = false,
                        notice = if (celebration != null) {
                            null
                        } else if (created.routeSegments.isEmpty()) {
                            "Hike saved. GPS did not collect enough points to draw a route."
                        } else {
                            "Hike saved on this phone. Give it a name and location."
                        },
                        celebration = celebration ?: state.celebration,
                    )
                }
                loadHikeLocations()
                onFinished(created, locationSuggestion)
            }.onFailure { error ->
                runCatching { trackingRepository.failFinalization(error.userMessage()) }
                _state.update {
                    it.copy(
                        isFinalizingTracking = false,
                        error = "The hike is still paused and safe on this phone. ${error.userMessage()}",
                    )
                }
            }
        }
    }

    fun discardTracking(onDiscarded: () -> Unit) {
        viewModelScope.launch {
            _state.update { it.copy(isFinalizingTracking = true, error = null) }
            val hikeId = _state.value.tracking?.hikeId
            runCatching {
                trackingRepository.discard()
                if (hikeId != null) repository.discardRecordingFieldMarks(hikeId)
            }
                .onSuccess {
                    _state.update {
                        it.copy(
                            tracking = null,
                            isFinalizingTracking = false,
                            notice = "Hike discarded.",
                        )
                    }
                    onDiscarded()
                }
                .onFailure { error ->
                    _state.update {
                        it.copy(
                            isFinalizingTracking = false,
                            error = "The hike is still paused. ${error.userMessage()}",
                        )
                    }
                }
        }
    }

    fun saveHike(draft: HikeDraft, routeUri: Uri?, editingId: String?, onSaved: () -> Unit) {
        viewModelScope.launch {
            _state.update { it.copy(isRefreshing = true, error = null) }
            runCatching {
                if (editingId == null) {
                    repository.createHike(draft).also { created ->
                        routeUri?.let { repository.uploadRoute(created.id, it) }
                    }
                }
                else {
                    repository.updateHike(editingId, draft)
                    null
                }
            }.onSuccess { created ->
                val savedId = created?.id ?: editingId.orEmpty()
                _state.update { state ->
                    val previous = state.journal?.takeIf { it.id == savedId }
                        ?: state.hikes.firstOrNull { it.id == savedId }
                    val saved = created ?: previous?.copy(
                        title = draft.title,
                        hikeDate = draft.hikeDate,
                        distanceMiles = draft.distanceMiles,
                        locationName = draft.locationName,
                        notes = draft.notes,
                        syncState = "queued",
                    )
                    val updatedHikes = saved?.let { hike ->
                        listOf(hike) + state.hikes.filterNot { it.id == hike.id }
                    } ?: state.hikes
                    val celebration = saved?.let { hike ->
                        buildHikeMilestoneCelebration(
                            previousHikes = state.hikes,
                            updatedHikes = updatedHikes,
                            savedHike = hike,
                        )
                    }
                    state.copy(
                        hikes = updatedHikes,
                        journal = saved?.let { hike ->
                            if (state.journal?.id == hike.id) hike else state.journal
                        } ?: state.journal,
                        isRefreshing = false,
                        notice = if (celebration != null) {
                            null
                        } else {
                            saved?.let { hike ->
                                buildHikeSaveNotice(hike, updatedHikes, state.species, state.speciesQuests)
                            } ?: state.notice
                        },
                        celebration = celebration ?: state.celebration,
                    )
                }
                onSaved()
                if (editingId != null) openHike(savedId)
            }.onFailure { error ->
                _state.update { it.copy(isRefreshing = false, error = error.userMessage()) }
            }
        }
    }

    fun setArchived(hike: Hike) {
        viewModelScope.launch {
            runCatching { repository.setArchived(hike.id, !hike.isArchived) }
                .onSuccess {
                    if (_state.value.journal?.id == hike.id) openHike(hike.id)
                    refreshLibrary()
                }
                .onFailure { error -> _state.update { it.copy(error = error.userMessage()) } }
        }
    }

    fun deleteHike(hike: Hike, onDeleted: () -> Unit) {
        viewModelScope.launch {
            _state.update { it.copy(deletingHikeId = hike.id, error = null, notice = null) }
            val remoteDeletionAllowed = _state.value.syncStatus.connected
            runCatching {
                repository.deleteHike(
                    hikeId = hike.id,
                    remoteDeletionAllowed = remoteDeletionAllowed,
                )
            }
                .onSuccess { deletionResult: HikeDeletionResult ->
                    _state.update { state ->
                        val deletedHikeIds = setOf(hike.id)
                        val publishItems = state.publishQueue.items.filterNot { it.hikeId == hike.id }
                        state.copy(
                            hikes = state.hikes.filterNot { it.id == hike.id },
                            journal = state.journal?.takeUnless { it.id == hike.id },
                            openingHikeId = state.openingHikeId?.takeUnless { it == hike.id },
                            species = state.species.mapNotNull { it.withoutHikes(deletedHikeIds) },
                            speciesDetail = null,
                            nearbySpecies = null,
                            speciesQuests = state.speciesQuests.map { quest ->
                                if (quest.linkedHikeId == hike.id) quest.copy(linkedHikeId = null) else quest
                            },
                            questMapQuest = null,
                            questMapNearby = null,
                            questMapTaxon = null,
                            questSightingsMap = null,
                            sightings = state.sightings.filterNot { it.hikeId == hike.id },
                            reviewQueue = state.reviewQueue.filterNot { it.hikeId == hike.id },
                            publishQueue = PublishQueue(
                                connected = state.publishQueue.connected,
                                readyCount = publishItems.count { it.state == "ready" },
                                needsAttentionCount = publishItems.count { it.state == "needs_attention" },
                                postedCount = publishItems.count { it.state == "posted" },
                                items = publishItems,
                            ),
                            badgesHydrated = false,
                            deletingHikeId = null,
                            error = deletionResult.warning,
                            notice = deletionResult.notice,
                        )
                    }
                    onDeleted()
                }
                .onFailure { error ->
                    _state.update { it.copy(deletingHikeId = null, error = error.userMessage(), notice = null) }
                }
        }
    }

    fun uploadPhotos(
        hikeId: String,
        uris: List<Uri>,
        caption: String,
        queueForReview: Boolean,
        prioritizeForIdentification: Boolean = false,
        onUploaded: (Photo) -> Unit = {},
    ) {
        if (uris.isEmpty()) return
        viewModelScope.launch {
            _state.update { it.copy(uploadCurrent = 0, uploadTotal = uris.size, error = null) }
            for ((index, uri) in uris.withIndex()) {
                val result = runCatching {
                    repository.uploadPhoto(
                        hikeId,
                        uri,
                        caption,
                        queueForReview,
                        scheduleSync = index == 0,
                    )
                }
                if (result.isFailure) {
                    repository.scheduleSync()
                    _state.update {
                        it.copy(
                            uploadCurrent = 0,
                            uploadTotal = 0,
                            error = result.exceptionOrNull().userMessage(),
                        )
                    }
                    return@launch
                }
                val savedPhoto = result.getOrThrow()
                if (prioritizeForIdentification && index == 0 && !savedPhoto.contentType.startsWith("video/")) {
                    _state.update { it.copy(prioritizingPhotoId = savedPhoto.id) }
                }
                _state.update { state ->
                    val journal = state.journal?.takeIf { it.id == hikeId }
                    state.copy(
                        journal = journal?.copy(
                            photos = journal.photos.filterNot { it.id == savedPhoto.id } + savedPhoto,
                            photoCount = journal.photos.count { it.id != savedPhoto.id } + 1,
                            coverUrl = journal.coverUrl.ifBlank { savedPhoto.url },
                        ) ?: state.journal,
                        hikes = state.hikes.map { hike ->
                            if (hike.id == hikeId) {
                                hike.copy(
                                    photoCount = hike.photoCount + 1,
                                    coverUrl = hike.coverUrl.ifBlank { savedPhoto.url },
                                )
                            } else {
                                hike
                            }
                        },
                        uploadCurrent = index + 1,
                    )
                }
                onUploaded(savedPhoto)
            }
            repository.scheduleSync()
            _state.update { it.copy(uploadCurrent = 0, uploadTotal = 0) }
            if (prioritizeForIdentification && _state.value.prioritizingPhotoId != null) {
                runCatching { repository.syncPhotoNow(_state.value.prioritizingPhotoId ?: return@launch) }
                    .onSuccess { refreshJournalAfterSync(hikeId) }
                    .onFailure { error -> _state.update { it.copy(error = error.userMessage()) } }
                _state.update { it.copy(prioritizingPhotoId = null) }
            } else {
                openHike(hikeId)
            }
        }
    }

    fun queuePhotosForSpeciesReview(photos: List<Photo>) {
        val eligible = photos
            .filterNot { it.contentType.startsWith("video/", ignoreCase = true) }
            .distinctBy { it.id }
        if (eligible.isEmpty()) return
        viewModelScope.launch {
            _state.update { it.copy(reviewUpdateId = "batch", error = null, notice = null) }
            runCatching {
                eligible.forEach { photo ->
                    val hikeId = photo.hikeId ?: _state.value.journal?.id ?: "everyday"
                    repository.setSpeciesReview(photo.id, hikeId, queued = true)
                }
            }.onSuccess {
                val selectedIds = eligible.mapTo(hashSetOf()) { it.id }
                _state.update { state ->
                    state.copy(
                        journal = state.journal?.copy(
                            photos = state.journal.photos.map { photo ->
                                if (photo.id in selectedIds) {
                                    photo.copy(
                                        processingStatus = "in_review",
                                        syncState = if (photo.syncState == "synced") "queued" else photo.syncState,
                                    )
                                } else {
                                    photo
                                }
                            },
                        ),
                        reviewQueue = emptyList(),
                        reviewUpdateId = null,
                        notice = "Added ${eligible.size} photo${if (eligible.size == 1) "" else "s"} to species review.",
                    )
                }
            }.onFailure { error ->
                _state.update { it.copy(reviewUpdateId = null, error = error.userMessage()) }
            }
        }
    }

    suspend fun inspectMediaLocations(uris: List<Uri>): MediaLocationSummary =
        repository.inspectMediaLocations(uris)

    fun updateCaption(photo: Photo, caption: String) {
        val hikeId = _state.value.journal
            ?.takeIf { journal -> journal.photos.any { it.id == photo.id } }
            ?.id
            ?: photo.hikeId
            ?: "everyday"
        viewModelScope.launch {
            runCatching { repository.updateCaption(photo.id, hikeId, caption) }
                .onSuccess {
                    updatePhotoState(photo.id) { existing ->
                        existing.copy(
                            caption = caption.trim(),
                            syncState = if (existing.syncState == "synced") "queued" else existing.syncState,
                        )
                    }
                }
                .onFailure { error -> _state.update { it.copy(error = error.userMessage()) } }
        }
    }

    fun setSpeciesReview(photo: Photo, queued: Boolean) {
        val hikeId = _state.value.journal
            ?.takeIf { journal -> journal.photos.any { it.id == photo.id } }
            ?.id
            ?: photo.hikeId
            ?: "everyday"
        viewModelScope.launch {
            _state.update { it.copy(reviewUpdateId = photo.id, error = null) }
            runCatching { repository.setSpeciesReview(photo.id, hikeId, queued) }
                .onSuccess {
                    updatePhotoState(photo.id) { existing ->
                        existing.copy(
                            processingStatus = if (queued) "in_review" else "ready",
                            syncState = if (existing.syncState == "synced") "queued" else existing.syncState,
                        )
                    }
                    _state.update { it.copy(reviewQueue = emptyList(), reviewUpdateId = null) }
                }
                .onFailure { error ->
                    _state.update { it.copy(reviewUpdateId = null, error = error.userMessage()) }
                }
        }
    }

    fun assignKnownSpecies(photo: Photo, species: SpeciesRecord, onAssigned: () -> Unit) {
        val hikeId = _state.value.journal
            ?.takeIf { journal -> journal.photos.any { it.id == photo.id } }
            ?.id
            ?: photo.hikeId
            ?: "everyday"
        viewModelScope.launch {
            _state.update { it.copy(speciesAssignmentId = photo.id, error = null, notice = null) }
            runCatching { repository.assignKnownSpecies(photo.id, hikeId, species) }
                .onSuccess {
                    val label = SpeciesLabel(
                        commonName = species.commonName,
                        scientificName = species.scientificName,
                        status = "confirmed",
                        isPrimary = true,
                        taxonId = species.taxonId,
                        wikipediaUrl = species.wikipediaUrl,
                        wikipediaSummary = species.wikipediaSummary,
                    )
                    updatePhotoState(photo.id) { existing ->
                        existing.copy(
                            processingStatus = "ready",
                            syncState = if (existing.syncState == "synced") "queued" else existing.syncState,
                            species = listOf(label) + existing.species.filterNot { it.isPrimary },
                        )
                    }
                    _state.update { state ->
                        val celebration = buildKnownSpeciesRediscoveryCelebration(species, photo)
                        state.copy(
                            reviewQueue = state.reviewQueue.filterNot { it.photo.id == photo.id },
                            speciesAssignmentId = null,
                            badgesHydrated = false,
                            notice = if (celebration != null) {
                                null
                            } else {
                                "Assigned ${species.commonName.ifBlank { species.scientificName }}. " +
                                    if (state.isOffline) "Saved for sync." else "Ready to publish."
                            },
                            celebration = celebration ?: state.celebration,
                        )
                    }
                    onAssigned()
                }
                .onFailure { error ->
                    _state.update { it.copy(speciesAssignmentId = null, error = error.userMessage()) }
                }
        }
    }

    fun setHikeCover(photo: Photo, selected: Boolean) {
        val journal = _state.value.journal ?: return
        if (journal.isStandalone || journal.photos.none { it.id == photo.id }) return
        val coverPhotoId = photo.id.takeIf { selected }
        val fallbackCover = journal.photos.maxByOrNull {
            "${it.takenAt.orEmpty()}|${it.createdAt.orEmpty()}"
        }?.url.orEmpty()
        val coverUrl = if (selected) photo.url else fallbackCover
        val previousCoverPhotoId = journal.coverPhotoId
        val previousCoverUrl = journal.coverUrl
        val previousArchiveCover = _state.value.hikes.firstOrNull { it.id == journal.id }
        // Reflect the durable local intent immediately. Queueing and remote sync happen in the
        // background; if local persistence fails, the guarded failure path restores this state.
        _state.update { state ->
            state.copy(
                journal = state.journal?.takeIf { it.id == journal.id }?.copy(
                    coverPhotoId = coverPhotoId,
                    coverUrl = coverUrl,
                    syncState = if (journal.syncState == "synced") "queued" else journal.syncState,
                ) ?: state.journal,
                hikes = state.hikes.map { hike ->
                    if (hike.id == journal.id) {
                        hike.copy(
                            coverPhotoId = coverPhotoId,
                            coverUrl = coverUrl,
                            syncState = if (hike.syncState == "synced") "queued" else hike.syncState,
                        )
                    } else {
                        hike
                    }
                },
                coverUpdateId = photo.id,
                error = null,
            )
        }
        viewModelScope.launch {
            runCatching { repository.setHikeCover(journal.id, coverPhotoId, coverUrl) }
                .onSuccess {
                    _state.update { state ->
                        if (state.coverUpdateId == photo.id) state.copy(coverUpdateId = null) else state
                    }
                }
                .onFailure { error ->
                    _state.update { state ->
                        if (state.coverUpdateId != photo.id) return@update state
                        state.copy(
                            journal = state.journal?.takeIf { it.id == journal.id }?.copy(
                                coverPhotoId = previousCoverPhotoId,
                                coverUrl = previousCoverUrl,
                                syncState = journal.syncState,
                            ) ?: state.journal,
                            hikes = state.hikes.map { hike ->
                                if (hike.id == journal.id && previousArchiveCover != null) {
                                    hike.copy(
                                        coverPhotoId = previousArchiveCover.coverPhotoId,
                                        coverUrl = previousArchiveCover.coverUrl,
                                        syncState = previousArchiveCover.syncState,
                                    )
                                } else {
                                    hike
                                }
                            },
                            coverUpdateId = null,
                            error = error.userMessage(),
                        )
                    }
                }
        }
    }

    fun deletePhoto(photo: Photo) {
        val hikeId = _state.value.journal
            ?.takeIf { journal -> journal.photos.any { it.id == photo.id } }
            ?.id
            ?: photo.hikeId
            ?: "everyday"
        viewModelScope.launch {
            runCatching { repository.deletePhoto(photo.id, hikeId) }
                .onSuccess { removePhotoState(photo.id) }
                .onFailure { error -> _state.update { it.copy(error = error.userMessage()) } }
        }
    }

    fun updateConnection(serverUrl: String, pairingKey: String) {
        repository.updateConnection(serverUrl, pairingKey)
        mapDataValidated = false
        _state.update { AppState() }
        refreshCompanionConfig()
        refreshLibrary(initial = true)
    }

    fun syncNow() {
        viewModelScope.launch {
            _state.update { it.copy(isSyncing = true, error = null) }
            runCatching { repository.syncNow() }
                .onSuccess {
                    _state.update { state -> state.copy(isSyncing = false) }
                    refreshLibrary()
                    _state.value.journal?.id?.let(::openHike)
                }
                .onFailure { error ->
                    _state.update { it.copy(isSyncing = false, error = error.userMessage()) }
                }
        }
    }

    fun retrySyncAttention() {
        viewModelScope.launch {
            repository.retryAttention()
            syncNow()
        }
    }

    fun discardSyncAttention() {
        viewModelScope.launch {
            runCatching { repository.discardSyncAttention() }
                .onSuccess {
                    refreshLibrary()
                    loadBadgeProgress(force = true)
                    loadSightings(force = true)
                    loadReviewQueue(force = true)
                    loadPublishQueue(force = true)
                }
                .onFailure { error -> _state.update { it.copy(error = error.userMessage()) } }
        }
    }

    fun clearError() {
        _state.update { it.copy(error = null) }
    }

    fun clearNotice() {
        _state.update { it.copy(notice = null) }
    }

    fun dismissCelebration() {
        _state.update { it.copy(celebration = null) }
    }

    private fun updatePhotoState(photoId: String, update: (Photo) -> Photo) {
        _state.update { state ->
            fun updateSpecies(record: SpeciesRecord): SpeciesRecord = record.copy(
                encounters = record.encounters.map { encounter ->
                    if (encounter.photo.id == photoId) encounter.copy(photo = update(encounter.photo)) else encounter
                },
            )
            state.copy(
                journal = state.journal?.copy(
                    photos = state.journal.photos.map { photo ->
                        if (photo.id == photoId) update(photo) else photo
                    },
                ),
                species = state.species.map(::updateSpecies),
                speciesDetail = state.speciesDetail?.let(::updateSpecies),
                reviewQueue = state.reviewQueue.map { item ->
                    if (item.photo.id == photoId) item.copy(photo = update(item.photo)) else item
                },
                publishQueue = state.publishQueue.copy(
                    items = state.publishQueue.items.map { item ->
                        if (item.photo.id == photoId) item.copy(photo = update(item.photo)) else item
                    },
                ),
            )
        }
    }

    private fun removePhotoState(photoId: String) {
        _state.update { state ->
            fun updateSpecies(record: SpeciesRecord): SpeciesRecord = record.copy(
                encounters = record.encounters.filterNot { it.photo.id == photoId },
            )
            val journal = state.journal
            val removedPhoto = journal?.photos?.firstOrNull { it.id == photoId }
            val remainingPhotos = journal?.photos.orEmpty().filterNot { it.id == photoId }
            val removedCover = journal?.coverPhotoId == photoId
            val removedImplicitCover = journal?.coverPhotoId == null && journal?.coverUrl == removedPhoto?.url
            val coverNeedsReplacement = removedCover || removedImplicitCover
            val replacementCoverUrl = remainingPhotos.maxByOrNull {
                "${it.takenAt.orEmpty()}|${it.createdAt.orEmpty()}"
            }?.url.orEmpty()
            state.copy(
                journal = journal?.let {
                    journal.copy(
                        photos = remainingPhotos,
                        photoCount = remainingPhotos.size,
                        coverPhotoId = journal.coverPhotoId.takeUnless { it == photoId },
                        coverUrl = if (coverNeedsReplacement) replacementCoverUrl else journal.coverUrl,
                    )
                },
                hikes = state.hikes.map { hike ->
                    if (hike.id == journal?.id) {
                        hike.copy(
                            photoCount = (hike.photoCount - 1).coerceAtLeast(0),
                            coverPhotoId = hike.coverPhotoId.takeUnless { it == photoId },
                            coverUrl = if (coverNeedsReplacement) replacementCoverUrl else hike.coverUrl,
                        )
                    } else {
                        hike
                    }
                },
                species = state.species.map(::updateSpecies),
                speciesDetail = state.speciesDetail?.let(::updateSpecies),
                reviewQueue = state.reviewQueue.filterNot { it.photo.id == photoId },
                publishQueue = state.publishQueue.copy(
                    items = state.publishQueue.items.filterNot { it.photo.id == photoId },
                ),
            )
        }
    }
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

private fun Throwable?.userMessage(): String =
    this?.message?.takeIf { it.isNotBlank() } ?: "HikeJournal could not complete that request."

internal fun mergeHikeLoadProgress(current: Hike?, incoming: Hike): Hike {
    if (current == null || current.id != incoming.id) return incoming
    return incoming.copy(
        durationSeconds = incoming.durationSeconds ?: current.durationSeconds,
        routeStartedAt = incoming.routeStartedAt ?: current.routeStartedAt,
        coverUrl = incoming.coverUrl.ifBlank { current.coverUrl },
        coverPhotoId = incoming.coverPhotoId ?: current.coverPhotoId,
        photoCount = maxOf(current.photoCount, incoming.photoCount),
        speciesCount = maxOf(current.speciesCount, incoming.speciesCount),
        photos = if (incoming.photos.size >= current.photos.size) incoming.photos else current.photos,
        routeSegments = incoming.routeSegments.ifEmpty { current.routeSegments },
    )
}

private fun NearbySpecies.asMapContext(): FieldQuest = FieldQuest(
    id = "",
    title = "Nearby field list",
    status = "active",
    linkedHikeId = null,
    areaId = areaId,
    areaName = areaName,
    latitude = latitude,
    longitude = longitude,
    radiusKm = radiusKm,
    targetDate = targetDate,
    periodLabel = periodLabel,
    iconicTaxon = iconicTaxon,
    progress = progress,
    taxa = taxa,
)
