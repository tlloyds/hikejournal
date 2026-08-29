import AuthenticationServices
import HikeJournalDomain
import HikeJournalMaps
import SwiftUI
import UIKit

struct FieldGuideWorkspaceView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var journal: JournalStore
    @State private var section: FieldWorkspaceSection = .guide
    @State private var search = ""
    @State private var taxonFilter = "All"
    @State private var sort: SpeciesSort = .latest
    @StateObject private var oauth = INaturalistWebSession()

    init(model: AppModel, initialSection: FieldWorkspaceSection = .guide) {
        self.model = model
        _journal = ObservedObject(wrappedValue: model.journal)
        _section = State(initialValue: initialSection)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                if case .signedIn = model.authentication.phase {
                    workspace
                } else {
                    signedOut
                }
            }
            .navigationTitle(section.title)
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $search, prompt: section.searchPrompt)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Menu {
                        Picker("Field workspace", selection: $section) {
                            ForEach(FieldWorkspaceSection.allCases) { section in
                                Label(section.title, systemImage: section.symbol).tag(section)
                            }
                        }
                    } label: {
                        Label(section.title, systemImage: section.symbol)
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    if section == .guide {
                        Menu {
                            Picker("Species group", selection: $taxonFilter) {
                                ForEach(taxonFilters, id: \.self) { value in
                                    Text(fieldGuideTaxonLabel(value)).tag(value)
                                }
                            }
                            Picker("Sort", selection: $sort) {
                                ForEach(SpeciesSort.allCases) { sort in Text(sort.title).tag(sort) }
                            }
                        } label: {
                            Image(systemName: "line.3.horizontal.decrease.circle")
                        }
                        .accessibilityLabel("Filter and sort field guide")
                    } else {
                        Button {
                            Task { await refreshSection() }
                        } label: {
                            Image(systemName: "arrow.clockwise")
                        }
                        .accessibilityLabel("Refresh \(section.title)")
                    }
                }
            }
            .task(id: "\(model.selectedTab)-\(section.rawValue)") {
                // Keep the initial guide request isolated. The species,
                // sightings, review, and publishing endpoints all fan out to
                // the same large account dataset; firing them together makes
                // the server contend with duplicate work and leaves the guide
                // stuck behind unrelated sections.
                guard model.selectedTab == .fieldGuide else { return }
                switch section {
                case .guide, .sightings:
                    await journal.refreshFieldGuide()
                case .quests:
                    await journal.loadQuests()
                case .review, .publish:
                    await journal.loadReviewAndPublishing()
                case .discover:
                    break
                }
            }
            .refreshable { await refreshSection() }
            .alert(
                "Field Guide needs attention",
                isPresented: Binding(
                    get: { journal.fieldGuideErrorMessage != nil || journal.errorMessage != nil || oauth.errorMessage != nil },
                    set: {
                        if !$0 {
                            journal.clearFieldGuideError()
                            journal.clearError()
                            oauth.clearError()
                        }
                    }
                )
            ) {
                Button("OK") {
                    journal.clearFieldGuideError()
                    journal.clearError()
                    oauth.clearError()
                }
            } message: {
                Text(journal.fieldGuideErrorMessage ?? journal.errorMessage ?? oauth.errorMessage ?? "")
            }
        }
    }

    @ViewBuilder
    private var workspace: some View {
        switch section {
        case .guide:
            SpeciesGuideList(
                model: model,
                species: filteredSpecies,
                search: search
            )
        case .sightings:
            SightingsList(model: model, sightings: filteredSightings)
        case .discover:
            DiscoveryWorkspace(model: model, journal: journal, initialQuery: search)
        case .quests:
            QuestList(model: model, journal: journal, quests: filteredQuests)
        case .review:
            SpeciesReviewList(
                journal: journal,
                items: filteredReview,
                inatConnected: journal.publishQueue?.connected == true,
                onConnect: connectINaturalist
            )
        case .publish:
            PublishingWorkspace(
                journal: journal,
                queue: journal.publishQueue,
                oauth: oauth,
                callbackScheme: model.configuration.callbackScheme,
                handleCallback: model.handleDeepLink
            )
        }
    }

    private var signedOut: some View {
        VStack(alignment: .leading, spacing: 12) {
            Spacer()
            Image(systemName: "leaf.circle.fill")
                .font(.system(size: 62, weight: .light))
                .foregroundStyle(HikeJournalTheme.fern)
                .accessibilityHidden(true)
            Text("Your guide grows from your sightings.")
                .font(HikeJournalTheme.display(38, relativeTo: .largeTitle))
                .foregroundStyle(HikeJournalTheme.ink)
            Text("Sign in to browse confirmed species, discovery quests, review history, and iNaturalist publishing.")
                .font(HikeJournalTheme.body(18))
                .foregroundStyle(HikeJournalTheme.inkMuted)
            Spacer()
            Button("Open account") { model.openSettings() }
                .buttonStyle(TrailButtonStyle())
        }
        .padding(24)
    }

    private var filteredSpecies: [SpeciesRecord] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        let values = journal.species.filter { species in
            (taxonFilter == "All" || species.iconicTaxonName == taxonFilter)
                && (query.isEmpty
                    || species.commonName.localizedCaseInsensitiveContains(query)
                    || species.scientificName.localizedCaseInsensitiveContains(query))
        }
        return values.sorted { lhs, rhs in
            switch sort {
            case .latest:
                if lhs.latestSeen != rhs.latestSeen { return (lhs.latestSeen ?? "") > (rhs.latestSeen ?? "") }
            case .encounters:
                if lhs.encounterCount != rhs.encounterCount { return lhs.encounterCount > rhs.encounterCount }
            case .name:
                break
            }
            return lhs.commonName.localizedCaseInsensitiveCompare(rhs.commonName) == .orderedAscending
        }
    }

    private var filteredSightings: [Sighting] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return journal.sightings }
        return journal.sightings.filter {
            [$0.speciesName, $0.scientificName, $0.hikeTitle, $0.locationName, $0.caption]
                .contains { $0.localizedCaseInsensitiveContains(query) }
        }
    }

    private var filteredQuests: [FieldQuest] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return journal.quests }
        return journal.quests.filter {
            [$0.title, $0.areaName, $0.periodLabel, $0.iconicTaxon ?? ""]
                .contains { $0.localizedCaseInsensitiveContains(query) }
        }
    }

    private var filteredReview: [ReviewItem] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return journal.reviewItems }
        return journal.reviewItems.filter {
            [$0.hikeTitle, $0.locationName, $0.photo.caption]
                .contains { $0.localizedCaseInsensitiveContains(query) }
                || $0.candidates.contains {
                    $0.commonName.localizedCaseInsensitiveContains(query)
                        || $0.scientificName.localizedCaseInsensitiveContains(query)
                }
        }
    }

    private var taxonFilters: [String] {
        ["All"] + Set(journal.species.map(\.iconicTaxonName).filter { !$0.isEmpty }).sorted()
    }

    private func fieldGuideTaxonLabel(_ value: String) -> String {
        switch value.lowercased() {
        case "all": "All life"
        case "actinopterygii": "Fish"
        case "amphibia": "Amphibians"
        case "animalia": "Other animals"
        case "arachnida": "Arachnids"
        case "aves": "Birds"
        case "fungi": "Fungi"
        case "insecta": "Insects"
        case "mammalia": "Mammals"
        case "mollusca": "Mollusks"
        case "plantae": "Plants"
        case "protozoa": "Protozoans"
        case "reptilia": "Reptiles"
        default: value
        }
    }

    private func refreshSection() async {
        switch section {
        case .guide, .sightings: await journal.refreshFieldGuide()
        case .discover: break
        case .quests: await journal.loadQuests()
        case .review, .publish: await journal.loadReviewAndPublishing()
        }
    }

    private func connectINaturalist() {
        Task {
            do {
                let url = try await journal.inaturalistAuthorizationURL()
                oauth.start(url: url, callbackScheme: model.configuration.callbackScheme) { callback in
                    if let callback { _ = model.handleDeepLink(callback) }
                    Task { await journal.loadReviewAndPublishing() }
                }
            } catch {
                oauth.show(error)
            }
        }
    }
}

