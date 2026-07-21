package com.hikejournal.app

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.HikeDraft
import com.hikejournal.app.data.HikeJournalRepository
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.PublishItem
import com.hikejournal.app.data.PublishOptions
import com.hikejournal.app.data.PublishQueue
import com.hikejournal.app.data.ReviewCandidate
import com.hikejournal.app.data.ReviewItem
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
    val sightings: List<Sighting> = emptyList(),
    val reviewQueue: List<ReviewItem> = emptyList(),
    val publishQueue: PublishQueue = PublishQueue(false, 0, 0, 0, emptyList()),
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val isOffline: Boolean = false,
    val error: String? = null,
    val uploadCurrent: Int = 0,
    val uploadTotal: Int = 0,
    val isSpeciesLoading: Boolean = false,
    val isMapLoading: Boolean = false,
    val isReviewLoading: Boolean = false,
    val decidingReviewId: String? = null,
    val identifyingReviewId: String? = null,
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
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, error = null) }
            runCatching { repository.loadHike(hikeId) }
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            journal = result.value,
                            isLoading = false,
                            isOffline = result.fromCache,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(isLoading = false, error = error.userMessage()) }
                }
        }
    }

    fun closeJournal() {
        _state.update { it.copy(journal = null, error = null) }
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

    fun clearError() {
        _state.update { it.copy(error = null) }
    }
}

private fun Throwable?.userMessage(): String =
    this?.message?.takeIf { it.isNotBlank() } ?: "HikeJournal could not complete that request."
