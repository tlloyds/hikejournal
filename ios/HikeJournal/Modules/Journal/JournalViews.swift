import AVKit
import HikeJournalDomain
import HikeJournalPersistence
import SwiftUI
import UniformTypeIdentifiers

struct JournalLibraryView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var authentication: AuthenticationStore
    @ObservedObject private var journal: JournalStore
    @State private var search = ""
    @State private var scope: JournalScope = .current
    @State private var path: [String] = []
    @State private var showingEditor = false
    @State private var showingPlaces = false
    @State private var showingMedals = false

    init(model: AppModel) {
        self.model = model
        _authentication = ObservedObject(wrappedValue: model.authentication)
        _journal = ObservedObject(wrappedValue: model.journal)
    }

    var body: some View {
        NavigationStack(path: $path) {
            ZStack {
                ParchmentBackground()
                content
            }
            .navigationTitle("HikeJournal")
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $search, prompt: "Search hikes and places")
            .refreshable { await journal.refreshHikes() }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Menu {
                        Picker("Journal scope", selection: $scope) {
                            ForEach(JournalScope.allCases) { scope in
                                Label(scope.title, systemImage: scope.symbol).tag(scope)
                            }
                        }
                        Divider()
                        Button {
                            showingPlaces = true
                        } label: {
                            Label("Places & conditions", systemImage: "mappin.and.ellipse")
                        }
                        Button {
                            showingMedals = true
                        } label: {
                            Label("Trail medals", systemImage: "medal.fill")
                        }
                    } label: {
                        Label(scope.title, systemImage: "line.3.horizontal.decrease.circle")
                    }
                    .accessibilityLabel("Journal filter, \(scope.title)")
                }
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button {
                        showingEditor = true
                    } label: {
                        Image(systemName: "plus")
                    }
                    .disabled(!journal.quotaAllowsNewHike || !isSignedIn)
                    .accessibilityLabel("Add a journal")

                    Button {
                        model.selectedTab = .settings
                    } label: {
                        Image(systemName: "person.crop.circle")
                    }
                    .accessibilityLabel("Account and settings")
                }
            }
            .navigationDestination(for: String.self) { hikeID in
                JournalHikeDetailView(model: model, hikeID: hikeID)
            }
            .sheet(isPresented: $showingEditor) {
                HikeEditorSheet(existing: nil) { draft in
                    await journal.createHike(draft) != nil
                }
            }
            .sheet(isPresented: $showingPlaces) {
                PlacesWorkspaceView(model: model)
            }
            .sheet(isPresented: $showingMedals) {
                TrailMedalsView(model: model)
            }
            .alert(
                "Journal needs attention",
                isPresented: Binding(
                    get: { journal.errorMessage != nil },
                    set: { if !$0 { journal.clearError() } }
                )
            ) {
                Button("OK") { journal.clearError() }
            } message: {
                Text(journal.errorMessage ?? "")
            }
            .onChange(of: model.pendingDeepLink) { _, link in
                guard case .hike(let id) = link else { return }
                path = [id.uuidString.lowercased()]
                model.consumeDeepLink()
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        switch authentication.phase {
        case .restoring:
            ProgressView("Opening your field journal…")
                .font(HikeJournalTheme.body())
                .tint(HikeJournalTheme.trailText)
        case .signedOut:
            signedOut
        case .signedIn:
            if journal.isRefreshingHikes && journal.hikes.isEmpty {
                ProgressView("Gathering your hikes…")
                    .font(HikeJournalTheme.body())
                    .tint(HikeJournalTheme.trailText)
            } else if visibleHikes.isEmpty {
                emptyJournal
            } else {
                journalList
            }
        }
    }

    private var signedOut: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                BrandLandscape()
                    .frame(height: 244)
                    .overlay(alignment: .bottomLeading) {
                        Text("HIKEJOURNAL")
                            .font(HikeJournalTheme.display(45, relativeTo: .largeTitle))
                            .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.91))
                            .padding(22)
                    }
                VStack(alignment: .leading, spacing: 10) {
                    Text("Your field pages travel with you.")
                        .font(HikeJournalTheme.display(34, relativeTo: .title))
                        .foregroundStyle(HikeJournalTheme.ink)
                    Text("Sign in to open the same hikes, routes, and observations you keep on Android and the web.")
                        .font(HikeJournalTheme.body(18))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                    Button("Open account") { model.selectedTab = .settings }
                        .buttonStyle(TrailButtonStyle())
                        .padding(.top, 14)
                }
                .padding(24)
            }
        }
        .scrollIndicators(.hidden)
    }

    private var emptyJournal: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                Text("HIKEJOURNAL")
                    .font(HikeJournalTheme.display(46, relativeTo: .largeTitle))
                    .foregroundStyle(HikeJournalTheme.moss)
                Text("Your time outside, kept together.")
                    .font(HikeJournalTheme.body(18))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                    .padding(.top, 2)
                Divider().overlay(HikeJournalTheme.line).padding(.vertical, 25)
                TrailNotebookIllustration()
                    .frame(height: 178)
                Text(search.isEmpty ? "The first page is yours." : "No field pages match.")
                    .font(HikeJournalTheme.display(33, relativeTo: .title))
                    .foregroundStyle(HikeJournalTheme.ink)
                    .padding(.top, 24)
                Text(search.isEmpty
                     ? "Record an outing or add one after the trail. Routes, photos, and notes will stay together here."
                     : "Try a different hike title, date, or place.")
                    .font(HikeJournalTheme.body())
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                    .padding(.top, 8)
                if search.isEmpty {
                    HStack(spacing: 12) {
                        Button("Add a journal") { showingEditor = true }
                            .buttonStyle(TrailButtonStyle())
                        Button("Record") { model.openRecording() }
                            .buttonStyle(.bordered)
                            .tint(HikeJournalTheme.moss)
                    }
                    .padding(.top, 24)
                }
            }
            .padding(24)
        }
        .scrollIndicators(.hidden)
    }

    private var journalList: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("HIKEJOURNAL")
                        .font(HikeJournalTheme.display(38, relativeTo: .largeTitle))
                        .foregroundStyle(HikeJournalTheme.moss)
                    Text(listSummary)
                        .font(HikeJournalTheme.body(16))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }
                .padding(.horizontal, 22)
                .padding(.top, 14)
                .padding(.bottom, 18)

                if let message = journal.statusMessage {
                    Label(message, systemImage: "icloud.slash")
                        .font(HikeJournalTheme.body(14))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                        .padding(.horizontal, 22)
                        .padding(.bottom, 14)
                        .accessibilityElement(children: .combine)
                }

                ForEach(visibleHikes) { hike in
                    NavigationLink(value: hike.id) {
                        JournalRow(hike: hike)
                    }
                    .buttonStyle(.plain)
                    .contextMenu {
                        Button(hike.isArchived ? "Return to journal" : "Archive") {
                            Task { await journal.setArchived(id: hike.id, archived: !hike.isArchived) }
                        }
                        ShareLink(item: shareText(hike))
                        Button("Delete", role: .destructive) {
                            Task { await journal.deleteHike(id: hike.id) }
                        }
                    }
                    Divider().overlay(HikeJournalTheme.line).padding(.leading, 22)
                }
            }
            .padding(.bottom, 42)
        }
        .scrollIndicators(.hidden)
        .scrollBounceBehavior(.basedOnSize)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .animation(.snappy(duration: 0.34), value: visibleHikes.map(\.id))
    }

    private var visibleHikes: [Hike] {
        journal.hikes.filter { hike in
            let scopeMatches = switch scope {
            case .current: !hike.isArchived
            case .archived: hike.isArchived
            case .all: true
            }
            guard scopeMatches else { return false }
            let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !query.isEmpty else { return true }
            return [hike.title, hike.locationName, hike.primaryLocationName, hike.notes, hike.hikeDate]
                .contains { $0.localizedCaseInsensitiveContains(query) }
        }
    }

    private var listSummary: String {
        let count = visibleHikes.count
        let offline = journal.showingCachedData ? " · saved offline copy" : ""
        return "\(count) \(count == 1 ? "field page" : "field pages")\(offline)"
    }

    private var isSignedIn: Bool {
        if case .signedIn = authentication.phase { return true }
        return false
    }

    private func shareText(_ hike: Hike) -> String {
        var parts = [hike.title, JournalDate.display(hike.hikeDate)]
        if !hike.locationName.isEmpty { parts.append(hike.locationName) }
        if let miles = hike.distanceMiles { parts.append(String(format: "%.2f miles", miles)) }
        if !hike.notes.isEmpty { parts.append(hike.notes) }
        parts.append("Kept in HikeJournal")
        return parts.joined(separator: "\n")
    }
}