enum FieldWorkspaceSection: String, CaseIterable, Identifiable {
    case guide
    case sightings
    case discover
    case quests
    case review
    case publish

    var id: String { rawValue }
    var title: String {
        switch self {
        case .guide: "Field Guide"
        case .sightings: "Sightings"
        case .discover: "Discover"
        case .quests: "Field Quests"
        case .review: "Species Review"
        case .publish: "Publish"
        }
    }
    var symbol: String {
        switch self {
        case .guide: "leaf.fill"
        case .sightings: "binoculars.fill"
        case .discover: "sparkle.magnifyingglass"
        case .quests: "scope"
        case .review: "checkmark.seal"
        case .publish: "arrow.up.circle"
        }
    }
    var searchPrompt: String {
        switch self {
        case .guide: "Common or scientific name"
        case .sightings: "Species, place, or outing"
        case .discover: "Search a park or area"
        case .quests: "Search quests"
        case .review: "Search review queue"
        case .publish: "Search publishing queue"
        }
    }
}

private enum SpeciesSort: String, CaseIterable, Identifiable {
    case latest
    case encounters
    case name
    var id: String { rawValue }
    var title: String {
        switch self {
        case .latest: "Most recently seen"
        case .encounters: "Most encountered"
        case .name: "Name"
        }
    }
}

private func reviewConfidenceLabel(_ confidence: Double?) -> String? {
    guard let normalized = normalizedReviewConfidence(confidence) else { return nil }
    return "\(Int((normalized * 100).rounded()))% confidence"
}

private struct SpeciesGuideList: View {
    @ObservedObject var model: AppModel
    let species: [SpeciesRecord]
    let search: String

    var body: some View {
        if species.isEmpty {
            ContentUnavailableView {
                Label(search.isEmpty ? "Your field guide is waiting" : "No species match", systemImage: "leaf")
            } description: {
                Text(search.isEmpty
                     ? "Confirmed plants, animals, fungi, and other finds appear here."
                     : "Try another common name, scientific name, or group.")
            }
        } else {
            ScrollView {
                LazyVStack(spacing: 0) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("YOUR FIELD GUIDE")
                            .font(HikeJournalTheme.label(12))
                            .tracking(1.4)
                            .foregroundStyle(HikeJournalTheme.trailText)
                        Text("\(species.count) species, noticed over time")
                            .font(HikeJournalTheme.display(31, relativeTo: .title))
                            .foregroundStyle(HikeJournalTheme.ink)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(22)

                    ForEach(species, id: \.key) { species in
                        NavigationLink {
                            SpeciesDetailView(model: model, seed: species)
                        } label: {
                            SpeciesRow(species: species)
                        }
                        .buttonStyle(.plain)
                        Divider().overlay(HikeJournalTheme.line).padding(.leading, 22)
                    }
                }
                .padding(.bottom, 38)
            }
            .scrollIndicators(.hidden)
        }
    }
}

private struct SpeciesRow: View {
    let species: SpeciesRecord

    var body: some View {
        HStack(spacing: 15) {
            JournalRemoteImage(
                urlString: species.coverThumbnailUrl.isEmpty ? species.coverUrl : species.coverThumbnailUrl,
                fallback: iconicSymbol(species.iconicTaxonName)
            )
                .frame(width: 82, height: 82)
                .clipShape(Circle())
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 3) {
                Text(species.commonName)
                    .font(HikeJournalTheme.display(22, relativeTo: .title3))
                    .foregroundStyle(HikeJournalTheme.ink)
                if !species.scientificName.isEmpty {
                    Text(species.scientificName)
                        .font(HikeJournalTheme.body(14))
                        .italic()
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }
                Text("\(species.encounterCount) \(species.encounterCount == 1 ? "encounter" : "encounters") · \(species.hikeCount) \(species.hikeCount == 1 ? "outing" : "outings")")
                    .font(HikeJournalTheme.body(13))
                    .foregroundStyle(HikeJournalTheme.trailText)
                if let latest = species.latestSeen {
                    Text("Last seen \(JournalDate.display(latest))")
                        .font(HikeJournalTheme.body(12))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.caption.weight(.bold))
                .foregroundStyle(HikeJournalTheme.inkMuted.opacity(0.55))
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 13)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens species history")
    }
}

struct SpeciesDetailView: View {
    @ObservedObject var model: AppModel
    let seed: SpeciesRecord
    @State private var detail: SpeciesRecord?
    @State private var loading = false
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            ParchmentBackground()
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    speciesHero
                    VStack(alignment: .leading, spacing: 28) {
                        if !value.wikipediaSummary.isEmpty {
                            FieldSection(title: "Field notes") {
                                Text(value.wikipediaSummary)
                                    .font(HikeJournalTheme.body(17))
                                    .foregroundStyle(HikeJournalTheme.ink)
                            }
                        }
                        FieldSection(title: "Your history") {
                            HStack(spacing: 32) {
                                FieldMetric(value: "\(value.encounterCount)", label: "encounters")
                                FieldMetric(value: "\(value.hikeCount)", label: "outings")
                                FieldMetric(value: value.latestSeen.map(JournalDate.display) ?? "—", label: "latest")
                            }
                        }
                        if canSeePhenology {
                            SeasonalHistoryView(history: value.seasonalHistory)
                        } else {
                            PlusFeatureLine(
                                title: "Seasonal history",
                                detail: "Monthly patterns and phenophase history are included with Plus."
                            )
                        }
                        if !value.encounters.isEmpty {
                            FieldSection(title: "Encounters") {
                                ForEach(Array(value.encounters.enumerated()), id: \.offset) { _, encounter in
                                    HStack(spacing: 13) {
                                        JournalRemoteImage(urlString: encounter.photo.url, fallback: "photo")
                                            .frame(width: 68, height: 68)
                                            .clipped()
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(encounter.hikeTitle)
                                                .font(HikeJournalTheme.label(15, relativeTo: .headline))
                                            Text(JournalDate.display(encounter.observedOn ?? encounter.hikeDate))
                                                .font(HikeJournalTheme.body(13))
                                                .foregroundStyle(HikeJournalTheme.inkMuted)
                                            if !encounter.locationName.isEmpty {
                                                Text(encounter.locationName)
                                                    .font(HikeJournalTheme.body(13))
                                                    .foregroundStyle(HikeJournalTheme.inkMuted)
                                            }
                                        }
                                        Spacer()
                                    }
                                    .accessibilityElement(children: .combine)
                                }
                            }
                        }
                    }
                    .padding(22)
                    .padding(.bottom, 36)
                }
            }
            .scrollIndicators(.hidden)
            if loading { ProgressView().tint(HikeJournalTheme.trailText) }
        }
        .navigationTitle(value.commonName)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            loading = true
            do { detail = try await model.journal.speciesDetail(key: seed.key) }
            catch { errorMessage = (error as? LocalizedError)?.errorDescription ?? "Species detail is unavailable." }
            loading = false
        }
        .alert("Species detail unavailable", isPresented: Binding(
            get: { errorMessage != nil }, set: { if !$0 { errorMessage = nil } }
        )) { Button("OK") { errorMessage = nil } } message: { Text(errorMessage ?? "") }
    }

    private var value: SpeciesRecord { detail ?? seed }

    private var speciesHero: some View {
        ZStack(alignment: .bottomLeading) {
            JournalRemoteImage(urlString: value.coverUrl, fallback: iconicSymbol(value.iconicTaxonName))
                .frame(maxWidth: .infinity)
                .frame(height: 300)
                .clipped()
                .overlay {
                    LinearGradient(colors: [.clear, .black.opacity(0.76)], startPoint: .center, endPoint: .bottom)
                }
            VStack(alignment: .leading, spacing: 3) {
                Text(value.iconicTaxonName.uppercased())
                    .font(HikeJournalTheme.label(12))
                    .tracking(1.4)
                Text(value.commonName)
                    .font(HikeJournalTheme.display(39, relativeTo: .largeTitle))
                if !value.scientificName.isEmpty {
                    Text(value.scientificName).font(HikeJournalTheme.body(16)).italic()
                }
            }
            .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.92))
            .padding(22)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 300)
        .clipped()
    }

    private var canSeePhenology: Bool {
        model.authentication.entitlement?.allows("phenology_history") != false
    }
}

