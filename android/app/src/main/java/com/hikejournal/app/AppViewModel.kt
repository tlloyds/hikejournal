package com.hikejournal.app

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.HikeDraft
import com.hikejournal.app.data.HikeDeletionResult
import com.hikejournal.app.data.HikeJournalRepository
import com.hikejournal.app.data.HikeLocation
import com.hikejournal.app.data.MediaLocationSummary
import com.hikejournal.app.data.DiscoveryArea
import com.hikejournal.app.data.DiscoveryTaxon
import com.hikejournal.app.data.FieldQuest
import com.hikejournal.app.data.NearbySpecies
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.PublishItem
import com.hikejournal.app.data.PublishOptions
import com.hikejournal.app.data.PublishQueue
import com.hikejournal.app.data.ReviewCandidate
import com.hikejournal.app.data.ReviewItem
import com.hikejournal.app.data.QuestSightingsMap
import com.hikejournal.app.data.Sighting
import com.hikejournal.app.data.SpeciesLabel
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.data.SyncStatus
import com.hikejournal.app.data.withoutHikes
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AppState(
    val hikes: List<Hike> = emptyList(),
    val hikeLocations: List<HikeLocation> = emptyList(),
    val journal: Hike? = null,
    val species: List<SpeciesRecord> = emptyList(),
    val speciesDetail: SpeciesRecord? = null,
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
    val isLoading: Boolean = true,
    val openingHikeId: String? = null,
    val isRefreshing: Boolean = false,
    val isOffline: Boolean = false,
    val error: String? = null,
    val notice: String? = null,
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
    val prioritizingPhotoId: String? = null,
    val inatAuthorizationUrl: String? = null,
    val reviewUpdateId: String? = null,
    val speciesAssignmentId: String? = null,
    val coverUpdateId: String? = null,
    val deletingHikeId: String? = null,
    val isPublishLoading: Boolean = false,
    val publishingId: String? = null,
    val publishNotice: String? = null,
    val syncStatus: SyncStatus = SyncStatus(),
    val isSyncing: Boolean = false,
)

class AppViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = HikeJournalRepository(application)
    private val _state = MutableStateFlow(AppState())
    val state: StateFlow<AppState> = _state.asStateFlow()

    val serverUrl: String get() = repository.serverUrl
    val pairingKey: String get() = repository.pairingKey

    init {
        viewModelScope.launch {
            repository.syncStatus.collect { syncStatus ->
                val journalNeedsRemoteUrls = syncStatus.connected &&
                    syncStatus.pendingCount == 0 &&
                    syncStatus.syncingCount == 0 &&
                    _state.value.journal?.photos.orEmpty().any { photo ->
                        photo.syncState != "synced" || photo.url.startsWith("file:")
                    }
                _state.update {
                    it.copy(
                        syncStatus = syncStatus,
                        isOffline = !syncStatus.connected || it.isOffline && syncStatus.pendingCount > 0,
                    )
                }
                if (journalNeedsRemoteUrls) {
                    refreshJournalAfterSync(_state.value.journal?.id ?: return@collect)
                }
            }
        }
        refreshLibrary(initial = true)
    }

    fun refreshLibrary(initial: Boolean = false) {
        viewModelScope.launch {
            _state.update {
                it.copy(
                    isLoading = initial && it.hikes.isEmpty(),
                    isRefreshing = !initial,
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
        if (_state.value.hikeLocations.isNotEmpty()) return
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
                        state.copy(journal = result.value, isOffline = result.fromCache)
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
            runCatching { repository.loadHike(hikeId) }
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
        iconicTaxon: String?,
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
                    iconicTaxon = iconicTaxon,
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
        if (_state.value.sightings.isNotEmpty() && !force) return
        viewModelScope.launch {
            _state.update { it.copy(isMapLoading = true, error = null) }
            runCatching {
                repository.loadSightings() to repository.loadMapRouteSegments()
            }.onSuccess { (sightings, routes) ->
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
                _state.update {
                    it.copy(
                        reviewQueue = result.value,
                        decidingReviewId = null,
                        isOffline = result.fromCache,
                        species = emptyList(),
                        sightings = emptyList(),
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

    fun clearPublishNotice() {
        _state.update { it.copy(publishNotice = null) }
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
                    state.copy(
                        hikes = created?.let { newHike ->
                            listOf(newHike) + state.hikes.filterNot { it.id == newHike.id }
                        } ?: state.hikes,
                        isRefreshing = false,
                    )
                }
                onSaved()
                if (editingId != null) openHike(savedId)
                delay(1_000)
                refreshLibrary()
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
        if (!_state.value.syncStatus.connected) {
            _state.update {
                it.copy(error = "Connect HikeJournal before deleting an outing and all of its stored files.")
            }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(deletingHikeId = hike.id, error = null, notice = null) }
            runCatching { repository.deleteHike(hike.id) }
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
                    repository.uploadPhoto(hikeId, uri, caption, queueForReview)
                }
                if (result.isFailure) {
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
                        state.copy(
                            reviewQueue = state.reviewQueue.filterNot { it.photo.id == photo.id },
                            speciesAssignmentId = null,
                            badgesHydrated = false,
                            notice = "Assigned ${species.commonName.ifBlank { species.scientificName }}. " +
                                if (state.isOffline) "Saved for sync." else "Ready to publish.",
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
        viewModelScope.launch {
            _state.update { it.copy(coverUpdateId = photo.id, error = null) }
            runCatching { repository.setHikeCover(journal.id, coverPhotoId, coverUrl) }
                .onSuccess {
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
                            coverUpdateId = null,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(coverUpdateId = null, error = error.userMessage()) }
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
        _state.update { AppState() }
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
            state.copy(
                journal = state.journal?.let { journal ->
                    val photos = journal.photos.filterNot { it.id == photoId }
                    journal.copy(
                        photos = photos,
                        photoCount = photos.size,
                        coverPhotoId = journal.coverPhotoId.takeUnless { it == photoId },
                        coverUrl = if (journal.coverPhotoId == photoId) {
                            photos.maxByOrNull { "${it.takenAt.orEmpty()}|${it.createdAt.orEmpty()}" }?.url.orEmpty()
                        } else {
                            journal.coverUrl
                        },
                    )
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

private fun Throwable?.userMessage(): String =
    this?.message?.takeIf { it.isNotBlank() } ?: "HikeJournal could not complete that request."

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