private enum JournalScope: String, CaseIterable, Identifiable {
    case current
    case archived
    case all

    var id: String { rawValue }
    var title: String {
        switch self {
        case .current: "Current"
        case .archived: "Archived"
        case .all: "All"
        }
    }
    var symbol: String {
        switch self {
        case .current: "book.closed"
        case .archived: "archivebox"
        case .all: "books.vertical"
        }
    }
}

private struct JournalRow: View {
    let hike: Hike

    var body: some View {
        HStack(spacing: 16) {
            JournalRemoteImage(urlString: hike.coverUrl, fallback: "figure.hiking")
                .frame(width: 88, height: 92)
                .clipped()
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 5) {
                HStack(alignment: .firstTextBaseline, spacing: 7) {
                    Text(hike.title)
                        .font(HikeJournalTheme.display(23, relativeTo: .title3))
                        .foregroundStyle(HikeJournalTheme.ink)
                        .lineLimit(2)
                    if hike.syncState != "synced" {
                        Image(systemName: "arrow.triangle.2.circlepath")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(HikeJournalTheme.trailText)
                            .accessibilityLabel("Waiting to sync")
                    }
                }
                Text(JournalDate.display(hike.hikeDate))
                    .font(HikeJournalTheme.label(13, relativeTo: .subheadline))
                    .foregroundStyle(HikeJournalTheme.trailText)
                if !hike.locationName.isEmpty || !hike.primaryLocationName.isEmpty {
                    Label(hike.locationName.isEmpty ? hike.primaryLocationName : hike.locationName, systemImage: "mappin")
                        .font(HikeJournalTheme.body(14))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                        .lineLimit(1)
                }
                HStack(spacing: 13) {
                    if let miles = hike.distanceMiles {
                        Label(String(format: "%.1f mi", miles), systemImage: "point.topleft.down.to.point.bottomright.curvepath")
                    }
                    Label("\(hike.photoCount)", systemImage: "photo")
                    if hike.speciesCount > 0 {
                        Label("\(hike.speciesCount)", systemImage: "leaf")
                    }
                }
                .font(HikeJournalTheme.body(13))
                .foregroundStyle(HikeJournalTheme.inkMuted)
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right")
                .font(.caption.weight(.bold))
                .foregroundStyle(HikeJournalTheme.inkMuted.opacity(0.6))
                .accessibilityHidden(true)
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 13)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens this journal")
    }
}