private struct SeasonalHistoryView: View {
    let history: SeasonalHistory

    var body: some View {
        FieldSection(title: "Seasonal history") {
            if history.months.isEmpty {
                Text("More confirmed observations are needed before a seasonal pattern appears.")
                    .font(HikeJournalTheme.body())
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            } else {
                HStack(alignment: .bottom, spacing: 5) {
                    ForEach(Array(history.months.enumerated()), id: \.offset) { _, month in
                        VStack(spacing: 5) {
                            RoundedRectangle(cornerRadius: 2)
                                .fill(HikeJournalTheme.fern.opacity(0.35 + 0.65 * min(1, max(0, month.relativeIntensity))))
                                .frame(height: 12 + 70 * min(1, max(0, month.relativeIntensity)))
                            Text(String(month.label.prefix(1)))
                                .font(HikeJournalTheme.body(10))
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                        .frame(maxWidth: .infinity)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(month.label), \(month.count) observations")
                    }
                }
                if !history.guidance.isEmpty {
                    Text(history.guidance)
                        .font(HikeJournalTheme.body(13))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }
            }
        }
    }
}

private struct SightingsList: View {
    @ObservedObject var model: AppModel
    let sightings: [Sighting]

    var body: some View {
        if sightings.isEmpty {
            ContentUnavailableView(
                "No mapped sightings yet",
                systemImage: "binoculars",
                description: Text("Confirmed, GPS-backed observations appear here and on the map.")
            )
        } else {
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(sightings) { sighting in
                        Group {
                            NavigationLink {
                                SightingPhotoViewer(sighting: sighting)
                            } label: { SightingRow(sighting: sighting) }
                        }
                        .buttonStyle(.plain)
                        Divider().overlay(HikeJournalTheme.line).padding(.leading, 22)
                    }
                }
                .padding(.bottom, 38)
            }
            .scrollIndicators(.hidden)
        }
    }
}

private struct SightingRow: View {
    let sighting: Sighting
    var body: some View {
        HStack(spacing: 15) {
            JournalRemoteImage(
                urlString: sighting.thumbnailUrl.isEmpty ? sighting.url : sighting.thumbnailUrl,
                fallback: "binoculars"
            )
                .frame(width: 88, height: 88)
                .clipped()
            VStack(alignment: .leading, spacing: 3) {
                Text(sighting.speciesName.isEmpty ? "Unidentified sighting" : sighting.speciesName)
                    .font(HikeJournalTheme.display(21, relativeTo: .title3))
                    .foregroundStyle(HikeJournalTheme.ink)
                if !sighting.scientificName.isEmpty {
                    Text(sighting.scientificName).font(HikeJournalTheme.body(13)).italic()
                }
                Text("\(sighting.hikeTitle) · \(JournalDate.display(sighting.hikeDate))")
                    .font(HikeJournalTheme.body(13))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                if let latitude = sighting.latitude, let longitude = sighting.longitude {
                    Label(String(format: "%.5f, %.5f", latitude, longitude), systemImage: "mappin")
                        .font(HikeJournalTheme.body(12))
                        .foregroundStyle(HikeJournalTheme.trailText)
                }
            }
            Spacer()
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 13)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
    }
}

private struct SightingPhotoViewer: View {
    let sighting: Sighting

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            Color(red: 0.06, green: 0.10, blue: 0.08).ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    JournalRemoteImage(urlString: sighting.url, fallback: "photo")
                        .scaledToFit()
                        .frame(maxWidth: .infinity, minHeight: 280)
                    VStack(alignment: .leading, spacing: 6) {
                        Text(sighting.speciesName.isEmpty ? "Unidentified sighting" : sighting.speciesName)
                            .font(HikeJournalTheme.display(30, relativeTo: .title))
                            .foregroundStyle(.white)
                        if !sighting.scientificName.isEmpty {
                            Text(sighting.scientificName)
                                .font(HikeJournalTheme.body(15))
                                .italic()
                                .foregroundStyle(Color.white.opacity(0.72))
                        }
                        Text("\(sighting.hikeTitle) · \(JournalDate.display(sighting.hikeDate))")
                            .font(HikeJournalTheme.body(14))
                            .foregroundStyle(Color.white.opacity(0.72))
                        if !sighting.locationName.isEmpty {
                            Text(sighting.locationName)
                                .font(HikeJournalTheme.body(14))
                                .foregroundStyle(Color.white.opacity(0.72))
                        }
                        if let latitude = sighting.latitude, let longitude = sighting.longitude {
                            Label(String(format: "%.5f, %.5f", latitude, longitude), systemImage: "mappin.and.ellipse")
                                .font(HikeJournalTheme.body(13))
                                .foregroundStyle(Color.white.opacity(0.62))
                        }
                        if !sighting.caption.isEmpty {
                            Divider().overlay(Color.white.opacity(0.20))
                            Text(sighting.caption)
                                .font(HikeJournalTheme.body(16))
                                .foregroundStyle(Color.white.opacity(0.86))
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 28)
                }
            }
            .scrollIndicators(.hidden)
        }
        .navigationTitle("Field photo")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Done") { dismiss() }
            }
        }
    }
}

private struct DiscoveryWorkspace: View {
    @ObservedObject var model: AppModel
    @ObservedObject var journal: JournalStore
    @State private var query: String
    @State private var selectedArea: DiscoveryArea?
    @State private var date = Date()
    @State private var radiusKM = 10
    @State private var iconicTaxon = "All"
    @State private var loading = false
    @State private var areaSearchLoading = false
    @State private var creatingQuest = false
    @State private var previewSelection: DiscoveryTaxonSelection?
    @State private var currentLatitude: Double?
    @State private var currentLongitude: Double?
    @State private var locationError: String?

