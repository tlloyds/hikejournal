import AVFoundation
import Combine
import CoreLocation
import Foundation
import HikeJournalLiveActivityTracking
import HikeJournalPersistence
import HikeJournalTracking

enum RecordingPresentationPhase: Equatable {
    case idle
    case preparing
    case recording
    case paused
    case finishing
    case finished
}

@MainActor
protocol ProgressSpeaking: AnyObject {
    func speak(_ announcement: MileAnnouncement)
    func stop()
}

@MainActor
final class SpeechProgressAnnouncer: ProgressSpeaking {
    private let synthesizer = AVSpeechSynthesizer()

    func speak(_ announcement: MileAnnouncement) {
        let utterance = AVSpeechUtterance(string: announcement.message)
        utterance.voice = AVSpeechSynthesisVoice(language: Locale.current.language.languageCode?.identifier)
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate
        synthesizer.speak(utterance)
    }

    func stop() {
        synthesizer.stopSpeaking(at: .immediate)
    }
}

@MainActor
final class RecordingStore: ObservableObject {
    @Published private(set) var phase: RecordingPresentationPhase = .idle
    @Published private(set) var snapshot: TrackingSnapshot?
    @Published private(set) var locationAuthorization: CLAuthorizationStatus
    @Published private(set) var latestRejection: LocationRejectionReason?
    @Published private(set) var errorMessage: String?
    @Published private(set) var lastFinishedRecording: FinishedRecording?
    @Published var voiceAnnouncementsEnabled: Bool {
        didSet { defaults.set(voiceAnnouncementsEnabled, forKey: Self.voicePreferenceKey) }
    }

    private static let voicePreferenceKey = "tracking.voiceAnnouncements.enabled"

    private let authentication: AuthenticationStore
    private let offlineStores: OfflineStoreCoordinator?
    private let location: any RecordingLocationControlling
    private let speaker: any ProgressSpeaking
    private let liveActivity: any HikeLiveActivityControlling
    private let defaults: UserDefaults
    private var recorder: HikeRecorder?

    init(
        authentication: AuthenticationStore,
        offlineStores: OfflineStoreCoordinator?,
        location: (any RecordingLocationControlling)? = nil,
        speaker: (any ProgressSpeaking)? = nil,
        liveActivity: (any HikeLiveActivityControlling)? = nil,
        defaults: UserDefaults = .standard
    ) {
        self.authentication = authentication
        self.offlineStores = offlineStores
        let location = location ?? RecordingLocationController()
        self.location = location
        self.speaker = speaker ?? SpeechProgressAnnouncer()
        self.liveActivity = liveActivity ?? makeSystemHikeLiveActivityController()
        self.defaults = defaults
        locationAuthorization = location.authorizationStatus
        voiceAnnouncementsEnabled = defaults.object(forKey: Self.voicePreferenceKey) == nil
            ? true
            : defaults.bool(forKey: Self.voicePreferenceKey)

        location.onAuthorizationChange = { [weak self] status in
            self?.locationAuthorization = status
            if status == .denied || status == .restricted {
                self?.handleLocationFailure(RecordingLocationError.alwaysAuthorizationRequired)
            }
        }
        location.onError = { [weak self] error in
            self?.handleLocationFailure(error)
        }
        location.onSample = { [weak self] sample, receivedAt in
            guard let self else { return }
            Task { await self.ingest(sample, receivedAt: receivedAt) }
        }
    }

    func requestBackgroundLocation() {
        errorMessage = nil
        location.requestAlwaysAuthorization()
    }

    func restoreIfNeeded() async {
        guard recorder == nil,
              let context = try? await accountContext() else {
            return
        }
        let recorder = HikeRecorder(
            database: context.database,
            routeDirectory: context.routesDirectory
        )
        do {
            if let recovered = try await recorder.restoreInterruptedRecording() {
                self.recorder = recorder
                snapshot = recovered
                phase = .paused
                await liveActivity.start(for: recovered)
            }
        } catch {
            errorMessage = readable(error)
        }
    }

    func start() async {
        guard phase == .idle || phase == .finished else { return }
        errorMessage = nil
        guard location.authorizationStatus == .authorizedAlways else {
            errorMessage = RecordingLocationError.alwaysAuthorizationRequired.localizedDescription
            return
        }
        phase = .preparing
        do {
            let context = try await accountContext()
            let recorder = HikeRecorder(
                database: context.database,
                routeDirectory: context.routesDirectory
            )
            let startedSnapshot = try await recorder.start()
            // The durable recording exists before Core Location starts. Keep
            // ownership of it immediately so a location-service failure leaves
            // a recoverable paused outing instead of an unreachable active row.
            self.recorder = recorder
            snapshot = startedSnapshot
            do {
                try location.start()
            } catch {
                snapshot = (try? await recorder.pause()) ?? startedSnapshot
                phase = .paused
                errorMessage = readable(error)
                return
            }
            lastFinishedRecording = nil
            phase = .recording
            await liveActivity.start(for: startedSnapshot)
        } catch {
            if snapshot?.status == .paused {
                phase = .paused
            } else {
                phase = .idle
            }
            errorMessage = readable(error)
        }
    }