struct JournalHikeDetailView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var journal: JournalStore
    @ObservedObject private var media: MediaAttachmentStore
    let hikeID: String

    @Environment(\.dismiss) private var dismiss
    @State private var showingEditor = false
    @State private var showingMedia = false
    @State private var showingDelete = false
    @State private var showingComparison = false
    @State private var showingShare = false
    @State private var showingRouteImporter = false
    @State private var editingPhoto: Photo?
    @State private var inspectingPhoto: Photo?
    @State private var localErrorMessage: String?

    init(model: AppModel, hikeID: String) {
        self.model = model
        self.hikeID = hikeID
        _journal = ObservedObject(wrappedValue: model.journal)
        _media = ObservedObject(wrappedValue: model.media)
    }

    var body: some View {
        ZStack {
            ParchmentBackground()
            if let hike {
                detail(hike)
            } else if journal.activeLoads.contains("hike:\(hikeID)") {
                ProgressView("Opening field page…")
                    .tint(HikeJournalTheme.trailText)
            } else {
                ContentUnavailableView(
                    "Journal unavailable",
                    systemImage: "book.closed",
                    description: Text("Pull to retry when this iPhone has a connection.")
                )
            }
        }
        .navigationTitle(hike?.title ?? "Journal")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let hike {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button("Edit journal", systemImage: "square.and.pencil") { showingEditor = true }
                        Button("Import TCX route", systemImage: "square.and.arrow.down") {
                            showingRouteImporter = true
                        }
                        Button("Compare hikes", systemImage: "arrow.left.arrow.right") { showingComparison = true }
                        Button("Share trail keepsake", systemImage: "square.and.arrow.up") {
                            showingShare = true
                        }
                        Button(hike.isArchived ? "Return to journal" : "Archive", systemImage: "archivebox") {
                            Task { await journal.setArchived(id: hikeID, archived: !hike.isArchived) }
                        }
                        Button("Delete journal", systemImage: "trash", role: .destructive) { showingDelete = true }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                    .accessibilityLabel("Journal actions")
                }
            }
        }
        .task(id: hikeID) { await journal.loadHike(id: hikeID) }
        .refreshable { await journal.loadHike(id: hikeID, force: true) }
        .sheet(isPresented: $showingEditor) {
            if let hike {
                HikeEditorSheet(existing: hike) { draft in
                    await journal.updateHike(id: hikeID, draft: draft)
                }
            }
        }
        .sheet(isPresented: $showingMedia) {
            PhotoLibraryBrowser(selectionLimit: journal.remainingMediaAllowance) { identifiers in
                await media.importAssets(identifiers, into: hikeID)
                if let message = media.errorMessage { throw JournalMediaError(message: message) }
                await journal.loadHike(id: hikeID, force: true)
            }
        }
        .sheet(item: $editingPhoto) { photo in
            CaptionEditor(photo: photo) { caption in
                await journal.queuePhotoAction(
                    kind: .updateCaption,
                    photoID: photo.id,
                    hikeID: hikeID,
                    payload: ["caption": caption]
                )
            }
        }
        .sheet(item: $inspectingPhoto) { photo in
            JournalMediaDetailView(
                journal: journal,
                seed: photo,
                hikeID: hikeID,
                isCover: hike?.coverPhotoId == photo.id
            )
        }
        .sheet(isPresented: $showingComparison) {
            HikeComparisonSheet(journal: journal, hikeID: hikeID)
        }
        .sheet(isPresented: $showingShare) {
            if let hike {
                HikeShareSheet(hike: hike)
            }
        }
        .fileImporter(
            isPresented: $showingRouteImporter,
            allowedContentTypes: routeImportTypes,
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                guard let url = urls.first else { return }
                Task {
                    if await journal.queueRouteImport(fileURL: url, hikeID: hikeID) {
                        await journal.loadHike(id: hikeID, force: true)
                    }
                }
            case .failure(let error):
                if (error as NSError).code != NSUserCancelledError {
                    localErrorMessage = error.localizedDescription
                }
            }
        }
        .confirmationDialog("Delete this journal?", isPresented: $showingDelete) {
            Button("Delete journal", role: .destructive) {
                Task {
                    if await journal.deleteHike(id: hikeID) { dismiss() }
                }
            }
            Button("Keep it", role: .cancel) {}
        } message: {
            Text("The deletion is queued safely if this iPhone is offline. Cloud quota updates after sync.")
        }
        .alert(
            "Journal needs attention",
            isPresented: Binding(
                get: { journal.errorMessage != nil || localErrorMessage != nil },
                set: {
                    if !$0 {
                        journal.clearError()
                        localErrorMessage = nil
                    }
                }
            )
        ) {
            Button("OK") {
                journal.clearError()
                localErrorMessage = nil
            }
        } message: {
            Text(localErrorMessage ?? journal.errorMessage ?? "")
        }
    }

    private var hike: Hike? {
        journal.details[hikeID] ?? journal.hikes.first { $0.id == hikeID }
    }

    private func detail(_ hike: Hike) -> some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0) {
                hero(hike)
                VStack(alignment: .leading, spacing: 26) {
                    if !hike.notes.isEmpty {
                        JournalSection(title: "Field notes") {
                            Text(hike.notes)
                                .font(HikeJournalTheme.body(18))
                                .foregroundStyle(HikeJournalTheme.ink)
                                .textSelection(.enabled)
                        }
                    }

                    if !hike.routeSegments.isEmpty {
                        JournalSection(title: "Route") {
                            JournalRouteSketch(segments: hike.routeSegments)
                                .frame(height: 230)
                            Text("\(hike.routeSegments.flatMap { $0 }.count) saved GPS points · \(hike.routeSegments.count) \(hike.routeSegments.count == 1 ? "segment" : "segments")")
                                .font(HikeJournalTheme.body(14))
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                    }

                    JournalSection(title: "Media", actionTitle: "Add", action: { showingMedia = true }) {
                        if hike.photos.isEmpty {
                            Text("Original photos and videos added here keep their Photos-library location when one exists.")
                                .font(HikeJournalTheme.body())
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        } else {
                            LazyVGrid(columns: [GridItem(.adaptive(minimum: 145), spacing: 3)], spacing: 3) {
                                ForEach(hike.photos) { photo in
                                    JournalPhotoTile(
                                        photo: photo,
                                        isCover: hike.coverPhotoId == photo.id,
                                        openDetails: { inspectingPhoto = photo },
                                        editCaption: { editingPhoto = photo },
                                        makeCover: {
                                            Task {
                                                await journal.queuePhotoAction(
                                                    kind: .setHikeCover,
                                                    photoID: photo.id,
                                                    hikeID: hikeID,
                                                    payload: ["photo_id": photo.id]
                                                )
                                            }
                                        },
                                        delete: {
                                            Task {
                                                await journal.queuePhotoAction(
                                                    kind: .deletePhoto,
                                                    photoID: photo.id,
                                                    hikeID: hikeID
                                                )
                                            }
                                        }
                                    )
                                }
                            }
                        }
                        if media.isImporting {
                            ProgressView(value: media.progress) {
                                Text("Securing originals")
                            }
                            .tint(HikeJournalTheme.trailText)
                        }
                    }

                    let observations = hike.photos.flatMap { photo in
                        photo.species.map { (photo: photo, species: $0) }
                    }
                    if !observations.isEmpty {
                        JournalSection(title: "Observations") {
                            ForEach(Array(observations.enumerated()), id: \.offset) { _, item in
                                Button {
                                    inspectingPhoto = item.photo
                                } label: {
                                    JournalObservationRow(photo: item.photo, species: item.species)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }

                    JournalSection(title: "Conditions") {
                        if let weather = hike.weather {
                            WeatherSummaryView(weather: weather)
                        } else {
                            Button {
                                Task { await journal.enrichWeather(hikeID: hikeID) }
                            } label: {
                                Label("Add historical weather", systemImage: "cloud.sun")
                            }
                            .buttonStyle(.bordered)
                            .tint(HikeJournalTheme.moss)
                        }
                    }

                    if !hike.fieldMarks.isEmpty {
                        JournalSection(title: "Field marks") {
                            ForEach(hike.fieldMarks) { mark in
                                HStack(alignment: .top, spacing: 12) {
                                    Image(systemName: "mappin.circle.fill")
                                        .foregroundStyle(HikeJournalTheme.trailText)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(mark.markType.replacingOccurrences(of: "_", with: " ").capitalized)
                                            .font(HikeJournalTheme.label(15, relativeTo: .headline))
                                        if !mark.note.isEmpty {
                                            Text(mark.note).font(HikeJournalTheme.body(15))
                                        }
                                        Text(String(format: "%.5f, %.5f", mark.latitude, mark.longitude))
                                            .font(HikeJournalTheme.body(12))
                                            .foregroundStyle(HikeJournalTheme.inkMuted)
                                    }
                                }
                                .accessibilityElement(children: .combine)
                            }
                        }
                    }
                }
                .padding(22)
                .padding(.bottom, 34)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .scrollIndicators(.hidden)
        .scrollBounceBehavior(.basedOnSize)
    }

    private func hero(_ hike: Hike) -> some View {
        ZStack(alignment: .bottomLeading) {
            JournalRemoteImage(urlString: hike.coverUrl, fallback: "mountain.2.fill")
                .frame(height: 285)
                .overlay {
                    LinearGradient(
                        colors: [.black.opacity(0.04), .black.opacity(0.72)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                }
            VStack(alignment: .leading, spacing: 5) {
                Text(JournalDate.display(hike.hikeDate).uppercased())
                    .font(HikeJournalTheme.label(12))
                    .tracking(1.3)
                Text(hike.title)
                    .font(HikeJournalTheme.display(38, relativeTo: .largeTitle))
                if !hike.locationName.isEmpty || !hike.primaryLocationName.isEmpty {
                    Label(hike.locationName.isEmpty ? hike.primaryLocationName : hike.locationName, systemImage: "mappin")
                        .font(HikeJournalTheme.body(16))
                }
                HStack(spacing: 18) {
                    if let miles = hike.distanceMiles { Text(String(format: "%.2f miles", miles)) }
                    if let duration = hike.durationSeconds { Text(JournalDate.duration(duration)) }
                    Text("\(hike.photoCount) media")
                }
                .font(HikeJournalTheme.label(13, relativeTo: .subheadline))
            }
            .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.92))
            .padding(22)
        }
        .accessibilityElement(children: .combine)
    }

    private func shareText(_ hike: Hike) -> String {
        var parts = [hike.title, JournalDate.display(hike.hikeDate)]
        if !hike.locationName.isEmpty { parts.append(hike.locationName) }
        if let miles = hike.distanceMiles { parts.append(String(format: "%.2f miles", miles)) }
        if !hike.notes.isEmpty { parts.append(hike.notes) }
        parts.append("Kept in HikeJournal")
        return parts.joined(separator: "\n")
    }

    private var routeImportTypes: [UTType] {
        [UTType(filenameExtension: "tcx") ?? .xml, .xml]
    }
}

private struct HikeEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var title: String
    @State private var date: Date
    @State private var location: String
    @State private var distance: String
    @State private var notes: String
    @State private var saving = false
    @State private var errorMessage: String?

    let existing: Hike?
    let save: (HikeDraft) async -> Bool

    init(existing: Hike?, save: @escaping (HikeDraft) async -> Bool) {
        self.existing = existing
        self.save = save
        _title = State(initialValue: existing?.title ?? "")
        _date = State(initialValue: JournalDate.parse(existing?.hikeDate) ?? Date())
        _location = State(initialValue: existing?.locationName ?? "")
        _distance = State(initialValue: existing?.distanceMiles.map { String(format: "%.2f", $0) } ?? "")
        _notes = State(initialValue: existing?.notes ?? "")
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Field page") {
                    TextField("Hike title", text: $title)
                        .textInputAutocapitalization(.words)
                    DatePicker("Date", selection: $date, displayedComponents: .date)
                    TextField("Place or trail", text: $location)
                        .textInputAutocapitalization(.words)
                    TextField("Distance in miles", text: $distance)
                        .keyboardType(.decimalPad)
                }
                Section("Notes") {
                    TextField("What do you want to remember?", text: $notes, axis: .vertical)
                        .lineLimit(6...14)
                }
                if let errorMessage {
                    Section { Text(errorMessage).foregroundStyle(HikeJournalTheme.error) }
                }
            }
            .scrollContentBackground(.hidden)
            .background(ParchmentBackground())
            .navigationTitle(existing == nil ? "New journal" : "Edit journal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(saving ? "Saving…" : "Save") { saveDraft() }
                        .disabled(saving || title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }

    private func saveDraft() {
        let cleanTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanTitle.isEmpty else { return }
        let miles = distance.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? nil : Double(distance.replacingOccurrences(of: ",", with: "."))
        if let miles, !miles.isFinite || miles < 0 {
            errorMessage = "Distance must be a positive number."
            return
        }
        saving = true
        let draft = HikeDraft(
            title: cleanTitle,
            hikeDate: JournalDate.api(date),
            distanceMiles: miles,
            locationName: location.trimmingCharacters(in: .whitespacesAndNewlines),
            notes: notes.trimmingCharacters(in: .whitespacesAndNewlines),
            locationId: existing?.primaryLocationId
        )
        Task {
            let saved = await save(draft)
            saving = false
            if saved { dismiss() }
            else { errorMessage = "The journal could not be queued. Your existing pages are unchanged." }
        }
    }
}

private struct CaptionEditor: View {
    @Environment(\.dismiss) private var dismiss
    @State private var caption: String
    @State private var saving = false
    let photo: Photo
    let save: (String) async -> Bool

    init(photo: Photo, save: @escaping (String) async -> Bool) {
        self.photo = photo
        self.save = save
        _caption = State(initialValue: photo.caption)
    }

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 18) {
                JournalRemoteImage(urlString: photo.url, fallback: "photo")
                    .frame(height: 250)
                    .clipped()
                TextField("What happened here?", text: $caption, axis: .vertical)
                    .lineLimit(4...9)
                    .textFieldStyle(.roundedBorder)
                Spacer()
            }
            .padding(20)
            .background(ParchmentBackground())
            .navigationTitle("Media caption")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(saving ? "Saving…" : "Save") {
                        saving = true
                        Task {
                            if await save(caption.trimmingCharacters(in: .whitespacesAndNewlines)) { dismiss() }
                            saving = false
                        }
                    }
                    .disabled(saving)
                }
            }
        }
    }
}