    init(model: AppModel, journal: JournalStore, initialQuery: String) {
        self.model = model
        self.journal = journal
        _query = State(initialValue: initialQuery)
    }

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("WHAT SHOULD I LOOK FOR?")
                        .font(HikeJournalTheme.label(12))
                        .tracking(1.4)
                        .foregroundStyle(HikeJournalTheme.trailText)
                    Text("A living list for one place and season.")
                        .font(HikeJournalTheme.display(32, relativeTo: .title))
                        .foregroundStyle(HikeJournalTheme.ink)
                }

                HStack {
                    TextField("Park, preserve, or area", text: $query)
                        .submitLabel(.search)
                        .onSubmit { searchAreas() }
                    if areaSearchLoading { ProgressView().tint(HikeJournalTheme.trailText) }
                }
                .textFieldStyle(.roundedBorder)
                .task(id: query) {
                    let clean = query.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard currentLatitude == nil else { return }
                    guard clean.count >= 2 else {
                        areaSearchLoading = false
                        return
                    }
                    areaSearchLoading = true
                    try? await Task.sleep(for: .milliseconds(350))
                    guard !Task.isCancelled else { return }
                    await journal.searchDiscoveryAreas(query)
                    areaSearchLoading = false
                }

                Button {
                    useCurrentLocation()
                } label: {
                    Label("Use current location", systemImage: "location.fill")
                }
                .font(HikeJournalTheme.label(14, relativeTo: .headline))
                .foregroundStyle(HikeJournalTheme.trailText)

                if let locationError {
                    Text(locationError)
                        .font(HikeJournalTheme.body(13))
                        .foregroundStyle(HikeJournalTheme.error)
                }

                if currentLatitude != nil {
                    Label("Using your current location", systemImage: "location.fill")
                        .font(HikeJournalTheme.body(13))
                        .foregroundStyle(HikeJournalTheme.moss)
                }

                if selectedArea == nil {
                    ForEach(journal.discoveryAreas.prefix(6)) { area in
                        Button {
                            selectedArea = area
                            query = area.name
                            currentLatitude = nil
                            currentLongitude = nil
                        } label: {
                            HStack {
                                Image(systemName: "mappin.circle.fill")
                                VStack(alignment: .leading) {
                                    Text(area.name).font(HikeJournalTheme.label(15, relativeTo: .headline))
                                    Text(area.locationType).font(HikeJournalTheme.body(12))
                                }
                                Spacer()
                            }
                            .frame(minHeight: 44)
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(HikeJournalTheme.moss)
                    }
                }

                DatePicker("Hike date", selection: $date, displayedComponents: .date)
                Stepper("Within \(radiusKM) km", value: $radiusKM, in: 1...50)
                Picker("Group", selection: $iconicTaxon) {
                    ForEach(["All", "Plants", "Birds", "Mammals", "Reptiles", "Amphibians", "Insects", "Fungi"], id: \.self) {
                        Text($0).tag($0)
                    }
                }

                Button {
                    discover()
                } label: {
                    Label(loading ? "Looking nearby…" : "Build nearby guide", systemImage: "sparkle.magnifyingglass")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(TrailButtonStyle())
                .disabled((selectedArea == nil && currentLatitude == nil) || loading)

                if let nearby = journal.nearbySpecies {
                    Divider().overlay(HikeJournalTheme.line)
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(nearby.areaName)
                                .font(HikeJournalTheme.display(27, relativeTo: .title2))
                            Text("\(nearby.periodLabel) · \(nearby.progress.collectedCount) of \(nearby.progress.totalCount) already in your guide")
                                .font(HikeJournalTheme.body(13))
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                        Spacer()
                    }
                    Button(creatingQuest ? "Saving quest…" : "Save as Field Quest") {
                        saveQuest(nearby)
                    }
                    .buttonStyle(.bordered)
                    .tint(HikeJournalTheme.moss)
                    .disabled(creatingQuest)

                    ForEach(nearby.taxa) { taxon in
                        Button {
                            previewSelection = DiscoveryTaxonSelection(nearby: nearby, taxon: taxon)
                        } label: {
                            DiscoveryTaxonRow(taxon: taxon)
                        }
                        .buttonStyle(.plain)
                        Divider().overlay(HikeJournalTheme.line)
                    }
                    Text(nearby.sourceGuidance)
                        .font(HikeJournalTheme.body(12))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }
            }
            .padding(22)
            .padding(.bottom, 36)
        }
        .scrollIndicators(.hidden)
        .sheet(item: $previewSelection) { selection in
            DiscoveryTaxonDetailView(
                model: model,
                journal: journal,
                taxon: selection.taxon,
                sightingsRequest: {
                    try await journal.nearbySightings(
                        nearby: selection.nearby,
                        taxonID: selection.taxon.taxonId
                    )
                }
            )
        }
    }

    private func discover() {
        guard selectedArea != nil || currentLatitude != nil else { return }
        loading = true
        Task {
            await journal.discoverNearbySpecies(
                areaID: selectedArea?.id,
                date: JournalDate.api(date),
                radiusKM: radiusKM,
                iconicTaxa: iconicTaxon == "All" ? [] : [iconicTaxon],
                latitude: currentLatitude,
                longitude: currentLongitude,
                limit: 50
            )
            loading = false
        }
    }

    private func searchAreas() {
        areaSearchLoading = true
        Task {
            await journal.searchDiscoveryAreas(query)
            areaSearchLoading = false
        }
    }

    private func useCurrentLocation() {
        locationError = nil
        areaSearchLoading = false
        loading = true
        Task {
            do {
                let location = try await model.currentLocation()
                selectedArea = nil
                query = "Current location"
                currentLatitude = location.coordinate.latitude
                currentLongitude = location.coordinate.longitude
                await journal.discoverNearbySpecies(
                    areaID: nil,
                    date: JournalDate.api(date),
                    radiusKM: radiusKM,
                    iconicTaxa: iconicTaxon == "All" ? [] : [iconicTaxon],
                    latitude: currentLatitude,
                    longitude: currentLongitude,
                    limit: 50
                )
            } catch {
                locationError = (error as? LocalizedError)?.errorDescription ?? "HikeJournal couldn't read your current location."
            }
            loading = false
        }
    }

    private func saveQuest(_ nearby: NearbySpecies) {
        creatingQuest = true
        let draft = SpeciesQuestDraft(
            areaID: nearby.areaId,
            targetDate: nearby.targetDate,
            radiusKM: nearby.radiusKm,
            iconicTaxon: nearby.iconicTaxon,
            title: "\(nearby.areaName) · \(nearby.periodLabel)",
            linkedHikeID: nil,
            resultLimit: nearby.resultLimit
        )
        Task {
            _ = await journal.createQuest(draft)
            creatingQuest = false
        }
    }
}

private struct DiscoveryTaxonSelection: Identifiable {
    let nearby: NearbySpecies
    let taxon: DiscoveryTaxon

    var id: Int64 { taxon.id }
}

private struct DiscoveryTaxonRow: View {
    let taxon: DiscoveryTaxon
    var body: some View {
        HStack(spacing: 14) {
            JournalRemoteImage(urlString: taxon.referencePhoto?.url ?? "", fallback: iconicSymbol(taxon.iconicTaxonName))
                .frame(width: 72, height: 72)
                .clipShape(Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(taxon.commonName)
                    .font(HikeJournalTheme.display(20, relativeTo: .title3))
                Text(taxon.scientificName).font(HikeJournalTheme.body(12)).italic()
                Text(taxon.frequencyBand)
                    .font(HikeJournalTheme.body(12))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }
            Spacer()
            if taxon.collected {
                Image(systemName: "checkmark.seal.fill")
                    .foregroundStyle(HikeJournalTheme.fern)
                    .accessibilityLabel("Already in your guide")
            }
        }
        .padding(.vertical, 9)
        .accessibilityElement(children: .combine)
    }
}

