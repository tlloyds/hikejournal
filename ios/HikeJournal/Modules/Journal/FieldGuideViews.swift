import AuthenticationServices
import HikeJournalDomain
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

    init(model: AppModel) {
        self.model = model
        _journal = ObservedObject(wrappedValue: model.journal)
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
                                ForEach(taxonFilters, id: \.self) { Text($0).tag($0) }
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
                    get: { journal.fieldGuideErrorMessage != nil || oauth.errorMessage != nil },
                    set: {
                        if !$0 {
                            journal.clearFieldGuideError()
                            oauth.clearError()
                        }
                    }
                )
            ) {
                Button("OK") {
                    journal.clearFieldGuideError()
                    oauth.clearError()
                }
            } message: {
                Text(journal.fieldGuideErrorMessage ?? oauth.errorMessage ?? "")
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
            DiscoveryWorkspace(journal: journal, initialQuery: search)
        case .quests:
            QuestList(journal: journal, quests: filteredQuests)
        case .review:
            SpeciesReviewList(journal: journal, items: filteredReview)
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
            Button("Open account") { model.selectedTab = .settings }
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

    private func refreshSection() async {
        switch section {
        case .guide, .sightings: await journal.refreshFieldGuide()
        case .discover: break
        case .quests: await journal.loadQuests()
        case .review, .publish: await journal.loadReviewAndPublishing()
        }
    }
}

private enum FieldWorkspaceSection: String, CaseIterable, Identifiable {
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
            JournalRemoteImage(urlString: species.coverUrl, fallback: iconicSymbol(species.iconicTaxonName))
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
                            if let hikeID = sighting.hikeId {
                                NavigationLink {
                                    JournalHikeDetailView(model: model, hikeID: hikeID)
                                } label: { SightingRow(sighting: sighting) }
                            } else {
                                SightingRow(sighting: sighting)
                            }
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
            JournalRemoteImage(urlString: sighting.url, fallback: "binoculars")
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
                Label(String(format: "%.5f, %.5f", sighting.latitude, sighting.longitude), systemImage: "mappin")
                    .font(HikeJournalTheme.body(12))
                    .foregroundStyle(HikeJournalTheme.trailText)
            }
            Spacer()
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 13)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
    }
}

private struct DiscoveryWorkspace: View {
    @ObservedObject var journal: JournalStore
    @State private var query: String
    @State private var selectedArea: DiscoveryArea?
    @State private var date = Date()
    @State private var radiusKM = 10
    @State private var iconicTaxon = "All"
    @State private var loading = false
    @State private var creatingQuest = false