private struct JournalPhotoTile: View {
    let photo: Photo
    let isCover: Bool
    let openDetails: () -> Void
    let editCaption: () -> Void
    let makeCover: () -> Void
    let delete: () -> Void

    var body: some View {
        Button(action: openDetails) {
            tile
        }
        .buttonStyle(.plain)
        .contextMenu {
            Button("Open details", systemImage: "arrow.up.left.and.arrow.down.right", action: openDetails)
            Button("Edit caption", systemImage: "text.quote", action: editCaption)
            Button("Use as cover", systemImage: "photo.badge.checkmark", action: makeCover)
            Button("Delete media", systemImage: "trash", role: .destructive, action: delete)
        }
        .accessibilityLabel(photo.caption.isEmpty ? "Journal media" : photo.caption)
        .accessibilityHint("Opens media details")
    }

    private var tile: some View {
            ZStack(alignment: .bottomLeading) {
                JournalRemoteImage(urlString: photo.url, fallback: photo.contentType.hasPrefix("video/") ? "video" : "photo")
                    .aspectRatio(1, contentMode: .fill)
                    .clipped()
                LinearGradient(colors: [.clear, .black.opacity(0.66)], startPoint: .center, endPoint: .bottom)
                VStack(alignment: .leading, spacing: 2) {
                    if isCover { Label("Cover", systemImage: "bookmark.fill") }
                    if let species = photo.species.first(where: \.isPrimary) ?? photo.species.first {
                        Text(species.commonName.isEmpty ? species.scientificName : species.commonName).lineLimit(1)
                    } else if !photo.caption.isEmpty {
                        Text(photo.caption).lineLimit(2)
                    }
                    if photo.contentType.hasPrefix("video/") {
                        Label("Video", systemImage: "play.fill")
                    }
                }
                .font(HikeJournalTheme.label(12, relativeTo: .caption))
                .foregroundStyle(.white)
                .padding(8)
            }
            .contentShape(Rectangle())
    }
}