private struct DiscoveryTaxonDetailView: View {
    @ObservedObject var model: AppModel
    @ObservedObject var journal: JournalStore
    let taxon: DiscoveryTaxon
    let sightingsRequest: () async throws -> QuestSightingsMap
    @Environment(\.dismiss) private var dismiss
    @State private var sightings: QuestSightingsMap?
    @State private var currentLocation: MapCurrentLocation?
    @State private var loadingSightings = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 18) {
                        JournalRemoteImage(
                            urlString: taxon.collectionPhotoUrl ?? taxon.referencePhoto?.url ?? "",
                            fallback: iconicSymbol(taxon.iconicTaxonName)
                        )
                        .frame(maxWidth: .infinity)
                        .frame(height: 260)
                        .clipped()

                        Text(taxon.commonName)
                            .font(HikeJournalTheme.display(34, relativeTo: .largeTitle))
                            .foregroundStyle(HikeJournalTheme.ink)
                        Text(taxon.scientificName)
                            .font(HikeJournalTheme.body(16))
                            .italic()
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                        if !taxon.matchReason.isEmpty {
                            Text(taxon.matchReason)
                                .font(HikeJournalTheme.body(15))
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                        if !taxon.wikipediaSummary.isEmpty {
                            Text(taxon.wikipediaSummary)
                                .font(HikeJournalTheme.body(16))
                                .foregroundStyle(HikeJournalTheme.ink)
                        }
                        if let url = URL(string: taxon.wikipediaUrl), !taxon.wikipediaUrl.isEmpty {
                            Link("Read species notes", destination: url)
                                .font(HikeJournalTheme.label(14, relativeTo: .headline))
                                .foregroundStyle(HikeJournalTheme.trailText)
                        }

                        Button {
                            loadSightings()
                        } label: {
                            Label(loadingSightings ? "Loading sightings…" : "View sightings", systemImage: "map")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(TrailButtonStyle())
                        .disabled(loadingSightings)

                        if let errorMessage {
                            Text(errorMessage)
                                .font(HikeJournalTheme.body(13))
                                .foregroundStyle(HikeJournalTheme.error)
                        }

                        if let sightings {
                            Text("\(sightings.mappedCount) mapped iNaturalist sightings")
                                .font(HikeJournalTheme.label(14, relativeTo: .headline))
                                .foregroundStyle(HikeJournalTheme.moss)
                            if let style = model.maps.style,
                               let surface = try? HikeJournalMapSurface(
                                   scene: mapScene(sightings),
                                   style: style,
                                   styleCredential: model.maps.styleCredential,
                                   cameraBehavior: .fitOnce
                               ) {
                                surface.frame(height: 340)
                            }
                            Text(sightings.sourceGuidance)
                                .font(HikeJournalTheme.body(12))
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                    }
                    .padding(22)
                    .padding(.bottom, 36)
                }
                .scrollIndicators(.hidden)
            }
            .navigationTitle("Species details")
            .navigationBarTitleDisplayMode(.inline)
            .task { await model.maps.start() }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } }
            }
        }
    }

    private func loadSightings() {
        loadingSightings = true
        errorMessage = nil
        Task {
            do {
                let result = try await sightingsRequest()
                sightings = result
                if let location = try? await model.currentLocation(),
                   let coordinate = try? GeoCoordinate(
                       latitude: location.coordinate.latitude,
                       longitude: location.coordinate.longitude
                   ) {
                    currentLocation = try? MapCurrentLocation(
                        coordinate: coordinate,
                        horizontalAccuracyMeters: max(0, location.horizontalAccuracy),
                        recordedAt: location.timestamp
                    )
                }
            } catch {
                errorMessage = (error as? LocalizedError)?.errorDescription ?? "iNaturalist sightings could not be loaded."
            }
            loadingSightings = false
        }
    }

    private func mapScene(_ result: QuestSightingsMap) -> MapScene {
        let points = result.sightings.compactMap { sighting -> MapPoint? in
            guard let coordinate = try? GeoCoordinate(
                latitude: sighting.latitude,
                longitude: sighting.longitude
            ) else { return nil }
            return try? MapPoint(
                id: "inat:\(sighting.id)",
                kind: .discovery,
                title: result.commonName,
                detail: sighting.placeGuess,
                coordinate: coordinate
            )
        }
        return MapScene(currentLocation: currentLocation, points: points)
    }
}

private struct QuestList: View {
    @ObservedObject var model: AppModel
    @ObservedObject var journal: JournalStore
    let quests: [FieldQuest]

    var body: some View {
        if quests.isEmpty {
            ContentUnavailableView(
                "No Field Quests yet",
                systemImage: "scope",
                description: Text("Build a nearby guide in Discover, then save it for your next outing.")
            )
        } else {
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(quests) { quest in
                        NavigationLink {
                            QuestDetailView(model: model, journal: journal, quest: quest)
                        } label: {
                            HStack(spacing: 15) {
                                ZStack {
                                    Circle().fill(HikeJournalTheme.fern.opacity(0.14))
                                    Image(systemName: "scope").foregroundStyle(HikeJournalTheme.moss)
                                }
                                .frame(width: 58, height: 58)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(quest.title).font(HikeJournalTheme.display(22, relativeTo: .title3))
                                    Text("\(quest.areaName) · \(quest.periodLabel)")
                                        .font(HikeJournalTheme.body(13))
                                        .foregroundStyle(HikeJournalTheme.inkMuted)
                                    Text("\(quest.progress.collectedCount) of \(quest.progress.totalCount) found")
                                        .font(HikeJournalTheme.label(12, relativeTo: .caption))
                                        .foregroundStyle(HikeJournalTheme.trailText)
                                }
                                Spacer()
                                Image(systemName: "chevron.right").font(.caption.weight(.bold))
                            }
                            .padding(.horizontal, 22)
                            .padding(.vertical, 14)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        Divider().overlay(HikeJournalTheme.line).padding(.leading, 22)
                    }
                }
                .padding(.bottom, 36)
            }
            .scrollIndicators(.hidden)
        }
    }
}

private struct QuestDetailView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var model: AppModel
    @ObservedObject var journal: JournalStore
    @State var quest: FieldQuest
    @State private var showingDelete = false
    @State private var previewTaxon: DiscoveryTaxon?

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 17) {
                Text(quest.areaName.uppercased())
                    .font(HikeJournalTheme.label(12)).tracking(1.3).foregroundStyle(HikeJournalTheme.trailText)
                Text(quest.title).font(HikeJournalTheme.display(36, relativeTo: .largeTitle))
                Text("\(quest.periodLabel) · within \(quest.radiusKm) km")
                    .font(HikeJournalTheme.body()).foregroundStyle(HikeJournalTheme.inkMuted)
                ProgressView(value: Double(quest.progress.collectedCount), total: Double(max(1, quest.progress.totalCount)))
                    .tint(HikeJournalTheme.fern)
                Text("\(quest.progress.remainingCount) still to notice")
                    .font(HikeJournalTheme.label(14, relativeTo: .subheadline))
                Divider().overlay(HikeJournalTheme.line)
                ForEach(quest.taxa) { taxon in
                    Button { previewTaxon = taxon } label: {
                        DiscoveryTaxonRow(taxon: taxon)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(22)
            .padding(.bottom, 36)
        }
        .background(ParchmentBackground())
        .navigationTitle("Field Quest")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button(quest.status == "completed" ? "Reopen" : "Mark complete") {
                        let next = quest.status == "completed" ? "active" : "completed"
                        Task {
                            if let updated = await journal.updateQuest(
                                id: quest.id,
                                update: SpeciesQuestUpdate(
                                    title: nil,
                                    status: next,
                                    linkedHikeID: nil,
                                    setLinkedHike: false,
                                    focusTaxonIDs: nil
                                )
                            ) { quest = updated }
                        }
                    }
                    Button("Delete quest", role: .destructive) { showingDelete = true }
                } label: { Image(systemName: "ellipsis.circle") }
            }
        }
        .confirmationDialog("Delete this Field Quest?", isPresented: $showingDelete) {
            Button("Delete quest", role: .destructive) {
                Task { if await journal.deleteQuest(id: quest.id) { dismiss() } }
            }
            Button("Cancel", role: .cancel) {}
        }
        .sheet(item: $previewTaxon) { taxon in
            DiscoveryTaxonDetailView(
                model: model,
                journal: journal,
                taxon: taxon,
                sightingsRequest: { try await journal.questSightings(questID: quest.id, taxonID: taxon.taxonId) }
            )
        }
    }
}

private struct SpeciesReviewList: View {
    @ObservedObject var journal: JournalStore
    let items: [ReviewItem]
    let inatConnected: Bool
    let onConnect: () -> Void
    @State private var managingGroups = false