    func pause() async {
        guard let recorder else { return }
        do {
            snapshot = try await recorder.pause()
            location.stop()
            speaker.stop()
            phase = .paused
            if let snapshot { await liveActivity.update(for: snapshot) }
        } catch {
            errorMessage = readable(error)
        }
    }

    func resume() async {
        guard let recorder else { return }
        errorMessage = nil
        guard location.authorizationStatus == .authorizedAlways else {
            errorMessage = RecordingLocationError.alwaysAuthorizationRequired.localizedDescription
            return
        }
        do {
            try location.start()
            snapshot = try await recorder.resume()
            phase = .recording
            if let snapshot { await liveActivity.update(for: snapshot) }
        } catch {
            location.stop()
            errorMessage = readable(error)
        }
    }

    func addFieldMark(type: FieldMarkType, note: String) async -> Bool {
        guard let recorder else { return false }
        do {
            _ = try await recorder.addFieldMark(type: type, note: note)
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
    }

    func finish(title: String, notes: String) async {
        guard let recorder else { return }
        phase = .finishing
        location.stop()
        speaker.stop()
        do {
            let finished = try await recorder.finish(title: title, notes: notes)
            lastFinishedRecording = finished
            snapshot = finished.snapshot
            self.recorder = nil
            phase = .finished
            await liveActivity.end(for: finished.snapshot, discarded: false)
        } catch {
            snapshot = try? await recorder.currentSnapshot()
            phase = .paused
            errorMessage = readable(error)
        }
    }

    func discard() async {
        guard let recorder else { return }
        do {
            let discardedSnapshot = snapshot
            try await recorder.discard()
            location.stop()
            speaker.stop()
            await liveActivity.end(for: discardedSnapshot, discarded: true)
            self.recorder = nil
            snapshot = nil
            phase = .idle
            errorMessage = nil
        } catch {
            errorMessage = readable(error)
        }
    }

    func clearError() {
        errorMessage = nil
    }

    /// Refreshes the clock-driven part of the active snapshot even when Core
    /// Location has not delivered another fix yet. The recorder owns the
    /// monotonic clock, so this does not create or persist a GPS point.
    func refreshSnapshot() async {
        guard phase == .recording, let recorder else { return }
        do {
            if let current = try await recorder.currentSnapshot() {
                snapshot = current
            }
        } catch {
            // A location tick should never turn a healthy recording into an
            // error state just because the display refresh missed a read.
        }
    }

    private func ingest(_ sample: LocationSample, receivedAt: Date) async {
        guard let recorder else { return }
        do {
            let update = try await recorder.ingest(sample, receivedAt: receivedAt)
            snapshot = update.snapshot
            if case .rejected(let reason) = update.ingestResult {
                latestRejection = reason
            } else {
                latestRejection = nil
                await liveActivity.update(for: update.snapshot)
            }
            if voiceAnnouncementsEnabled, let announcement = update.announcement {
                speaker.speak(announcement)
            }
        } catch {
            errorMessage = readable(error)
        }
    }

    private func handleLocationFailure(_ error: Error) {
        errorMessage = readable(error)
        guard phase == .recording else { return }
        Task { await pause() }
    }

    private func accountContext() async throws -> (
        database: HikeJournalPersistence.OfflineDatabase,
        routesDirectory: URL
    ) {
        guard case .signedIn(let account) = authentication.phase,
              let canonicalUserID = account.userID else {
            throw APIClientError.sessionRequired
        }
        guard let offlineStores else {
            throw OfflineStoreCoordinatorError.applicationSupportUnavailable
        }
        let database = try await offlineStores.database(canonicalUserID: canonicalUserID)
        let routes = try await offlineStores.routesDirectory(canonicalUserID: canonicalUserID)
        return (database, routes)
    }

    private func readable(_ error: Error) -> String {
        if let localized = error as? LocalizedError,
           let description = localized.errorDescription,
           !description.isEmpty {
            return description
        }
        return "HikeJournal couldn't update this recording. Your saved points remain on this iPhone."
    }
}