private struct JournalObservationRow: View {
    let photo: Photo
    let species: SpeciesLabel

    var body: some View {
        HStack(spacing: 13) {
            JournalRemoteImage(urlString: photo.url, fallback: "leaf")
                .frame(width: 62, height: 62)
                .clipped()
            VStack(alignment: .leading, spacing: 2) {
                Text(species.commonName.isEmpty ? species.scientificName : species.commonName)
                    .font(HikeJournalTheme.label(16, relativeTo: .headline))
                    .foregroundStyle(HikeJournalTheme.ink)
                if !species.scientificName.isEmpty {
                    Text(species.scientificName)
                        .font(HikeJournalTheme.body(13))
                        .italic()
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }
                Text("\(friendlyObservationConfidence(species.confidence)) · \(friendlyObservationProvenance(species.provenance))")
                    .font(HikeJournalTheme.body(12))
                    .foregroundStyle(HikeJournalTheme.trailText)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.caption.weight(.bold))
                .foregroundStyle(HikeJournalTheme.inkMuted.opacity(0.55))
        }
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens the observation and identification history")
    }
}

private struct JournalMediaDetailView: View {
    @ObservedObject var journal: JournalStore
    let seed: Photo
    let hikeID: String
    let isCover: Bool

    @Environment(\.dismiss) private var dismiss
    @State private var showingCaption = false
    @State private var showingKnownSpecies = false
    @State private var showingNaturalHistory = false
    @State private var showingDelete = false
    @State private var working = false