    var body: some View {
        VStack(spacing: 0) {
            if waitingCount > 0 || journal.isReviewBatchWorking {
                VStack(alignment: .leading, spacing: 9) {
                    Text("SMART GROUPED IDENTIFICATION")
                        .font(HikeJournalTheme.label(11))
                        .tracking(1.1)
                        .foregroundStyle(HikeJournalTheme.trailText)
                    Text("Photos taken together can be read as one field encounter; unmatched photos stay individual.")
                        .font(HikeJournalTheme.body(14))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                    if let status = journal.reviewBatchStatus, journal.isReviewBatchWorking {
                        ProgressView(
                            value: Double(status.processedCount),
                            total: Double(max(1, status.totalPhotos))
                        )
                        .tint(HikeJournalTheme.trailText)
                        Text("Reading \(status.processedCount) of \(status.totalPhotos) photos")
                            .font(HikeJournalTheme.body(13))
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                    }
                    if journal.isReviewBatchWorking {
                        Button("Stop identification", role: .cancel) {
                            Task { await journal.cancelReviewBatch() }
                        }
                        .font(HikeJournalTheme.label(14, relativeTo: .subheadline))
                        .foregroundStyle(HikeJournalTheme.error)
                    }
                    if !inatConnected {
                        Button("Connect iNaturalist", action: onConnect)
                            .buttonStyle(TrailButtonStyle())
                    }
                    Button(journal.isReviewBatchWorking ? "Identification running…" : "Identify \(waitingCount) waiting photo\(waitingCount == 1 ? "" : "s")") {
                        Task { await journal.startReviewBatchRecommendations() }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(HikeJournalTheme.moss)
                    .disabled(journal.isReviewBatchWorking || waitingCount == 0 || !inatConnected)
                    if !journal.isReviewBatchWorking && waitingCount > 0 {
                        Button("Manage groups") { managingGroups = true }
                            .font(HikeJournalTheme.label(14, relativeTo: .subheadline))
                            .foregroundStyle(HikeJournalTheme.moss)
                    }
                }
                .padding(.horizontal, 22)
                .padding(.vertical, 16)
                Divider().overlay(HikeJournalTheme.line)
            }

            if items.isEmpty {
                VStack(spacing: 14) {
                    ContentUnavailableView(
                        "Review queue is clear",
                        systemImage: "checkmark.seal",
                        description: Text("Media queued for identification appears here with its identification provenance.")
                    )
                    if !inatConnected {
                        Button("Connect iNaturalist", action: onConnect)
                            .buttonStyle(TrailButtonStyle())
                    }
                }
                .padding(.bottom, 24)
            } else {
                SpeciesReviewCardDeck(
                    journal: journal,
                    items: items,
                    inatConnected: inatConnected,
                    onConnect: onConnect
                )
            }
        }
        .sheet(isPresented: $managingGroups) {
            ReviewGroupingPlanner(
                items: items.filter { $0.candidates.isEmpty },
                journal: journal
            ) {
                managingGroups = false
            }
        }
    }

    private var waitingCount: Int {
        items.filter { $0.candidates.isEmpty }.count
    }
}

private struct ReviewGroupingPlanner: View {
    let items: [ReviewItem]
    @ObservedObject var journal: JournalStore
    let close: () -> Void
    @State private var separatePhotoIDs: Set<String> = []

    private var proposedGroups: [ReviewPhotoGroup] {
        splitReviewPhotoGroups(
            buildReviewPhotoGroups(items),
            separatePhotoIds: separatePhotoIDs
        )
    }

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 18) {
                        Text("MANAGE GROUPS")
                            .font(HikeJournalTheme.label(11))
                            .tracking(1.1)
                            .foregroundStyle(HikeJournalTheme.trailText)
                        Text("Photos from the same outing can share one identification request. Split any photo that deserves its own suggestion.")
                            .font(HikeJournalTheme.body(15))
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                        Text("\(items.count) waiting · \(proposedGroups.count) identification request\(proposedGroups.count == 1 ? "" : "s")")
                            .font(HikeJournalTheme.label(14, relativeTo: .headline))
                            .foregroundStyle(HikeJournalTheme.moss)

                        ForEach(Array(proposedGroups.enumerated()), id: \.offset) { index, group in
                            VStack(alignment: .leading, spacing: 10) {
                                Text(group.items.count > 1 ? "Group \(index + 1) · \(group.items.count) photos" : "Individual photo")
                                    .font(HikeJournalTheme.label(14, relativeTo: .headline))
                                ForEach(group.items) { item in
                                    HStack(spacing: 10) {
                                        JournalRemoteImage(urlString: item.photo.url, fallback: "photo")
                                            .frame(width: 52, height: 52)
                                            .clipped()
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(item.hikeTitle)
                                                .font(HikeJournalTheme.body(13))
                                            Text(JournalDate.display(item.hikeDate))
                                                .font(HikeJournalTheme.body(12))
                                                .foregroundStyle(HikeJournalTheme.inkMuted)
                                        }
                                        Spacer()
                                        if group.items.count > 1 {
                                            Button(separatePhotoIDs.contains(item.id) ? "Keep grouped" : "Split") {
                                                if separatePhotoIDs.contains(item.id) {
                                                    separatePhotoIDs.remove(item.id)
                                                } else {
                                                    separatePhotoIDs.insert(item.id)
                                                }
                                            }
                                            .font(HikeJournalTheme.label(12, relativeTo: .caption))
                                            .foregroundStyle(HikeJournalTheme.trailText)
                                        }
                                    }
                                }
                            }
                            .padding(14)
                            .background(HikeJournalTheme.paper.opacity(0.72))
                            .overlay(RoundedRectangle(cornerRadius: 12).stroke(HikeJournalTheme.line))
                        }
                    }
                    .padding(22)
                    .padding(.bottom, 36)
                }
            }
            .navigationTitle("Review groups")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("Cancel") { close() } }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Identify") {
                        Task {
                            await journal.startReviewBatchRecommendations(groups: proposedGroups.map(\.photoIds))
                            close()
                        }
                    }
                    .disabled(journal.isReviewBatchWorking || proposedGroups.isEmpty)
                }
            }
        }
    }
}

private struct SpeciesReviewCardDeck: View {
    @ObservedObject var journal: JournalStore
    let items: [ReviewItem]
    let inatConnected: Bool
    let onConnect: () -> Void
    @State private var selectedID: String

    init(
        journal: JournalStore,
        items: [ReviewItem],
        inatConnected: Bool,
        onConnect: @escaping () -> Void
    ) {
        self.journal = journal
        self.items = items
        self.inatConnected = inatConnected
        self.onConnect = onConnect
        _selectedID = State(initialValue: items.first?.id ?? "")
    }

    var body: some View {
        VStack(spacing: 8) {
            if items.count > 1 {
                Text("Swipe left or right to move through photos")
                    .font(HikeJournalTheme.label(13, relativeTo: .subheadline))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                    .padding(.top, 8)
            }

            TabView(selection: $selectedID) {
                ForEach(items) { item in
                    ReviewCardPage(
                        journal: journal,
                        item: item,
                        inatConnected: inatConnected,
                        onConnect: onConnect,
                        position: position(of: item),
                        total: items.count,
                        onAdvance: advance
                    )
                    .tag(item.id)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: items.count > 1 ? .automatic : .never))
            .frame(maxWidth: .infinity, minHeight: 590, maxHeight: .infinity)
        }
        .onAppear { syncSelection() }
        .onChange(of: itemIDs) { _, _ in syncSelection() }
    }

    private var itemIDs: [String] { items.map(\.id) }

    private func position(of item: ReviewItem) -> Int {
        (items.firstIndex(where: { $0.id == item.id }) ?? 0) + 1
    }

    private func syncSelection() {
        if !itemIDs.contains(selectedID) {
            selectedID = itemIDs.first ?? ""
        }
    }

    private func advance(after id: String) {
        guard let index = items.firstIndex(where: { $0.id == id }) else { return }
        if index < items.index(before: items.endIndex) {
            selectedID = items[index + 1].id
        } else if index > items.startIndex {
            selectedID = items[index - 1].id
        }
    }
}

private struct ReviewCardPage: View {
    @ObservedObject var journal: JournalStore
    let item: ReviewItem
    let inatConnected: Bool
    let onConnect: () -> Void
    let position: Int
    let total: Int
    let onAdvance: (String) -> Void
    @State private var working = false
    @State private var recommendationTask: Task<Void, Never>?
    @State private var selectedCandidateIndex = 0

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                ZStack(alignment: .bottomLeading) {
                    JournalRemoteImage(urlString: item.photo.url, fallback: "photo")
                        .frame(height: 292)
                        .clipped()
                        .overlay {
                            LinearGradient(
                                colors: [.clear, HikeJournalTheme.moss.opacity(0.88)],
                                startPoint: .center,
                                endPoint: .bottom
                            )
                        }
                    VStack(alignment: .leading, spacing: 3) {
                        Text("PHOTO \(position) OF \(total)")
                            .font(HikeJournalTheme.label(11))
                            .tracking(1.1)
                        Text(item.hikeTitle)
                            .font(HikeJournalTheme.display(28, relativeTo: .title2))
                            .lineLimit(2)
                        Text(item.locationName.isEmpty ? JournalDate.display(item.hikeDate) : item.locationName)
                            .font(HikeJournalTheme.body(14))
                            .lineLimit(1)
                    }
                    .foregroundStyle(HikeJournalTheme.paper)
                    .padding(18)
                }