    init(journal: JournalStore, initialQuery: String) {
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

                TextField("Park, preserve, or area", text: $query)
                    .textFieldStyle(.roundedBorder)
                    .task(id: query) {
                        try? await Task.sleep(for: .milliseconds(350))
                        guard !Task.isCancelled else { return }
                        await journal.searchDiscoveryAreas(query)
                    }

                if selectedArea == nil {
                    ForEach(journal.discoveryAreas.prefix(6)) { area in
                        Button {
                            selectedArea = area
                            query = area.name
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

                DatePicker("Season around", selection: $date, displayedComponents: .date)
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
                .disabled(selectedArea == nil || loading)

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
                        DiscoveryTaxonRow(taxon: taxon)
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
    }

    private func discover() {
        guard let selectedArea else { return }
        loading = true
        Task {
            await journal.discoverNearbySpecies(
                areaID: selectedArea.id,
                date: JournalDate.api(date),
                radiusKM: radiusKM,
                iconicTaxa: iconicTaxon == "All" ? [] : [iconicTaxon],
                limit: 50
            )
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

private struct QuestList: View {
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
                            QuestDetailView(journal: journal, quest: quest)
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
    @ObservedObject var journal: JournalStore
    @State var quest: FieldQuest
    @State private var showingDelete = false

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
                ForEach(quest.taxa) { taxon in DiscoveryTaxonRow(taxon: taxon) }
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
    }
}

private struct SpeciesReviewList: View {
    @ObservedObject var journal: JournalStore
    let items: [ReviewItem]

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
                    Button(journal.isReviewBatchWorking ? "Identification running…" : "Identify \(waitingCount) waiting photo\(waitingCount == 1 ? "" : "s")") {
                        Task { await journal.startReviewBatchRecommendations() }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(HikeJournalTheme.moss)
                    .disabled(journal.isReviewBatchWorking || waitingCount == 0)
                }
                .padding(.horizontal, 22)
                .padding(.vertical, 16)
                Divider().overlay(HikeJournalTheme.line)
            }

            if items.isEmpty {
                ContentUnavailableView(
                    "Review queue is clear",
                    systemImage: "checkmark.seal",
                    description: Text("Media queued for identification appears here with provenance and confidence.")
                )
            } else {
                ScrollView {
                    LazyVStack(spacing: 18) {
                        ForEach(items) { item in
                            ReviewItemView(journal: journal, item: item)
                            Divider().overlay(HikeJournalTheme.line)
                        }
                    }
                    .padding(22)
                    .padding(.bottom, 36)
                }
                .scrollIndicators(.hidden)
            }
        }
    }

    private var waitingCount: Int {
        items.filter { $0.candidates.isEmpty }.count
    }
}

private struct ReviewItemView: View {
    @ObservedObject var journal: JournalStore
    let item: ReviewItem
    @State private var working = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            JournalRemoteImage(urlString: item.photo.url, fallback: "photo")
                .frame(height: 220)
                .clipped()
            Text(item.hikeTitle).font(HikeJournalTheme.display(24, relativeTo: .title3))
            Text("\(JournalDate.display(item.hikeDate)) · \(item.locationName)")
                .font(HikeJournalTheme.body(13)).foregroundStyle(HikeJournalTheme.inkMuted)
            if item.candidates.isEmpty {
                Button(working ? "Requesting…" : "Ask iNaturalist for suggestions") {
                    working = true
                    Task {
                        _ = await journal.requestReviewRecommendation(photoID: item.photo.id)
                        working = false
                    }
                }
                .buttonStyle(.bordered)
                .tint(HikeJournalTheme.moss)
                .disabled(working || journal.isReviewBatchWorking)
            } else {
                ForEach(Array(item.candidates.prefix(5).enumerated()), id: \.offset) { index, candidate in
                    HStack(alignment: .top, spacing: 12) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(candidate.commonName).font(HikeJournalTheme.label(15, relativeTo: .headline))
                            Text(candidate.scientificName).font(HikeJournalTheme.body(12)).italic()
                            if let confidence = normalizedReviewConfidence(candidate.confidence) {
                                Text("Suggestion confidence \(confidence.formatted(.percent.precision(.fractionLength(0))))")
                                    .font(HikeJournalTheme.body(12)).foregroundStyle(HikeJournalTheme.inkMuted)
                            }
                        }
                        Spacer()
                        Button(index == 0 ? "Confirm" : "Choose") {
                            decide(action: "confirm", candidate: candidate)
                        }
                        .font(HikeJournalTheme.label(13, relativeTo: .subheadline))
                        .disabled(working)
                    }
                }
                Button("Reject suggestion", role: .destructive) { decide(action: "reject", candidate: nil) }
                    .disabled(working)
            }
        }
    }

    private func decide(action: String, candidate: ReviewCandidate?) {
        working = true
        Task {
            _ = await journal.decideReview(
                photoID: item.photo.id,
                observationID: item.observationId,
                action: action,
                candidate: candidate
            )
            working = false
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
                    Button(working ? "Publishing…" : "Publish") {
                        working = true
                        Task {
                            _ = await journal.publishObservation(
                                id: item.id,
                                options: PublishOptions(
                                    observationIds: [item.id],
                                    geoprivacy: geoprivacy
                                )
                            )
                            working = false
                        }
                    }
                    .font(HikeJournalTheme.label(13, relativeTo: .subheadline))
                    .disabled(!connected || working || journal.isPublishBatchWorking)
                }
            }
            Spacer()
        }
        .accessibilityElement(children: .combine)
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