    var body: some View {
        NavigationStack {
            ZStack {
                Color(red: 0.06, green: 0.10, blue: 0.08).ignoresSafeArea()
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        mediaPlane
                        VStack(alignment: .leading, spacing: 16) {
                            if let species = primarySpecies {
                                identification(species)
                            } else if !currentPhoto.contentType.hasPrefix("video/") {
                                unidentifiedActions
                            } else {
                                Text("Field video")
                                    .font(HikeJournalTheme.display(27, relativeTo: .title2))
                                    .foregroundStyle(.white)
                                Text("Videos keep their date and location, but species review is limited to still photos.")
                                    .font(HikeJournalTheme.body(15))
                                    .foregroundStyle(Color.white.opacity(0.72))
                            }

                            if !currentPhoto.caption.isEmpty {
                                Divider().overlay(Color.white.opacity(0.20))
                                Text(currentPhoto.caption)
                                    .font(HikeJournalTheme.body(17))
                                    .foregroundStyle(.white)
                            }

                            if let latitude = currentPhoto.latitude, let longitude = currentPhoto.longitude {
                                Label(
                                    String(format: "%.5f, %.5f", latitude, longitude),
                                    systemImage: "mappin.and.ellipse"
                                )
                                .font(HikeJournalTheme.body(14))
                                .foregroundStyle(Color.white.opacity(0.72))
                            }

                            Divider().overlay(Color.white.opacity(0.20))
                            mediaActions
                        }
                        .padding(20)
                        .padding(.bottom, 26)
                    }
                }
                .scrollIndicators(.hidden)
            }
            .navigationTitle(currentPhoto.contentType.hasPrefix("video/") ? "Field video" : "Field photo")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
            .sheet(isPresented: $showingCaption) {
                CaptionEditor(photo: currentPhoto) { caption in
                    await journal.queuePhotoAction(
                        kind: .updateCaption,
                        photoID: currentPhoto.id,
                        hikeID: hikeID,
                        payload: ["caption": caption]
                    )
                }
            }
            .sheet(isPresented: $showingKnownSpecies) {
                KnownSpeciesAssignmentView(
                    journal: journal,
                    photoID: currentPhoto.id,
                    hikeID: hikeID
                )
            }
            .sheet(isPresented: $showingNaturalHistory) {
                if let species = primarySpecies, let observationID = species.observationId {
                    NaturalHistoryEditor(species: species) { confidence, phenophases in
                        let saved = await journal.updateNaturalHistory(
                            observationID: observationID,
                            hikeID: hikeID,
                            confidence: confidence,
                            phenophases: phenophases
                        )
                        if saved { await journal.loadHike(id: hikeID, force: true) }
                        return saved
                    }
                }
            }
            .confirmationDialog("Delete this media item?", isPresented: $showingDelete) {
                Button("Delete from HikeJournal", role: .destructive) {
                    Task {
                        if await journal.queuePhotoAction(
                            kind: .deletePhoto,
                            photoID: currentPhoto.id,
                            hikeID: hikeID
                        ) { dismiss() }
                    }
                }
                Button("Keep it", role: .cancel) {}
            } message: {
                Text("The deletion is queued safely if this iPhone is offline.")
            }
        }
    }

    @ViewBuilder
    private var mediaPlane: some View {
        if currentPhoto.contentType.hasPrefix("video/"), let url = URL(string: currentPhoto.url) {
            JournalVideoPreview(url: url)
                .frame(height: 360)
        } else {
            JournalRemoteImage(urlString: currentPhoto.url, fallback: "photo")
                .scaledToFit()
                .frame(maxWidth: .infinity, minHeight: 280, maxHeight: 480)
        }
    }

    private func identification(_ species: SpeciesLabel) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(species.commonName.isEmpty ? species.scientificName : species.commonName)
                .font(HikeJournalTheme.display(32, relativeTo: .title))
                .foregroundStyle(Color(red: 0.78, green: 0.87, blue: 0.75))
            if !species.scientificName.isEmpty {
                Text(species.scientificName)
                    .font(HikeJournalTheme.body(15))
                    .italic()
                    .foregroundStyle(Color.white.opacity(0.72))
            }
            Text("\(friendlyObservationConfidence(species.confidence)) · \(friendlyObservationProvenance(species.provenance))")
                .font(HikeJournalTheme.label(12))
                .tracking(0.5)
                .foregroundStyle(Color(red: 0.58, green: 0.70, blue: 0.57))

            if !species.phenophases.isEmpty {
                Text(species.phenophases.map(friendlyPhenophase).joined(separator: " · "))
                    .font(HikeJournalTheme.body(15))
                    .foregroundStyle(.white)
            }

            if !species.identificationHistory.isEmpty {
                Text("IDENTIFICATION HISTORY")
                    .font(HikeJournalTheme.label(11))
                    .tracking(1.2)
                    .foregroundStyle(Color(red: 0.58, green: 0.70, blue: 0.57))
                    .padding(.top, 8)
                ForEach(species.identificationHistory.prefix(5)) { event in
                    Text("\(event.createdAt.map { String($0.prefix(10)) } ?? "Undated") · \(friendlyObservationProvenance(event.source)) → \(event.commonName.isEmpty ? event.scientificName : event.commonName)")
                        .font(HikeJournalTheme.body(13))
                        .foregroundStyle(Color.white.opacity(0.76))
                }
            }

            if let _ = species.observationId {
                Button {
                    showingNaturalHistory = true
                } label: {
                    Label("Confidence & phenophase", systemImage: "leaf.circle")
                        .frame(maxWidth: .infinity, minHeight: 46)
                }
                .buttonStyle(.bordered)
                .tint(Color(red: 0.72, green: 0.82, blue: 0.69))
                .padding(.top, 5)
            }

            if !species.wikipediaSummary.isEmpty {
                Text("FROM WIKIPEDIA")
                    .font(HikeJournalTheme.label(11))
                    .tracking(1.2)
                    .foregroundStyle(Color(red: 0.58, green: 0.70, blue: 0.57))
                    .padding(.top, 8)
                Text(species.wikipediaSummary)
                    .font(HikeJournalTheme.body(15))
                    .foregroundStyle(Color.white.opacity(0.84))
            }
            if let url = URL(string: species.wikipediaUrl), !species.wikipediaUrl.isEmpty {
                Link("Read on Wikipedia", destination: url)
                    .font(HikeJournalTheme.label(14, relativeTo: .headline))
                    .foregroundStyle(Color(red: 0.85, green: 0.93, blue: 0.82))
            }
        }
    }

    private var unidentifiedActions: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Unidentified field photo")
                .font(HikeJournalTheme.display(28, relativeTo: .title2))
                .foregroundStyle(.white)
            Button {
                showingKnownSpecies = true
            } label: {
                Label("Assign known species", systemImage: "checkmark.seal")
                    .frame(maxWidth: .infinity, minHeight: 46)
            }
            .buttonStyle(.bordered)
            .tint(Color(red: 0.72, green: 0.82, blue: 0.69))

            Button {
                let queued = currentPhoto.processingStatus != "in_review"
                working = true
                Task {
                    _ = await journal.queueSpeciesReview(
                        photoID: currentPhoto.id,
                        hikeID: hikeID,
                        queued: queued
                    )
                    working = false
                }
            } label: {
                Label(
                    currentPhoto.processingStatus == "in_review" ? "Remove from species review" : "Add to species review",
                    systemImage: currentPhoto.processingStatus == "in_review" ? "checkmark.circle.fill" : "sparkle.magnifyingglass"
                )
                .frame(maxWidth: .infinity, minHeight: 46)
            }
            .buttonStyle(.bordered)
            .tint(Color(red: 0.72, green: 0.82, blue: 0.69))
            .disabled(working)
        }
    }

    private var mediaActions: some View {
        VStack(spacing: 8) {
            Button {
                showingCaption = true
            } label: {
                Label("Edit note", systemImage: "text.quote")
                    .frame(maxWidth: .infinity, minHeight: 44)
            }
            .buttonStyle(.bordered)
            .tint(.white)

            if !currentPhoto.contentType.hasPrefix("video/") && !isCover {
                Button {
                    Task {
                        _ = await journal.queuePhotoAction(
                            kind: .setHikeCover,
                            photoID: currentPhoto.id,
                            hikeID: hikeID,
                            payload: ["photo_id": currentPhoto.id]
                        )
                    }
                } label: {
                    Label("Use as journal cover", systemImage: "photo.badge.checkmark")
                        .frame(maxWidth: .infinity, minHeight: 44)
                }
                .buttonStyle(.bordered)
                .tint(.white)
            }

            Button("Delete media", role: .destructive) { showingDelete = true }
                .font(HikeJournalTheme.label(15, relativeTo: .headline))
                .frame(maxWidth: .infinity, minHeight: 44)
        }
    }

    private var currentPhoto: Photo {
        journal.details[hikeID]?.photos.first { $0.id == seed.id } ?? seed
    }

    private var primarySpecies: SpeciesLabel? {
        currentPhoto.species.first(where: \.isPrimary) ?? currentPhoto.species.first
    }
}

private struct JournalVideoPreview: View {
    @State private var player: AVPlayer