                VStack(alignment: .leading, spacing: 14) {
                    if item.candidates.isEmpty {
                        waitingContent
                    } else {
                        candidateContent
                    }
                }
                .padding(18)
            }
            .background(HikeJournalTheme.paper)
            .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .stroke(HikeJournalTheme.line, lineWidth: 1)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
        }
        .onDisappear { recommendationTask?.cancel() }
        .onChange(of: item.candidates.count) { _, count in
            selectedCandidateIndex = min(selectedCandidateIndex, max(0, count - 1))
        }
    }

    @ViewBuilder
    private var waitingContent: some View {
        Text("Awaiting a suggestion")
            .font(HikeJournalTheme.display(27, relativeTo: .title2))
            .foregroundStyle(HikeJournalTheme.ink)
        Text("Ask iNaturalist for a field identification, or swipe to keep moving through the queue.")
            .font(HikeJournalTheme.body(15))
            .foregroundStyle(HikeJournalTheme.inkMuted)

        if working {
            Button("Stop asking", role: .cancel) {
                recommendationTask?.cancel()
                recommendationTask = nil
                working = false
            }
            .buttonStyle(.borderedProminent)
            .tint(HikeJournalTheme.moss)
        } else if inatConnected {
            Button {
                working = true
                recommendationTask = Task { @MainActor in
                    defer {
                        working = false
                        recommendationTask = nil
                    }
                    _ = await journal.requestReviewRecommendation(photoID: item.photo.id)
                }
            } label: {
                Label("Ask iNaturalist for suggestions", systemImage: "sparkle.magnifyingglass")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(TrailButtonStyle())
        } else {
            Button("Connect iNaturalist", action: onConnect)
                .buttonStyle(TrailButtonStyle())
        }

        HStack(spacing: 10) {
            Button {
                onAdvance(item.id)
            } label: {
                Label("Skip", systemImage: "forward.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .disabled(working || !hasNext)

            removeButton
        }
    }

    @ViewBuilder
    private var candidateContent: some View {
        Text("Choose the best match")
            .font(HikeJournalTheme.display(27, relativeTo: .title2))
            .foregroundStyle(HikeJournalTheme.ink)
        Text("The first option is iNaturalist’s current suggestion.")
            .font(HikeJournalTheme.body(15))
            .foregroundStyle(HikeJournalTheme.inkMuted)

        ForEach(Array(item.candidates.prefix(5).enumerated()), id: \.offset) { index, candidate in
            Button {
                selectedCandidateIndex = index
            } label: {
                HStack(alignment: .top, spacing: 11) {
                    Image(systemName: selectedCandidateIndex == index ? "checkmark.circle.fill" : "circle")
                        .foregroundStyle(selectedCandidateIndex == index ? HikeJournalTheme.moss : HikeJournalTheme.inkMuted)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(candidate.commonName.isEmpty ? candidate.scientificName : candidate.commonName)
                            .font(HikeJournalTheme.label(16, relativeTo: .headline))
                            .foregroundStyle(HikeJournalTheme.ink)
                        if !candidate.scientificName.isEmpty {
                            Text(candidate.scientificName)
                                .font(HikeJournalTheme.body(13))
                                .italic()
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                        if let confidence = reviewConfidenceLabel(candidate.confidence) {
                            Text(confidence)
                                .font(HikeJournalTheme.body(12))
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                    }
                    Spacer(minLength: 0)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(working)
        }

        Button {
            guard item.candidates.indices.contains(selectedCandidateIndex) else { return }
            decide(action: "confirm", candidate: item.candidates[selectedCandidateIndex])
        } label: {
            Label("\(selectedCandidateIndex == 0 ? "Confirm ID" : "Use this ID")", systemImage: "checkmark")
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(TrailButtonStyle())
        .disabled(working || item.candidates.isEmpty)

        HStack(spacing: 10) {
            Button("Reject suggestion", role: .destructive) {
                decide(action: "reject", candidate: nil)
            }
            .frame(maxWidth: .infinity)
            .buttonStyle(.bordered)
            .disabled(working)

            Button {
                onAdvance(item.id)
            } label: {
                Label("Skip", systemImage: "forward.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .disabled(working || !hasNext)
        }
        removeButton
    }

    private var hasNext: Bool { position < total }

    private var removeButton: some View {
        Button {
            removeFromReview()
        } label: {
            Label("Remove from review", systemImage: "xmark.circle")
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.bordered)
        .tint(HikeJournalTheme.error)
        .disabled(working || journal.isReviewBatchWorking)
    }

    private func decide(action: String, candidate: ReviewCandidate?) {
        working = true
        Task {
            let saved = await journal.decideReview(
                photoID: item.photo.id,
                observationID: item.observationId,
                action: action,
                candidate: candidate
            )
            working = false
            if saved { onAdvance(item.id) }
        }
    }

    private func removeFromReview() {
        guard !working else { return }
        working = true
        Task {
            let saved = await journal.queueSpeciesReview(
                photoID: item.photo.id,
                hikeID: item.hikeId ?? "everyday",
                queued: false
            )
            working = false
            if saved { onAdvance(item.id) }
        }
    }
}

private struct PublishingWorkspace: View {
    @ObservedObject var journal: JournalStore
    let queue: PublishQueue?
    @ObservedObject var oauth: INaturalistWebSession
    let callbackScheme: String
    let handleCallback: (URL) -> Bool
    @State private var bulkGeoprivacy = "open"
    @State private var showingBulkPublishConfirmation = false

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("INATURALIST")
                        .font(HikeJournalTheme.label(12)).tracking(1.4).foregroundStyle(HikeJournalTheme.trailText)
                    Text(queue?.connected == true ? "Confirmed sightings, ready to share." : "Connect before publishing.")
                        .font(HikeJournalTheme.display(32, relativeTo: .title))
                    Text("Publishing makes the selected observation and its location public according to your geoprivacy choice.")
                        .font(HikeJournalTheme.body(15)).foregroundStyle(HikeJournalTheme.inkMuted)
                }

                if queue?.connected != true {
                    Button(oauth.isAuthenticating ? "Connecting…" : "Connect iNaturalist") {
                        connect()
                    }
                    .buttonStyle(TrailButtonStyle())
                    .disabled(oauth.isAuthenticating)
                }

                if let queue {
                    HStack(spacing: 30) {
                        FieldMetric(value: "\(queue.readyCount)", label: "ready")
                        FieldMetric(value: "\(queue.needsAttentionCount)", label: "attention")
                        FieldMetric(value: "\(queue.postedCount)", label: "posted")
                    }
                    Divider().overlay(HikeJournalTheme.line)

                    if queue.connected && (queue.readyCount > 0 || journal.isPublishBatchWorking) {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("PUBLISH READY OBSERVATIONS")
                                .font(HikeJournalTheme.label(11))
                                .tracking(1.1)
                                .foregroundStyle(HikeJournalTheme.trailText)
                            Text("Share every ready, confirmed field encounter with one location-privacy choice.")
                                .font(HikeJournalTheme.body(14))
                                .foregroundStyle(HikeJournalTheme.inkMuted)

                            if let status = journal.publishBatchStatus, journal.isPublishBatchWorking {
                                ProgressView(
                                    value: Double(status.processedPhotoCount),
                                    total: Double(max(1, status.totalPhotos))
                                )
                                .tint(HikeJournalTheme.trailText)
                                Text("Published \(status.processedPhotoCount) of \(status.totalPhotos) photos")
                                    .font(HikeJournalTheme.body(13))
                                    .foregroundStyle(HikeJournalTheme.inkMuted)
                            }
                            if journal.isPublishBatchWorking {
                                Button("Stop publishing", role: .cancel) {
                                    Task { await journal.cancelPublishBatch() }
                                }
                                .font(HikeJournalTheme.label(14, relativeTo: .subheadline))
                                .foregroundStyle(HikeJournalTheme.error)
                            }

                            Picker("Location privacy", selection: $bulkGeoprivacy) {
                                Text("Open location").tag("open")
                                Text("Obscured location").tag("obscured")
                                Text("Private location").tag("private")
                            }
                            .pickerStyle(.menu)
                            .disabled(journal.isPublishBatchWorking)

                            Button(journal.isPublishBatchWorking ? "Publishing observations…" : "Publish \(queue.readyCount) ready observation\(queue.readyCount == 1 ? "" : "s")") {
                                showingBulkPublishConfirmation = true
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(HikeJournalTheme.moss)
                            .disabled(journal.isPublishBatchWorking || queue.readyCount == 0)
                        }
                        .padding(.vertical, 2)
                        Divider().overlay(HikeJournalTheme.line)
                    }

                    ForEach(queue.items) { item in
                        PublishItemView(journal: journal, item: item, connected: queue.connected)
                        Divider().overlay(HikeJournalTheme.line)
                    }
                }
            }
            .padding(22)
            .padding(.bottom, 36)
        }
        .scrollIndicators(.hidden)
        .confirmationDialog(
            "Publish \(queue?.readyCount ?? 0) confirmed observation\((queue?.readyCount ?? 0) == 1 ? "" : "s")?",
            isPresented: $showingBulkPublishConfirmation,
            titleVisibility: .visible
        ) {
            Button("Publish publicly with \(bulkPrivacyLabel)") {
                Task {
                    await journal.startPublishBatch(
                        options: PublishOptions(
                            observationIds: [],
                            geoprivacy: bulkGeoprivacy
                        )
                    )
                }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This sends every ready observation and its selected photos to iNaturalist. Location visibility will be \(bulkPrivacyLabel.lowercased()).")
        }
    }

    private var bulkPrivacyLabel: String {
        switch bulkGeoprivacy {
        case "private": "Private"
        case "obscured": "Obscured"
        default: "Open"
        }
    }

    private func connect() {
        Task {
            do {
                let url = try await journal.inaturalistAuthorizationURL()
                oauth.start(url: url, callbackScheme: callbackScheme) { callback in
                    if let callback { _ = handleCallback(callback) }
                    Task { await journal.loadReviewAndPublishing() }
                }
            } catch {
                oauth.show(error)
            }
        }
    }
}

private struct PublishItemView: View {
    @ObservedObject var journal: JournalStore
    let item: PublishItem
    let connected: Bool
    @State private var working = false
    @State private var publishTask: Task<Void, Never>?
    @State private var geoprivacy = "open"

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            JournalRemoteImage(urlString: item.photo.url, fallback: "photo")
                .frame(width: 92, height: 92)
                .clipped()
            VStack(alignment: .leading, spacing: 4) {
                Text(item.commonName).font(HikeJournalTheme.display(21, relativeTo: .title3))
                Text(item.scientificName).font(HikeJournalTheme.body(12)).italic()
                Text(item.hikeTitle).font(HikeJournalTheme.body(12)).foregroundStyle(HikeJournalTheme.inkMuted)
                if item.state == "posted", let url = URL(string: item.inatUrl) {
                    Link("View on iNaturalist", destination: url)
                        .font(HikeJournalTheme.label(13, relativeTo: .subheadline))
                } else {
                    Menu {
                        Picker("Geoprivacy", selection: $geoprivacy) {
                            Text("Open location").tag("open")
                            Text("Obscured location").tag("obscured")
                            Text("Private location").tag("private")
                        }
                    } label: {
                        Label(geoprivacy.capitalized, systemImage: "location.shield")
                    }
                    .font(HikeJournalTheme.body(12))
                    .disabled(journal.isPublishBatchWorking)
                    if working {
                        Button("Stop publishing", role: .cancel) {
                            publishTask?.cancel()
                            publishTask = nil
                            working = false
                        }
                        .font(HikeJournalTheme.label(13, relativeTo: .subheadline))
                    } else {
                        Button("Publish") {
                            working = true
                            publishTask = Task { @MainActor in
                                defer {
                                    working = false
                                    publishTask = nil
                                }
                                _ = await journal.publishObservation(
                                    id: item.id,
                                    options: PublishOptions(
                                        observationIds: [item.id],
                                        geoprivacy: geoprivacy
                                    )
                                )
                            }
                        }
                        .font(HikeJournalTheme.label(13, relativeTo: .subheadline))
                        .disabled(!connected || journal.isPublishBatchWorking)
            }
        }
    }
            Spacer()
        }
        .accessibilityElement(children: .combine)
        .onDisappear { publishTask?.cancel() }
    }
}

private struct FieldSection<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content
    init(title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(HikeJournalTheme.display(27, relativeTo: .title2))
            Divider().overlay(HikeJournalTheme.line)
            content
        }
    }
}

private struct FieldMetric: View {
    let value: String
    let label: String
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value).font(HikeJournalTheme.display(25, relativeTo: .title3)).lineLimit(1).minimumScaleFactor(0.65)
            Text(label).font(HikeJournalTheme.body(12)).foregroundStyle(HikeJournalTheme.inkMuted)
        }
    }
}

