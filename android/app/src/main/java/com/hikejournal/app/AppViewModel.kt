package com.hikejournal.app

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.HikeDraft
import com.hikejournal.app.data.HikeJournalRepository
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
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.data.SyncStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AppState(
    val hikes: List<Hike> = emptyList(),
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
    val reviewQueue: List<ReviewItem> = emptyList(),
    val publishQueue: PublishQueue = PublishQueue(false, 0, 0, 0, emptyList()),
    val isLoading: Boolean = true,
    val openingHikeId: String? = null,
    val isRefreshing: Boolean = false,
    val isOffline: Boolean = false,
    val error: String? = null,
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
    val inatAuthorizationUrl: String? = null,
    val queuingReviewId: String? = null,
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
                _state.update {
                    it.copy(
                        syncStatus = syncStatus,
                        isOffline = !syncStatus.connected || it.isOffline && syncStatus.pendingCount > 0,
                    )
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
            val cached = repository.loadCachedHike(hikeId)
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
            }.onFailure { error ->
                _state.update {
                    it.copy(isSavingQuest = false, discoveryNotice = error.userMessage())
                }
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

    fun loadSightings(force: Boolean = false) {
        if (_state.value.sightings.isNotEmpty() && !force) return
        viewModelScope.launch {
            _state.update { it.copy(isMapLoading = true, error = null) }
            runCatching { repository.loadSightings() }
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            sightings = result.value,
                            isMapLoading = false,
                            isOffline = result.fromCache,
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

    fun saveHike(draft: HikeDraft, editingId: String?, onSaved: () -> Unit) {
        viewModelScope.launch {
            _state.update { it.copy(isRefreshing = true, error = null) }
            runCatching {
                if (editingId == null) repository.createHike(draft).id
                else {
                    repository.updateHike(editingId, draft)
                    editingId
                }
            }.onSuccess { savedId ->
                onSaved()
                refreshLibrary()
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

    fun uploadPhotos(
        hikeId: String,
        uris: List<Uri>,
        caption: String,
        queueForReview: Boolean,
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
                _state.update { it.copy(uploadCurrent = index + 1) }
            }
            _state.update { it.copy(uploadCurrent = 0, uploadTotal = 0) }
            openHike(hikeId)
        }
    }

    suspend fun inspectMediaLocations(uris: List<Uri>): MediaLocationSummary =
        repository.inspectMediaLocations(uris)

    fun updateCaption(photoId: String, caption: String) {
        val hikeId = _state.value.journal?.id ?: return
        viewModelScope.launch {
            runCatching { repository.updateCaption(photoId, hikeId, caption) }
                .onSuccess { openHike(hikeId) }
                .onFailure { error -> _state.update { it.copy(error = error.userMessage()) } }
        }
    }

    fun queueSpeciesReview(photo: Photo) {
        val hikeId = _state.value.journal?.id ?: photo.hikeId ?: return
        viewModelScope.launch {
            _state.update { it.copy(queuingReviewId = photo.id, error = null) }
            runCatching { repository.queueSpeciesReview(photo.id, hikeId) }
                .onSuccess {
                    _state.update { state ->
                        state.copy(
                            journal = state.journal?.copy(
                                photos = state.journal.photos.map { existing ->
                                    if (existing.id == photo.id) {
                                        existing.copy(
                                            processingStatus = "in_review",
                                            syncState = if (existing.syncState == "synced") "queued" else existing.syncState,
                                        )
                                    } else {
                                        existing
                                    }
                                },
                            ),
                            reviewQueue = emptyList(),
                            queuingReviewId = null,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(queuingReviewId = null, error = error.userMessage()) }
                }
        }
    }

    fun deletePhoto(photoId: String) {
        val hikeId = _state.value.journal?.id ?: return
        viewModelScope.launch {
            runCatching { repository.deletePhoto(photoId, hikeId) }
                .onSuccess { openHike(hikeId) }
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

    fun clearSyncAttention() {
        viewModelScope.launch {
            repository.clearSyncAttention()
        }
    }

    fun clearError() {
        _state.update { it.copy(error = null) }
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