    init(url: URL) {
        _player = State(initialValue: AVPlayer(url: url))
    }

    var body: some View {
        VideoPlayer(player: player)
            .background(.black)
            .onDisappear { player.pause() }
    }
}

private struct KnownSpeciesAssignmentView: View {
    @ObservedObject var journal: JournalStore
    let photoID: String
    let hikeID: String

    @Environment(\.dismiss) private var dismiss
    @State private var query = ""
    @State private var assigningID: String?

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                if filtered.isEmpty {
                    ContentUnavailableView(
                        journal.species.isEmpty ? "Your Field Guide is empty" : "No species match",
                        systemImage: "leaf",
                        description: Text("Choose a species already confirmed in your Field Guide.")
                    )
                } else {
                    List(filtered, id: \.key) { species in
                        Button {
                            assign(species)
                        } label: {
                            HStack(spacing: 12) {
                                JournalRemoteImage(urlString: species.coverUrl, fallback: "leaf")
                                    .frame(width: 52, height: 52)
                                    .clipShape(Circle())
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(species.commonName.isEmpty ? species.scientificName : species.commonName)
                                        .font(HikeJournalTheme.label(16, relativeTo: .headline))
                                        .foregroundStyle(HikeJournalTheme.ink)
                                    Text("\(species.scientificName) · \(species.encounterCount) prior \(species.encounterCount == 1 ? "record" : "records")")
                                        .font(HikeJournalTheme.body(13))
                                        .foregroundStyle(HikeJournalTheme.inkMuted)
                                }
                                Spacer()
                                if assigningID == species.key { ProgressView() }
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .disabled(assigningID != nil)
                    }
                    .scrollContentBackground(.hidden)
                }
            }
            .navigationTitle("Assign known species")
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $query, prompt: "Common or scientific name")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
            }
            .task {
                if journal.species.isEmpty { await journal.refreshFieldGuide() }
            }
        }
    }

    private var filtered: [SpeciesRecord] {
        let clean = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { return journal.species }
        return journal.species.filter {
            $0.commonName.localizedCaseInsensitiveContains(clean)
                || $0.scientificName.localizedCaseInsensitiveContains(clean)
        }
    }

    private func assign(_ species: SpeciesRecord) {
        assigningID = species.key
        Task {
            let saved = await journal.assignKnownSpecies(
                photoID: photoID,
                hikeID: hikeID,
                species: species
            )
            if saved {
                await journal.loadHike(id: hikeID, force: true)
                dismiss()
            }
            assigningID = nil
        }
    }
}

private struct NaturalHistoryEditor: View {
    let species: SpeciesLabel
    let save: (String, [String]) async -> Bool

    @Environment(\.dismiss) private var dismiss
    @State private var confidence: String
    @State private var phenophases: Set<String>
    @State private var saving = false

    init(species: SpeciesLabel, save: @escaping (String, [String]) async -> Bool) {
        self.species = species
        self.save = save
        _confidence = State(initialValue: species.confidence)
        _phenophases = State(initialValue: Set(species.phenophases))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Identification confidence") {
                    Picker("Confidence", selection: $confidence) {
                        ForEach(confidenceOptions, id: \.value) { option in
                            Text(option.label).tag(option.value)
                        }
                    }
                    .pickerStyle(.inline)
                    .labelsHidden()
                }

                if species.iconicTaxonName.localizedCaseInsensitiveContains("plant") {
                    Section("Plant phenophase · optional") {
                        ForEach(phenophaseOptions, id: \.value) { option in
                            Toggle(option.label, isOn: Binding(
                                get: { phenophases.contains(option.value) },
                                set: { enabled in
                                    if enabled { phenophases.insert(option.value) }
                                    else { phenophases.remove(option.value) }
                                }
                            ))
                        }
                    }
                }

                Section {
                    Text("These labels describe this observation; they do not claim a species-wide season.")
                        .font(HikeJournalTheme.body(14))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }
            }
            .font(HikeJournalTheme.body())
            .scrollContentBackground(.hidden)
            .background(ParchmentBackground())
            .navigationTitle("Natural-history detail")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(saving ? "Saving…" : "Save") {
                        saving = true
                        Task {
                            if await save(confidence, phenophases.sorted()) { dismiss() }
                            saving = false
                        }
                    }
                    .disabled(saving)
                }
            }
        }
    }

    private let confidenceOptions = [
        (value: "tentative", label: "Tentative"),
        (value: "likely", label: "Likely"),
        (value: "confident", label: "Confident"),
        (value: "externally_confirmed", label: "Externally confirmed"),
    ]

    private let phenophaseOptions = [
        (value: "vegetative", label: "Vegetative"),
        (value: "budding", label: "Budding"),
        (value: "flowering", label: "Flowering"),
        (value: "fruiting", label: "Fruiting"),
        (value: "senescent", label: "Senescent"),
    ]
}

private func friendlyObservationConfidence(_ value: String) -> String {
    switch value.lowercased() {
    case "likely": "Likely"
    case "confident": "Confident"
    case "externally_confirmed": "Externally confirmed"
    default: "Tentative"
    }
}

private func friendlyObservationProvenance(_ value: String) -> String {
    switch value.lowercased() {
    case "user": "Your field note"
    case "known_species": "Known species"
    case "inat", "inaturalist", "inat_recommendation": "iNaturalist"
    case "manual": "Manual identification"
    case "legacy_import": "Earlier HikeJournal record"
    default: value.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

private func friendlyPhenophase(_ value: String) -> String {
    value.replacingOccurrences(of: "_", with: " ").capitalized
}

private struct WeatherSummaryView: View {
    let weather: WeatherSnapshot

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(weather.conditionLabel, systemImage: "cloud.sun.fill")
                .font(HikeJournalTheme.label(17, relativeTo: .headline))
                .foregroundStyle(HikeJournalTheme.moss)
            HStack(spacing: 26) {
                WeatherMetric(value: weather.temperatureMeanC.map { String(format: "%.0f°", $0 * 9 / 5 + 32) } ?? "—", label: "mean")
                WeatherMetric(value: weather.precipitationTotalMm.map { String(format: "%.2f in", $0 / 25.4) } ?? "—", label: "rain")
                WeatherMetric(value: weather.windSpeedMeanKph.map { String(format: "%.0f mph", $0 / 1.609) } ?? "—", label: "wind")
            }
            Text([weather.provider, weather.providerDataset].filter { !$0.isEmpty }.joined(separator: " · "))
                .font(HikeJournalTheme.body(12))
                .foregroundStyle(HikeJournalTheme.inkMuted)
        }
    }
}