private struct PlusFeatureLine: View {
    let title: String
    let detail: String
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Label(title, systemImage: "sparkles")
                .font(HikeJournalTheme.label(16, relativeTo: .headline))
                .foregroundStyle(HikeJournalTheme.moss)
            Text(detail).font(HikeJournalTheme.body(14)).foregroundStyle(HikeJournalTheme.inkMuted)
        }
    }
}

@MainActor
final class INaturalistWebSession: NSObject, ObservableObject, ASWebAuthenticationPresentationContextProviding {
    @Published private(set) var isAuthenticating = false
    @Published private(set) var errorMessage: String?
    private var session: ASWebAuthenticationSession?

    func start(url: URL, callbackScheme: String, completion: @escaping (URL?) -> Void) {
        guard !isAuthenticating else { return }
        errorMessage = nil
        isAuthenticating = true
        let session = ASWebAuthenticationSession(url: url, callbackURLScheme: callbackScheme) { [weak self] url, error in
            Task { @MainActor [weak self] in
                guard let self else { return }
                self.isAuthenticating = false
                self.session = nil
                if let webError = error as? ASWebAuthenticationSessionError,
                   webError.code == .canceledLogin {
                    completion(nil)
                    return
                }
                if let error {
                    self.errorMessage = (error as? LocalizedError)?.errorDescription
                        ?? "iNaturalist connection did not finish."
                    completion(nil)
                    return
                }
                completion(url)
            }
        }
        session.presentationContextProvider = self
        session.prefersEphemeralWebBrowserSession = false
        self.session = session
        if !session.start() {
            isAuthenticating = false
            self.session = nil
            errorMessage = "HikeJournal could not open the secure iNaturalist sign-in session."
        }
    }

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap(\.windows)
            .first(where: \.isKeyWindow)
            ?? ASPresentationAnchor()
    }

    func show(_ error: Error) {
        errorMessage = (error as? LocalizedError)?.errorDescription
            ?? "HikeJournal could not begin iNaturalist sign-in."
    }

    func clearError() { errorMessage = nil }
}

private func iconicSymbol(_ value: String) -> String {
    switch value.lowercased() {
    case let text where text.contains("bird"): "bird.fill"
    case let text where text.contains("mammal"): "hare.fill"
    case let text where text.contains("plant"): "leaf.fill"
    case let text where text.contains("insect"): "ant.fill"
    case let text where text.contains("fish"): "fish.fill"
    case let text where text.contains("fung"): "circle.hexagongrid.fill"
    default: "sparkle"
    }
}