private struct WeatherMetric: View {
    let value: String
    let label: String
    var body: some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(value).font(HikeJournalTheme.display(25, relativeTo: .title3))
            Text(label).font(HikeJournalTheme.body(12)).foregroundStyle(HikeJournalTheme.inkMuted)
        }
    }
}

private struct HikeComparisonSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var journal: JournalStore
    let hikeID: String
    @State private var otherID = ""
    @State private var comparison: HikeComparison?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Picker("Compare with", selection: $otherID) {
                        Text("Choose another hike").tag("")
                        ForEach(journal.hikes.filter { $0.id != hikeID && !$0.isArchived }) { hike in
                            Text("\(hike.title) · \(JournalDate.display(hike.hikeDate))").tag(hike.id)
                        }
                    }
                    .pickerStyle(.menu)

                    Button("Compare field pages") { load() }
                        .buttonStyle(TrailButtonStyle())
                        .disabled(otherID.isEmpty || isLoading)

                    if isLoading { ProgressView("Reading both field pages…") }
                    if let errorMessage { Text(errorMessage).foregroundStyle(HikeJournalTheme.error) }
                    if let comparison {
                        Text("\(comparison.hikeA.title) / \(comparison.hikeB.title)")
                            .font(HikeJournalTheme.display(31, relativeTo: .title))
                        HStack(spacing: 30) {
                            WeatherMetric(value: "\(comparison.shared.count)", label: "shared species")
                            WeatherMetric(value: "\(comparison.onlyA.count)", label: "only first")
                            WeatherMetric(value: "\(comparison.onlyB.count)", label: "only second")
                        }
                        if !comparison.guidance.isEmpty {
                            Text(comparison.guidance)
                                .font(HikeJournalTheme.body())
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                    }
                }
                .padding(22)
            }
            .background(ParchmentBackground())
            .navigationTitle("Compare hikes")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Done") { dismiss() } } }
        }
    }

    private func load() {
        guard !otherID.isEmpty else { return }
        isLoading = true
        errorMessage = nil
        Task {
            do {
                comparison = try await journal.comparison(hikeID: hikeID, otherHikeID: otherID).value
            } catch {
                errorMessage = (error as? LocalizedError)?.errorDescription ?? "Comparison is unavailable."
            }
            isLoading = false
        }
    }
}

struct JournalRemoteImage: View {
    let urlString: String
    let fallback: String

    var body: some View {
        AsyncImage(url: URL(string: urlString)) { phase in
            switch phase {
            case .success(let image): image.resizable().scaledToFill()
            case .empty: ZStack { Color(red: 0.12, green: 0.22, blue: 0.15); ProgressView().tint(.white) }
            case .failure: fallbackView
            @unknown default: fallbackView
            }
        }
    }

    private var fallbackView: some View {
        ZStack {
            LinearGradient(
                colors: [Color(red: 0.10, green: 0.24, blue: 0.16), Color(red: 0.30, green: 0.39, blue: 0.22)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            Image(systemName: fallback)
                .font(.system(size: 30, weight: .light))
                .foregroundStyle(Color(red: 0.92, green: 0.90, blue: 0.76))
        }
    }
}

private struct JournalSection<Content: View>: View {
    let title: String
    let actionTitle: String?
    let action: (() -> Void)?
    @ViewBuilder let content: Content

    init(
        title: String,
        actionTitle: String? = nil,
        action: (() -> Void)? = nil,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.actionTitle = actionTitle
        self.action = action
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(title)
                    .font(HikeJournalTheme.display(27, relativeTo: .title2))
                    .foregroundStyle(HikeJournalTheme.ink)
                Spacer()
                if let actionTitle, let action {
                    Button(actionTitle, action: action)
                        .font(HikeJournalTheme.label(15, relativeTo: .headline))
                        .foregroundStyle(HikeJournalTheme.trailText)
                }
            }
            Divider().overlay(HikeJournalTheme.line)
            content
        }
    }
}

private struct JournalRouteSketch: View {
    let segments: [[RoutePoint]]

    var body: some View {
        GeometryReader { proxy in
            let points = segments.flatMap { $0 }
            let minLat = points.map(\.latitude).min() ?? 0
            let maxLat = points.map(\.latitude).max() ?? 1
            let minLng = points.map(\.longitude).min() ?? 0
            let maxLng = points.map(\.longitude).max() ?? 1
            ZStack {
                Color(red: 0.07, green: 0.17, blue: 0.12)
                BrandLandscape().opacity(0.14)
                ForEach(Array(segments.enumerated()), id: \.offset) { _, segment in
                    Path { path in
                        for (index, point) in segment.enumerated() {
                            let x = 18 + normalized(point.longitude, min: minLng, max: maxLng) * (proxy.size.width - 36)
                            let y = 18 + (1 - normalized(point.latitude, min: minLat, max: maxLat)) * (proxy.size.height - 36)
                            if index == 0 { path.move(to: CGPoint(x: x, y: y)) }
                            else { path.addLine(to: CGPoint(x: x, y: y)) }
                        }
                    }
                    .stroke(HikeJournalTheme.trail, style: StrokeStyle(lineWidth: 4, lineCap: .round, lineJoin: .round))
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Recorded route")
        .accessibilityValue("\(segments.count) segments and \(segments.flatMap { $0 }.count) GPS points")
    }

    private func normalized(_ value: Double, min: Double, max: Double) -> CGFloat {
        guard max - min > 0.000_001 else { return 0.5 }
        return CGFloat((value - min) / (max - min))
    }
}

private struct JournalMediaError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

enum JournalDate {
    private static let apiFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    static func parse(_ value: String?) -> Date? {
        guard let value else { return nil }
        return apiFormatter.date(from: String(value.prefix(10)))
    }

    static func api(_ date: Date) -> String { apiFormatter.string(from: date) }

    static func display(_ value: String) -> String {
        guard let date = parse(value) else { return value }
        return date.formatted(date: .long, time: .omitted)
    }

    static func duration(_ seconds: Int64) -> String {
        let hours = seconds / 3_600
        let minutes = (seconds % 3_600) / 60
        return hours > 0 ? "\(hours)h \(minutes)m" : "\(minutes)m"
    }
}
