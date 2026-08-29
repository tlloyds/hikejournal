import Charts
import Foundation
import HikeJournalDomain
import HikeJournalMaps
import SwiftUI

struct PlacesWorkspaceView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var journal: JournalStore
    @ObservedObject private var authentication: AuthenticationStore

    @Environment(\.dismiss) private var dismiss
    @AppStorage("places.library.stateCode") private var stateCode = "FL"
    @State private var query = ""
    @State private var showingAddPlace = false

    init(model: AppModel) {
        self.model = model
        _journal = ObservedObject(wrappedValue: model.journal)
        _authentication = ObservedObject(wrappedValue: model.authentication)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                content
            }
            .navigationTitle("Places")
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $query, prompt: "Search saved places")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Menu {
                        Picker("State library", selection: $stateCode) {
                            ForEach(unitedStates, id: \.code) { state in
                                Text(state.name).tag(state.code)
                            }
                        }
                    } label: {
                        Text(stateCode)
                            .font(HikeJournalTheme.label(14, relativeTo: .headline))
                    }
                    .accessibilityLabel("Place library state, \(stateName)")
                }
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button {
                        showingAddPlace = true
                    } label: {
                        Image(systemName: "plus")
                    }
                    .disabled(!isSignedIn)
                    .accessibilityLabel("Add a saved place")
                    Button("Done") { dismiss() }
                }
            }
            .navigationDestination(for: PlaceTarget.self) { target in
                PlaceProfileView(model: model, target: target)
            }
            .task(id: "\(accountIdentity)|\(stateCode)") {
                guard isSignedIn else { return }
                await journal.loadLocations(state: stateCode)
                if journal.hikes.isEmpty { await journal.refreshHikes() }
            }
            .refreshable {
                await journal.loadLocations(state: stateCode, force: true)
                await journal.refreshHikes()
            }
            .sheet(isPresented: $showingAddPlace) {
                AddPlaceView { name, latitude, longitude in
                    await journal.createLocation(
                        name: name,
                        latitude: latitude,
                        longitude: longitude
                    ) != nil
                }
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        switch authentication.phase {
        case .restoring:
            ProgressView("Opening saved places…")
                .font(HikeJournalTheme.body())
                .tint(HikeJournalTheme.trailText)
        case .signedOut:
            VStack(alignment: .leading, spacing: 10) {
                Text("Plan from the places you know.")
                    .font(HikeJournalTheme.display(36, relativeTo: .title))
                    .foregroundStyle(HikeJournalTheme.ink)
                Text("Sign in to see visited places, save trailheads, and check conditions before an outing.")
                    .font(HikeJournalTheme.body(18))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                Button("Open account") {
                    dismiss()
                    model.openSettings()
                }
                .buttonStyle(TrailButtonStyle())
                .padding(.top, 12)
            }
            .padding(24)
        case .signedIn:
            if journal.activeLoads.contains("locations") && placeTargets.isEmpty {
                ProgressView("Gathering the \(stateName) place library…")
                    .font(HikeJournalTheme.body())
                    .tint(HikeJournalTheme.trailText)
            } else {
                placeList
            }
        }
    }

    private var placeList: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("HIKEJOURNAL PLACES")
                        .font(HikeJournalTheme.display(37, relativeTo: .largeTitle))
                        .foregroundStyle(HikeJournalTheme.moss)
                    Text("Return to personal histories, or plan somewhere you haven't recorded yet.")
                        .font(HikeJournalTheme.body(16))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.horizontal, 22)
                .padding(.top, 16)
                .padding(.bottom, 22)

                if visibleTargets.isEmpty {
                    ContentUnavailableView(
                        query.isEmpty ? "No saved places yet" : "No matching places",
                        systemImage: "mappin.slash",
                        description: Text(query.isEmpty
                            ? "Add a park, trailhead, or preserve with coordinates, or choose another state library."
                            : "Try another place name.")
                    )
                    .padding(.top, 50)
                } else {
                    ForEach(visibleTargets) { target in
                        NavigationLink(value: target) {
                            PlaceTargetRow(target: target)
                        }
                        .buttonStyle(.plain)
                        Divider().overlay(HikeJournalTheme.line).padding(.leading, 22)
                    }
                }
            }
            .padding(.bottom, 42)
        }
        .scrollIndicators(.hidden)
    }

    private var placeTargets: [PlaceTarget] {
        buildPlaceTargets(hikes: journal.hikes, locations: journal.locations)
    }

    private var visibleTargets: [PlaceTarget] {
        let clean = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { return placeTargets }
        return placeTargets.filter { $0.name.localizedCaseInsensitiveContains(clean) }
    }

    private var stateName: String {
        unitedStates.first { $0.code == stateCode }?.name ?? stateCode
    }

    private var isSignedIn: Bool {
        if case .signedIn = authentication.phase { return true }
        return false
    }

    private var accountIdentity: String {
        switch authentication.phase {
        case .restoring: "restoring"
        case .signedOut: "signed-out"
        case let .signedIn(account): account.userID ?? account.subject
        }
    }
}

struct PlaceTarget: Hashable, Identifiable {
    let id: String
    let name: String
    let coverURL: String
    let latestHikeDate: String
    let latitude: Double?
    let longitude: Double?
    let isUserPlace: Bool

    var hasCoordinates: Bool { latitude != nil && longitude != nil }
    var hasRecordedVisit: Bool { !latestHikeDate.isEmpty }
}

private func buildPlaceTargets(hikes: [Hike], locations: [HikeLocation]) -> [PlaceTarget] {
    let locationsByID = Dictionary(uniqueKeysWithValues: locations.map { ($0.id, $0) })
    var latestByPlace: [String: Hike] = [:]
    for hike in hikes where !hike.isStandalone {
        guard let locationID = hike.primaryLocationId, !locationID.isEmpty else { continue }
        if let current = latestByPlace[locationID], current.hikeDate >= hike.hikeDate { continue }
        latestByPlace[locationID] = hike
    }
    let visited = latestByPlace.map { locationID, hike in
        let location = locationsByID[locationID]
        return PlaceTarget(
            id: locationID,
            name: firstPlaceName(hike.primaryLocationName, hike.locationName, location?.name),
            coverURL: hike.coverUrl,
            latestHikeDate: hike.hikeDate,
            latitude: location?.latitude,
            longitude: location?.longitude,
            isUserPlace: location?.isUserPlace ?? false
        )
    }
    .sorted {
        if $0.latestHikeDate != $1.latestHikeDate { return $0.latestHikeDate > $1.latestHikeDate }
        return $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending
    }
    let visitedIDs = Set(visited.map(\.id))
    let unvisited = locations
        .filter { !visitedIDs.contains($0.id) }
        .map {
            PlaceTarget(
                id: $0.id,
                name: $0.name,
                coverURL: "",
                latestHikeDate: "",
                latitude: $0.latitude,
                longitude: $0.longitude,
                isUserPlace: $0.isUserPlace
            )
        }
        .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    return visited + unvisited
}

private func firstPlaceName(_ values: String? ...) -> String {
    values
        .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
        .first { !$0.isEmpty } ?? "Unknown place"
}

private struct PlaceTargetRow: View {
    let target: PlaceTarget

    var body: some View {
        HStack(spacing: 15) {
            if target.coverURL.isEmpty {
                ZStack {
                    LinearGradient(
                        colors: [HikeJournalTheme.lichen, HikeJournalTheme.fern.opacity(0.55)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                    Image(systemName: target.isUserPlace ? "mappin.and.ellipse" : "leaf")
                        .font(.title2)
                        .foregroundStyle(HikeJournalTheme.moss)
                }
                .frame(width: 76, height: 76)
            } else {
                JournalRemoteImage(urlString: target.coverURL, fallback: "mappin")
                    .frame(width: 76, height: 76)
                    .clipped()
            }
            VStack(alignment: .leading, spacing: 4) {
                Text(target.name)
                    .font(HikeJournalTheme.display(22, relativeTo: .title3))
                    .foregroundStyle(HikeJournalTheme.ink)
                Text(subtitle)
                    .font(HikeJournalTheme.body(14))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                if target.isUserPlace {
                    Text("YOUR PLACE")
                        .font(HikeJournalTheme.label(10))
                        .tracking(0.8)
                        .foregroundStyle(HikeJournalTheme.trailText)
                }
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.caption.weight(.bold))
                .foregroundStyle(HikeJournalTheme.inkMuted.opacity(0.6))
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 12)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens the place profile")
    }

    private var subtitle: String {
        if !target.latestHikeDate.isEmpty {
            return "Last visit \(JournalDate.display(target.latestHikeDate))"
        }
        return target.hasCoordinates ? "Live planning ready" : "Coordinates needed for conditions"
    }
}

private struct AddPlaceView: View {
    let save: (String, Double, Double) async -> Bool
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var latitude = ""
    @State private var longitude = ""
    @State private var validation: String?
    @State private var saving = false

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Save a place of your own.")
                            .font(HikeJournalTheme.display(34, relativeTo: .title))
                            .foregroundStyle(HikeJournalTheme.ink)
                        Text("Add a park, trailhead, preserve, or neighborhood patch anywhere. Coordinates power local forecasts and field briefings.")
                            .font(HikeJournalTheme.body())
                            .foregroundStyle(HikeJournalTheme.inkMuted)

                        PlaceTextField(title: "Place name", placeholder: "Oak Flat Preserve", text: $name)
                        PlaceTextField(title: "Latitude", placeholder: "28.6419", text: $latitude, decimal: true)
                        PlaceTextField(title: "Longitude", placeholder: "−81.1214", text: $longitude, decimal: true)

                        Text("Tip: press and hold a point in Apple Maps or Google Maps to copy its coordinates.")
                            .font(HikeJournalTheme.body(13))
                            .foregroundStyle(HikeJournalTheme.inkMuted)

                        if let validation {
                            Label(validation, systemImage: "exclamationmark.triangle.fill")
                                .font(HikeJournalTheme.body(14))
                                .foregroundStyle(HikeJournalTheme.error)
                        }

                        Button {
                            submit()
                        } label: {
                            HStack {
                                if saving { ProgressView().tint(HikeJournalTheme.paper) }
                                Text(saving ? "Saving place…" : "Save place")
                                Spacer()
                                Image(systemName: "arrow.right")
                            }
                        }
                        .buttonStyle(TrailButtonStyle())
                        .disabled(saving)
                    }
                    .padding(24)
                }
            }
            .navigationTitle("Add place")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Cancel") { dismiss() }.disabled(saving)
                }
            }
        }
    }

    private func submit() {
        let cleanName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        let normalizedLatitude = latitude.replacingOccurrences(of: "−", with: "-")
        let normalizedLongitude = longitude.replacingOccurrences(of: "−", with: "-")
        guard !cleanName.isEmpty else { validation = "Enter a name for this place."; return }
        guard let lat = Double(normalizedLatitude), let lng = Double(normalizedLongitude) else {
            validation = "Enter valid decimal coordinates."
            return
        }
        guard (-90...90).contains(lat) else { validation = "Latitude must be between −90 and 90."; return }
        guard (-180...180).contains(lng) else { validation = "Longitude must be between −180 and 180."; return }
        validation = nil
        saving = true
        Task {
            if await save(cleanName, lat, lng) { dismiss() }
            else { validation = "HikeJournal couldn't save this place. Check the connection and try again." }
            saving = false
        }
    }
}

private struct PlaceTextField: View {
    let title: String
    let placeholder: String
    @Binding var text: String
    var decimal = false

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title.uppercased())
                .font(HikeJournalTheme.label(11))
                .tracking(0.9)
                .foregroundStyle(HikeJournalTheme.trailText)
            TextField(placeholder, text: $text)
                .keyboardType(decimal ? .numbersAndPunctuation : .default)
                .textInputAutocapitalization(decimal ? .never : .words)
                .padding(.horizontal, 12)
                .frame(minHeight: 48)
                .background(HikeJournalTheme.paper)
                .overlay { RoundedRectangle(cornerRadius: 8).stroke(HikeJournalTheme.line) }
        }
    }
}

private struct PlaceProfileView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var authentication: AuthenticationStore
    @ObservedObject private var maps: MapStore
    @ObservedObject private var riverGauges: RiverGaugePreferencesStore
    let target: PlaceTarget

    @State private var profile: PlaceProfile?
    @State private var isLoading = false
    @State private var fromCache = false
    @State private var errorMessage: String?
    @State private var riverDays = 7
    @State private var showingBriefing = false
    @State private var showingPaywall = false

    init(model: AppModel, target: PlaceTarget) {
        self.model = model
        self.target = target
        _authentication = ObservedObject(wrappedValue: model.authentication)
        _maps = ObservedObject(wrappedValue: model.maps)
        _riverGauges = ObservedObject(wrappedValue: model.riverGauges)
    }

    var body: some View {
        ZStack {
            ParchmentBackground()
            if authentication.entitlement?.allows("place_profiles") == false {
                upgradeView
            } else if isLoading && profile == nil {
                ProgressView("Gathering this place…")
                    .font(HikeJournalTheme.body())
                    .tint(HikeJournalTheme.trailText)
            } else if let profile {
                profileBody(profile)
            } else {
                ContentUnavailableView(
                    "Place profile unavailable",
                    systemImage: "mappin.slash",
                    description: Text(errorMessage ?? "Try again when this iPhone has a connection.")
                )
            }
        }
        .navigationTitle(profile?.name ?? target.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Task { await load(force: true) }
                } label: {
                    if isLoading { ProgressView() } else { Image(systemName: "arrow.clockwise") }
                }
                .disabled(isLoading || authentication.entitlement?.allows("place_profiles") == false)
                .accessibilityLabel("Refresh place profile")
            }
        }
        .task(id: conditionsTaskID) { await load() }
        .sheet(isPresented: $showingBriefing) {
            FieldBriefingView(
                model: model,
                locationID: profile?.locationId ?? target.id,
                locationName: profile?.name ?? target.name
            )
        }
        .sheet(isPresented: $showingPaywall) {
            PlusPaywallView(
                storefront: model.storefront,
                privacyURL: model.configuration.webBaseURL?.appendingPathComponent("privacy")
            )
        }
        .alert("Place profile unavailable", isPresented: Binding(
            get: { errorMessage != nil && profile != nil },
            set: { if !$0 { errorMessage = nil } }
        )) {
            Button("OK") { errorMessage = nil }
        } message: {
            Text(errorMessage ?? "")
        }
    }

    private func profileBody(_ profile: PlaceProfile) -> some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0) {
                placeHero(profile)
                if fromCache {
                    Label("Saved offline copy", systemImage: "icloud.slash")
                        .font(HikeJournalTheme.body(13))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                        .padding(.horizontal, 22)
                        .padding(.top, 12)
                }
                if let forecast = profile.forecast {
                    PlaceForecastSection(
                        placeName: profile.name,
                        forecast: forecast,
                        openBriefing: { showingBriefing = true }
                    )
                } else {
                    PlaceSection(title: "Today at \(profile.name)") {
                        Text(profile.liveConditionsNotice ?? conditionsFallback(profile))
                            .font(HikeJournalTheme.body())
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                        Button("What might I see today?") { showingBriefing = true }
                            .font(HikeJournalTheme.label(15, relativeTo: .headline))
                            .foregroundStyle(HikeJournalTheme.moss)
                            .disabled(profile.latitude == nil || profile.longitude == nil)
                    }
                }

                RiverConditionsSection(
                    series: profile.riverGauges,
                    periodDays: riverDays,
                    loading: isLoading,
                    hasCoordinates: profile.latitude != nil && profile.longitude != nil,
                    changePeriod: { days in
                        guard days != riverDays else { return }
                        riverDays = days
                    },
                    isFollowed: { gauge in
                        riverGauges.isFollowed(gauge)
                    },
                    toggleFollow: { gauge in
                        riverGauges.setFollowed(
                            gauge,
                            isFollowed: !riverGauges.isFollowed(gauge)
                        )
                    }
                )

                if let mapScene = placeMapScene(profile), let style = maps.style,
                   let surface = try? HikeJournalMapSurface(
                       scene: mapScene,
                       style: style,
                       styleCredential: maps.styleCredential,
                       cameraBehavior: .fitOnce
                   ) {
                    PlaceSection(title: "Where this record lives") {
                        surface.frame(height: 235)
                    }
                }

                if profile.outingCount > 0 {
                    PlaceHistorySummary(profile: profile)
                    PlaceSeasonalSection(history: profile.seasonalHistory)
                    PlaceLifeSection(model: model, groups: profile.taxonGroups)
                    PlaceVisitsSection(model: model, visits: profile.visits)
                } else {
                    PlaceSection(title: "A future field page") {
                        Text("No recorded visit yet. Use this profile to plan, then link the place when you save an outing.")
                            .font(HikeJournalTheme.body())
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                    }
                }
            }
            .padding(.bottom, 44)
        }
        .scrollIndicators(.hidden)
    }

    private func placeHero(_ profile: PlaceProfile) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            if let cover = profile.visits.first?.coverUrl, !cover.isEmpty {
                JournalRemoteImage(urlString: cover, fallback: "mappin.and.ellipse")
                    .frame(height: 260)
                    .clipped()
                    .accessibilityLabel("Most recent outing at \(profile.name)")
            } else {
                BrandLandscape()
                    .frame(height: 220)
                    .accessibilityHidden(true)
            }
            VStack(alignment: .leading, spacing: 5) {
                Text("PLACE PROFILE")
                    .font(HikeJournalTheme.label(11))
                    .tracking(1.3)
                    .foregroundStyle(HikeJournalTheme.trailText)
                Text(profile.name)
                    .font(HikeJournalTheme.display(38, relativeTo: .largeTitle))
                    .foregroundStyle(HikeJournalTheme.ink)
                Text(profile.outingCount == 0
                    ? "Live planning profile"
                    : "\(profile.outingCount) recorded \(profile.outingCount == 1 ? "visit" : "visits") · \(String(format: "%.1f", profile.totalDistanceMiles)) miles")
                    .font(HikeJournalTheme.body(16))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }
            .padding(.horizontal, 22)
            .padding(.top, 18)
        }
    }

    private var upgradeView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                BrandLandscape().frame(height: 230)
                Text("Know a place across seasons.")
                    .font(HikeJournalTheme.display(36, relativeTo: .title))
                    .foregroundStyle(HikeJournalTheme.ink)
                Text("Complete Place Profiles—forecast, water gauges, personal history, seasonal patterns, and Field Briefings—are included with HikeJournal Plus.")
                    .font(HikeJournalTheme.body(18))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                Button("Explore HikeJournal Plus") { showingPaywall = true }
                    .buttonStyle(TrailButtonStyle())
                    .padding(.top, 14)
            }
            .padding(22)
        }
    }

    private func load(force: Bool = false) async {
        guard authentication.entitlement?.allows("place_profiles") != false else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            let result = try await model.journal.placeProfile(
                id: target.id,
                riverDays: riverDays,
                followedGaugeIDs: riverGauges.followedIDs,
                force: force
            )
            profile = result.value
                .withResolvedName(fallback: target.name)
                .withLocalVisitEvidence(hikes: model.journal.hikes, locationID: target.id)
            fromCache = result.fromCache
            errorMessage = nil
        } catch is CancellationError {
            return
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "This place profile is unavailable."
        }
    }

    private func placeMapScene(_ profile: PlaceProfile) -> MapScene? {
        guard let latitude = profile.latitude, let longitude = profile.longitude,
              let coordinate = try? GeoCoordinate(latitude: latitude, longitude: longitude),
              let point = try? MapPoint(
                  id: "place:\(profile.locationId)",
                  kind: .place,
                  title: profile.name,
                  detail: profile.outingCount == 0 ? "Saved place" : "\(profile.outingCount) recorded visits",
                  coordinate: coordinate
              ) else { return nil }
        return MapScene(points: [point])
    }

    private func conditionsFallback(_ profile: PlaceProfile) -> String {
        profile.latitude == nil || profile.longitude == nil
            ? "Add coordinates to this place to load live planning conditions."
            : "Live weather is temporarily unavailable."
    }

    private var conditionsTaskID: String {
        "\(target.id)|\(riverDays)|\(riverGauges.followedIDs.joined(separator: ","))"
    }
}

private struct PlaceForecastSection: View {
    let placeName: String
    let forecast: PlaceForecast
    let openBriefing: () -> Void

    var body: some View {
        PlaceSection(title: "Today at \(placeName)") {
            HStack(alignment: .center, spacing: 13) {
                Image(systemName: weatherSymbol)
                    .font(.system(size: 32, weight: .light))
                    .foregroundStyle(HikeJournalTheme.trailText)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 0) {
                    Text(forecast.temperatureF.map { "\(Int($0.rounded()))°F" } ?? "—")
                        .font(HikeJournalTheme.display(42, relativeTo: .largeTitle))
                        .foregroundStyle(HikeJournalTheme.ink)
                    Text(forecast.conditionLabel)
                        .font(HikeJournalTheme.label(16, relativeTo: .headline))
                        .foregroundStyle(HikeJournalTheme.moss)
                }
                Spacer()
                if let today = forecast.days.first {
                    VStack(alignment: .trailing, spacing: 1) {
                        Text(highLow(today))
                            .font(HikeJournalTheme.display(24, relativeTo: .title3))
                            .foregroundStyle(HikeJournalTheme.ink)
                        Text("HIGH / LOW")
                            .font(HikeJournalTheme.label(10))
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                    }
                }
            }

            let details = currentDetails
            if !details.isEmpty {
                Text(details.joined(separator: " · "))
                    .font(HikeJournalTheme.body(14))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }

            if let today = forecast.days.first {
                HStack(spacing: 24) {
                    WeatherMetric(value: today.precipitationProbabilityPercent.map { "\(Int($0.rounded()))%" } ?? "—", label: "RAIN")
                    WeatherMetric(value: today.uvIndexMax.map { String(format: "%.1f", $0) } ?? "—", label: "PEAK UV")
                    WeatherMetric(value: forecastClock(today.sunrise), label: "SUNRISE")
                    WeatherMetric(value: forecastClock(today.sunset), label: "SUNSET")
                }
                .padding(.vertical, 8)
            }

            ForEach(forecast.planningNotes, id: \.self) { note in
                HStack(alignment: .top, spacing: 9) {
                    Circle().fill(HikeJournalTheme.trailText).frame(width: 6, height: 6).padding(.top, 7)
                    Text(note)
                        .font(HikeJournalTheme.body(15))
                        .foregroundStyle(HikeJournalTheme.ink)
                }
            }

            if forecast.days.count > 1 {
                Text("NEXT FIVE DAYS")
                    .font(HikeJournalTheme.label(11))
                    .tracking(0.9)
                    .foregroundStyle(HikeJournalTheme.trailText)
                    .padding(.top, 10)
                ForEach(Array(forecast.days.dropFirst().prefix(5).enumerated()), id: \.offset) { _, day in
                    HStack {
                        Text(shortWeekday(day.date)).frame(width: 42, alignment: .leading)
                        Text(day.conditionLabel).frame(maxWidth: .infinity, alignment: .leading)
                        if let chance = day.precipitationProbabilityPercent {
                            Text("\(Int(chance.rounded()))%")
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                        Text(highLow(day))
                    }
                    .font(HikeJournalTheme.body(14))
                    .foregroundStyle(HikeJournalTheme.ink)
                    .padding(.vertical, 5)
                    Divider().overlay(HikeJournalTheme.line)
                }
            }

            Link("Open-Meteo forecast data · CC BY 4.0", destination: URL(string: "https://open-meteo.com/")!)
                .font(HikeJournalTheme.body(12, relativeTo: .caption))
                .foregroundStyle(HikeJournalTheme.inkMuted)
            Button("What might I see today?", action: openBriefing)
                .font(HikeJournalTheme.label(16, relativeTo: .headline))
                .foregroundStyle(HikeJournalTheme.moss)
                .padding(.top, 4)
        }
    }

    private var weatherSymbol: String {
        let value = forecast.conditionLabel.lowercased()
        if value.contains("clear") { return "sun.max.fill" }
        if value.contains("thunder") { return "cloud.bolt.rain.fill" }
        if value.contains("rain") || value.contains("drizzle") { return "cloud.rain.fill" }
        if value.contains("snow") { return "cloud.snow.fill" }
        if value.contains("fog") { return "cloud.fog.fill" }
        return "cloud.sun.fill"
    }

    private var currentDetails: [String] {
        var values: [String] = []
        if let feels = forecast.apparentTemperatureF { values.append("Feels \(Int(feels.rounded()))°F") }
        if let humidity = forecast.relativeHumidityPercent { values.append("\(Int(humidity.rounded()))% humidity") }
        if let wind = forecast.windSpeedMph { values.append("\(Int(wind.rounded())) mph wind") }
        if let cloud = forecast.cloudCoverPercent { values.append("\(Int(cloud.rounded()))% cloud cover") }
        return values
    }

    private func highLow(_ day: ForecastDay) -> String {
        [day.temperatureMaxF, day.temperatureMinF]
            .compactMap { $0.map { "\(Int($0.rounded()))°" } }
            .joined(separator: " / ")
    }
}

private struct WeatherMetric: View {
    let value: String
    let label: String
    var body: some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(value).font(HikeJournalTheme.label(16, relativeTo: .headline)).foregroundStyle(HikeJournalTheme.moss)
            Text(label).font(HikeJournalTheme.label(9)).foregroundStyle(HikeJournalTheme.inkMuted)
        }
        .accessibilityElement(children: .combine)
    }
}

private struct RiverConditionsSection: View {
    let series: [RiverGaugeSeries]
    let periodDays: Int
    let loading: Bool
    let hasCoordinates: Bool
    let changePeriod: (Int) -> Void
    let isFollowed: (RiverGauge) -> Bool
    let toggleFollow: (RiverGauge) -> Void

    var body: some View {
        PlaceSection(title: "Water height") {
            Text("Closest active USGS water gauges to this place.")
                .font(HikeJournalTheme.body(15))
                .foregroundStyle(HikeJournalTheme.inkMuted)
            Picker("Gauge history", selection: Binding(
                get: { periodDays }, set: changePeriod
            )) {
                Text("7 days").tag(7)
                Text("30 days").tag(30)
            }
            .pickerStyle(.segmented)
            .disabled(loading)

            if loading && series.isEmpty {
                ProgressView("Reading USGS gauges…")
                    .font(HikeJournalTheme.body(14))
                    .tint(HikeJournalTheme.trailText)
            } else if series.isEmpty {
                Text(hasCoordinates
                    ? "No active USGS water gauges were found within 30 miles."
                    : "Add coordinates to find nearby USGS water gauges.")
                    .font(HikeJournalTheme.body())
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            } else {
                ForEach(Array(series.enumerated()), id: \.element.gauge.siteId) { _, value in
                    RiverGaugeView(
                        series: value,
                        isFollowed: isFollowed(value.gauge),
                        toggleFollow: { toggleFollow(value.gauge) }
                    )
                    Divider().overlay(HikeJournalTheme.line)
                }
                Text("USGS parameter 00065. Values may be provisional; a height at one station is not a crossing-safety rating and cannot be compared directly with another station.")
                    .font(HikeJournalTheme.body(12, relativeTo: .caption))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }
        }
    }
}

private struct RiverGaugeView: View {
    let series: RiverGaugeSeries
    let isFollowed: Bool
    let toggleFollow: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(alignment: .top) {
                Image(systemName: "drop.fill")
                    .foregroundStyle(HikeJournalTheme.trailText)
                VStack(alignment: .leading, spacing: 1) {
                    Text(series.gauge.name)
                        .font(HikeJournalTheme.label(16, relativeTo: .headline))
                        .foregroundStyle(HikeJournalTheme.ink)
                    Text([series.gauge.siteId, series.distanceMiles.map { String(format: "%.0f mi away", $0) }]
                        .compactMap { $0 }.joined(separator: " · "))
                        .font(HikeJournalTheme.body(12))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }
                Spacer()
                if let current = series.currentHeightFeet {
                    Text(String(format: "%.2f ft", current))
                        .font(HikeJournalTheme.display(23, relativeTo: .title3))
                        .foregroundStyle(HikeJournalTheme.moss)
                }
            }
            if let error = series.errorMessage {
                Text(error).font(HikeJournalTheme.body(14)).foregroundStyle(HikeJournalTheme.inkMuted)
            } else if series.readings.count >= 2 {
                Chart(Array(series.readings.enumerated()), id: \.offset) { index, reading in
                    LineMark(
                        x: .value("Reading", index),
                        y: .value("Height in feet", reading.heightFeet)
                    )
                    .foregroundStyle(HikeJournalTheme.trailText)
                    .lineStyle(StrokeStyle(lineWidth: 2.4, lineCap: .round, lineJoin: .round))
                }
                .chartXAxis(.hidden)
                .chartYAxis(.hidden)
                .frame(height: 72)
                .accessibilityLabel("\(series.periodDays)-day water-height trend")
                Text(trendLabel)
                    .font(HikeJournalTheme.body(13))
                    .foregroundStyle(HikeJournalTheme.ink)
            }
            if let url = URL(string: "https://waterdata.usgs.gov/monitoring-location/\(series.gauge.siteId)/#dataTypeId=continuous-00065-0&period=P\(series.periodDays)D") {
                HStack(spacing: 18) {
                    Button(action: toggleFollow) {
                        Label(
                            isFollowed ? "Following" : "Follow gauge",
                            systemImage: isFollowed ? "bookmark.fill" : "bookmark"
                        )
                    }
                    .accessibilityLabel(isFollowed ? "Stop following \(series.gauge.name)" : "Follow \(series.gauge.name)")
                    Link("Open USGS station", destination: url)
                }
                .font(HikeJournalTheme.label(14, relativeTo: .headline))
                .foregroundStyle(HikeJournalTheme.moss)
                .buttonStyle(.plain)
            }
        }
        .padding(.vertical, 10)
    }

    private var trendLabel: String {
        guard let change = series.changeFeet else { return "Net change unavailable" }
        if change > 0.05 { return String(format: "Up +%.2f ft over %d days", change, series.periodDays) }
        if change < -0.05 { return String(format: "Down %.2f ft over %d days", change, series.periodDays) }
        return "Little net change over \(series.periodDays) days"
    }
}

private struct PlaceHistorySummary: View {
    let profile: PlaceProfile
    var body: some View {
        PlaceSection(title: "Your record here") {
            Text("\(profile.speciesCount) species across \(profile.observationCount) confirmed observations, from \(profile.firstVisit.map(JournalDate.display) ?? "your first saved visit") through \(profile.latestVisit.map(JournalDate.display) ?? "the latest page").")
                .font(HikeJournalTheme.body(17))
                .foregroundStyle(HikeJournalTheme.ink)
            if !profile.guidance.isEmpty {
                Text(profile.guidance)
                    .font(HikeJournalTheme.body(16))
                    .italic()
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }
        }
    }
}

private struct PlaceSeasonalSection: View {
    let history: SeasonalHistory
    var body: some View {
        PlaceSection(title: "When you visit") {
            if history.months.isEmpty {
                Text("More recorded observations are needed before a seasonal pattern appears.")
                    .font(HikeJournalTheme.body())
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            } else {
                HStack(alignment: .bottom, spacing: 5) {
                    ForEach(Array(history.months.enumerated()), id: \.offset) { _, month in
                        VStack(spacing: 4) {
                            RoundedRectangle(cornerRadius: 2)
                                .fill(HikeJournalTheme.fern.opacity(0.32 + 0.68 * min(1, max(0, month.relativeIntensity))))
                                .frame(height: 10 + 64 * min(1, max(0, month.relativeIntensity)))
                            Text(String(month.label.prefix(1)))
                                .font(HikeJournalTheme.label(9))
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

private struct PlaceLifeSection: View {
    @ObservedObject var model: AppModel
    let groups: [PlaceTaxonGroup]
    @State private var expanded: Set<String> = []

    var body: some View {
        if !groups.isEmpty {
            PlaceSection(title: "Life recorded") {
                ForEach(Array(groups.enumerated()), id: \.offset) { _, group in
                    DisclosureGroup(isExpanded: Binding(
                        get: { expanded.contains(group.name) },
                        set: { value in
                            if value { expanded.insert(group.name) } else { expanded.remove(group.name) }
                        }
                    )) {
                        ForEach(Array(group.species.enumerated()), id: \.element.key) { _, species in
                            if let seed = model.journal.species.first(where: { $0.key == species.key }) {
                                NavigationLink {
                                    SpeciesDetailView(model: model, seed: seed)
                                } label: {
                                    PlaceSpeciesRow(species: species)
                                }
                                .buttonStyle(.plain)
                            } else {
                                PlaceSpeciesRow(species: species)
                            }
                        }
                    } label: {
                        Text("\(friendlyPlaceTaxon(group.name)) · \(group.count)")
                            .font(HikeJournalTheme.label(16, relativeTo: .headline))
                            .foregroundStyle(HikeJournalTheme.ink)
                    }
                    .tint(HikeJournalTheme.moss)
                    Divider().overlay(HikeJournalTheme.line)
                }
            }
        }
    }
}

private func friendlyPlaceTaxon(_ value: String) -> String {
    switch value.lowercased() {
    case "plantae": "Plants"
    case "aves": "Birds"
    case "mammalia": "Mammals"
    case "fungi": "Fungi"
    case "insecta": "Insects"
    case "arachnida": "Arachnids"
    case "reptilia": "Reptiles"
    case "amphibia": "Amphibians"
    case "actinopterygii": "Fish"
    case "mollusca": "Mollusks"
    case "animalia": "Other animals"
    default: value.isEmpty ? "Other" : value
    }
}

private struct PlaceSpeciesRow: View {
    let species: PlaceSpecies
    var body: some View {
        HStack(spacing: 11) {
            JournalRemoteImage(urlString: species.referencePhotoUrl, fallback: "leaf")
                .frame(width: 52, height: 52)
                .clipped()
            VStack(alignment: .leading, spacing: 1) {
                Text(species.commonName)
                    .font(HikeJournalTheme.label(15, relativeTo: .headline))
                    .foregroundStyle(HikeJournalTheme.ink)
                Text(species.scientificName)
                    .font(HikeJournalTheme.body(13))
                    .italic()
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }
            Spacer()
            Text("\(species.encounterCount)")
                .font(HikeJournalTheme.label(13))
                .foregroundStyle(HikeJournalTheme.trailText)
        }
        .padding(.vertical, 6)
        .accessibilityElement(children: .combine)
    }
}

private struct PlaceVisitsSection: View {
    @ObservedObject var model: AppModel
    let visits: [PlaceVisit]
    var body: some View {
        if !visits.isEmpty {
            PlaceSection(title: "Visit history") {
                ForEach(Array(visits.enumerated()), id: \.element.hikeId) { _, visit in
                    NavigationLink {
                        JournalHikeDetailView(model: model, hikeID: visit.hikeId)
                    } label: {
                        HStack(spacing: 13) {
                            JournalRemoteImage(urlString: visit.coverUrl, fallback: "figure.hiking")
                                .frame(width: 78, height: 68)
                                .clipped()
                            VStack(alignment: .leading, spacing: 2) {
                                Text(JournalDate.display(visit.hikeDate))
                                    .font(HikeJournalTheme.label(11))
                                    .foregroundStyle(HikeJournalTheme.trailText)
                                Text(visit.title)
                                    .font(HikeJournalTheme.display(20, relativeTo: .title3))
                                    .foregroundStyle(HikeJournalTheme.ink)
                                Text("\(visit.speciesCount) species · \(visit.newSpeciesCount) new then")
                                    .font(HikeJournalTheme.body(13))
                                    .foregroundStyle(HikeJournalTheme.inkMuted)
                            }
                            Spacer()
                            Image(systemName: "arrow.right")
                                .foregroundStyle(HikeJournalTheme.moss)
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    Divider().overlay(HikeJournalTheme.line)
                }
            }
        }
    }
}

private struct PlaceSection<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content

    init(title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 11) {
            Text(title.uppercased())
                .font(HikeJournalTheme.label(11))
                .tracking(1.1)
                .foregroundStyle(HikeJournalTheme.trailText)
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 22)
        .padding(.vertical, 24)
        .background(HikeJournalTheme.paper.opacity(0.38))
        .overlay(alignment: .bottom) { Divider().overlay(HikeJournalTheme.line) }
    }
}

private struct FieldBriefingView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var authentication: AuthenticationStore
    let locationID: String
    let locationName: String

    @Environment(\.dismiss) private var dismiss
    @State private var briefing: FieldBriefing?
    @State private var selectedGroups: Set<String> = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingPaywall = false
    @State private var preview: BriefingItem?
    @State private var mapSelection: BriefingSightingsSelection?

    init(model: AppModel, locationID: String, locationName: String) {
        self.model = model
        self.locationID = locationID
        self.locationName = locationName
        _authentication = ObservedObject(wrappedValue: model.authentication)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                if authentication.entitlement?.allows("field_briefing") == false {
                    briefingUpgrade
                } else if isLoading && briefing == nil {
                    ProgressView("Preparing today's field briefing…")
                        .font(HikeJournalTheme.body())
                        .tint(HikeJournalTheme.trailText)
                } else if let briefing {
                    briefingBody(briefing)
                } else {
                    ContentUnavailableView(
                        "Field Briefing unavailable",
                        systemImage: "binoculars",
                        description: Text(errorMessage ?? "Try again when this iPhone has a connection.")
                    )
                }
            }
            .navigationTitle("Field Briefing")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Menu {
                        Button("Every life group") {
                            selectedGroups.removeAll()
                            Task { await load(force: true) }
                        }
                        ForEach(availableGroups, id: \.self) { group in
                            Button {
                                if selectedGroups.contains(group) { selectedGroups.remove(group) }
                                else { selectedGroups.insert(group) }
                                Task { await load(force: true) }
                            } label: {
                                Label(group, systemImage: selectedGroups.contains(group) ? "checkmark" : "circle")
                            }
                        }
                    } label: {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                    }
                    .disabled(briefing == nil)
                    .accessibilityLabel("Filter life groups")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
            .task { await load() }
            .sheet(isPresented: $showingPaywall) {
                PlusPaywallView(
                    storefront: model.storefront,
                    privacyURL: model.configuration.webBaseURL?.appendingPathComponent("privacy")
                )
            }
            .sheet(item: $preview) { item in
                BriefingItemDetail(item: item) {
                    preview = nil
                    guard let briefing, item.taxonId != nil else { return }
                    Task { await loadSightings(briefing: briefing, item: item) }
                }
            }
            .sheet(item: $mapSelection) { selection in
                BriefingSightingsMapView(model: model, value: selection.value)
            }
            .alert("Field Briefing unavailable", isPresented: Binding(
                get: { errorMessage != nil && briefing != nil },
                set: { if !$0 { errorMessage = nil } }
            )) { Button("OK") { errorMessage = nil } } message: { Text(errorMessage ?? "") }
        }
    }

    private func briefingBody(_ briefing: FieldBriefing) -> some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0) {
                if let cover = briefing.sections.flatMap(\.items).first(where: { !$0.displayPhotoURL.isEmpty }) {
                    JournalRemoteImage(urlString: cover.displayPhotoURL, fallback: "binoculars")
                        .frame(height: 255)
                        .clipped()
                } else {
                    BrandLandscape().frame(height: 220)
                }
                VStack(alignment: .leading, spacing: 5) {
                    Text("FIELD BRIEFING · \(JournalDate.display(briefing.targetDate))")
                        .font(HikeJournalTheme.label(11))
                        .tracking(1.0)
                        .foregroundStyle(HikeJournalTheme.trailText)
                    Text("What might I see today?")
                        .font(HikeJournalTheme.display(36, relativeTo: .title))
                        .foregroundStyle(HikeJournalTheme.ink)
                    Text(briefing.areaName)
                        .font(HikeJournalTheme.body(17))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                    Text("Nearby reports within \(briefing.radiusKm) km · \(briefing.periodLabel)")
                        .font(HikeJournalTheme.body(14))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                        .padding(.top, 4)
                    if !briefing.guidance.isEmpty {
                        Text(briefing.guidance)
                            .font(HikeJournalTheme.body(15))
                            .italic()
                            .foregroundStyle(HikeJournalTheme.ink)
                            .padding(.top, 7)
                    }
                }
                .padding(22)

                ForEach(Array(visibleSections(briefing).enumerated()), id: \.offset) { _, section in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(section.title)
                            .font(HikeJournalTheme.display(28, relativeTo: .title2))
                            .foregroundStyle(HikeJournalTheme.ink)
                        Text("\(section.items.count) field \(section.items.count == 1 ? "note" : "notes")")
                            .font(HikeJournalTheme.label(11))
                            .foregroundStyle(HikeJournalTheme.trailText)
                    }
                    .padding(.horizontal, 22)
                    .padding(.top, 20)
                    .padding(.bottom, 7)
                    ForEach(section.items) { item in
                        BriefingItemRow(
                            item: item,
                            details: { preview = item },
                            sightings: item.taxonId == nil ? nil : {
                                Task { await loadSightings(briefing: briefing, item: item) }
                            }
                        )
                        Divider().overlay(HikeJournalTheme.line).padding(.leading, 22)
                    }
                }
                if visibleSections(briefing).isEmpty {
                    Text("No recommendations match the selected life groups.")
                        .font(HikeJournalTheme.body())
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                        .padding(22)
                }
            }
            .padding(.bottom, 42)
        }
        .scrollIndicators(.hidden)
    }

    private var briefingUpgrade: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                BrandLandscape().frame(height: 230)
                Text("Know what to notice next.")
                    .font(HikeJournalTheme.display(36, relativeTo: .title))
                    .foregroundStyle(HikeJournalTheme.ink)
                Text("Field Briefings combine the season, nearby research-grade reports, active quests, and your own archive. They are included with HikeJournal Plus.")
                    .font(HikeJournalTheme.body(18))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                Button("Explore HikeJournal Plus") { showingPaywall = true }
                    .buttonStyle(TrailButtonStyle())
                    .padding(.top, 14)
            }
            .padding(22)
        }
    }

    private var availableGroups: [String] {
        Array(Set(briefing?.sections.flatMap(\.items).map(\.iconicTaxonName) ?? []))
            .filter { !$0.isEmpty }
            .sorted()
    }

    private func visibleSections(_ briefing: FieldBriefing) -> [BriefingSection] {
        guard !selectedGroups.isEmpty else { return briefing.sections }
        return briefing.sections.compactMap { section in
            let items = section.items.filter { selectedGroups.contains($0.iconicTaxonName) }
            return items.isEmpty ? nil : BriefingSection(title: section.title, items: items)
        }
    }

    private func load(force: Bool = false) async {
        guard authentication.entitlement?.allows("field_briefing") != false else { return }
        isLoading = true
        defer { isLoading = false }
        let date = ISO8601DateFormatter.day.string(from: Date())
        do {
            let result = try await model.journal.fieldBriefing(
                locationID: locationID,
                date: date,
                iconicTaxa: Array(selectedGroups),
                force: force
            )
            briefing = result.value
            errorMessage = nil
        } catch is CancellationError {
            return
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "Today's briefing is unavailable."
        }
    }

    private func loadSightings(briefing: FieldBriefing, item: BriefingItem) async {
        isLoading = true
        defer { isLoading = false }
        do {
            mapSelection = BriefingSightingsSelection(
                value: try await model.journal.briefingSightings(briefing: briefing, item: item)
            )
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "Mapped sightings are unavailable."
        }
    }
}

private struct BriefingItemRow: View {
    let item: BriefingItem
    let details: () -> Void
    let sightings: (() -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            Button(action: details) {
                HStack(spacing: 13) {
                    JournalRemoteImage(urlString: item.displayPhotoURL, fallback: "leaf")
                        .frame(width: 88, height: 88)
                        .clipped()
                    VStack(alignment: .leading, spacing: 2) {
                        Text(item.commonName)
                            .font(HikeJournalTheme.display(22, relativeTo: .title3))
                            .foregroundStyle(HikeJournalTheme.ink)
                        if !item.scientificName.isEmpty {
                            Text(item.scientificName)
                                .font(HikeJournalTheme.body(14))
                                .italic()
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                        Text(item.frequencyBand)
                            .font(HikeJournalTheme.label(11))
                            .foregroundStyle(HikeJournalTheme.trailText)
                    }
                    Spacer()
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            ForEach(item.reasons, id: \.self) { reason in
                Text("· \(reason)")
                    .font(HikeJournalTheme.body(14))
                    .foregroundStyle(HikeJournalTheme.ink)
            }
            HStack {
                Button("Species details", action: details)
                if let sightings {
                    Button("Map sightings", action: sightings)
                }
            }
            .font(HikeJournalTheme.label(14, relativeTo: .headline))
            .foregroundStyle(HikeJournalTheme.moss)
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 12)
    }
}

private struct BriefingItemDetail: View {
    let item: BriefingItem
    let mapSightings: (() -> Void)?
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        JournalRemoteImage(urlString: item.displayPhotoURL, fallback: "leaf")
                            .frame(height: 280)
                            .clipped()
                        Text(item.iconicTaxonName.uppercased())
                            .font(HikeJournalTheme.label(11))
                            .tracking(1.1)
                            .foregroundStyle(HikeJournalTheme.trailText)
                            .padding(.top, 20)
                        Text(item.commonName)
                            .font(HikeJournalTheme.display(35, relativeTo: .title))
                            .foregroundStyle(HikeJournalTheme.ink)
                        Text(item.scientificName)
                            .font(HikeJournalTheme.body())
                            .italic()
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                        if !item.wikipediaSummary.isEmpty {
                            Text(item.wikipediaSummary)
                                .font(HikeJournalTheme.body())
                                .foregroundStyle(HikeJournalTheme.ink)
                                .padding(.top, 16)
                        }
                        if let url = URL(string: item.wikipediaUrl) {
                            Link("Read source", destination: url)
                                .font(HikeJournalTheme.label(15, relativeTo: .headline))
                                .foregroundStyle(HikeJournalTheme.moss)
                                .padding(.top, 14)
                        }
                        if let mapSightings = mapSightings, item.taxonId != nil {
                            Button("Map sightings", action: mapSightings)
                                .font(HikeJournalTheme.label(15, relativeTo: .headline))
                                .foregroundStyle(HikeJournalTheme.moss)
                                .padding(.top, 16)
                        }
                        let credit = [item.referencePhotoAttribution, item.referencePhotoLicenseCode]
                            .filter { !$0.isEmpty }.joined(separator: " · ")
                        if !credit.isEmpty {
                            Text(credit)
                                .font(HikeJournalTheme.body(12, relativeTo: .caption))
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                                .padding(.top, 18)
                        }
                    }
                    .padding(.horizontal, 22)
                    .padding(.bottom, 36)
                }
            }
            .navigationTitle("Species note")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } } }
        }
    }
}

private extension BriefingItem {
    var displayPhotoURL: String {
        let collection = collectionPhotoUrl?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return collection.isEmpty ? referencePhotoUrl : collection
    }
}

private struct BriefingSightingsSelection: Identifiable {
    let value: QuestSightingsMap
    var id: String { "\(value.taxonId)|\(value.questId)" }
}

private struct BriefingSightingsMapView: View {
    @ObservedObject var model: AppModel
    let value: QuestSightingsMap
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if let style = model.maps.style,
                   let surface = try? HikeJournalMapSurface(
                       scene: scene,
                       style: style,
                       styleCredential: model.maps.styleCredential,
                       cameraBehavior: .fitOnce
                   ) {
                    surface.frame(maxHeight: .infinity)
                }
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        Text(value.sourceGuidance)
                            .font(HikeJournalTheme.body(13))
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                            .padding(16)
                        ForEach(value.sightings) { sighting in
                            HStack(spacing: 12) {
                                JournalRemoteImage(urlString: sighting.photoUrl, fallback: "mappin")
                                    .frame(width: 58, height: 58)
                                    .clipped()
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(sighting.placeGuess.isEmpty ? value.commonName : sighting.placeGuess)
                                        .font(HikeJournalTheme.label(14, relativeTo: .headline))
                                    Text(JournalDate.display(sighting.observedOn))
                                        .font(HikeJournalTheme.body(13))
                                        .foregroundStyle(HikeJournalTheme.inkMuted)
                                }
                                Spacer()
                                if let url = URL(string: sighting.uri) {
                                    Link(destination: url) { Image(systemName: "arrow.up.right.square") }
                                        .accessibilityLabel("Open iNaturalist sighting")
                                }
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 9)
                            Divider().overlay(HikeJournalTheme.line)
                        }
                    }
                }
                .frame(maxHeight: 260)
                .background(HikeJournalTheme.paper)
            }
            .navigationTitle(value.commonName)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } } }
        }
    }

    private var scene: MapScene {
        let points = value.sightings.compactMap { sighting -> MapPoint? in
            guard let coordinate = try? GeoCoordinate(
                latitude: sighting.latitude,
                longitude: sighting.longitude
            ) else { return nil }
            return try? MapPoint(
                id: "discovery:\(sighting.id)",
                kind: .discovery,
                title: value.commonName,
                detail: sighting.placeGuess,
                coordinate: coordinate
            )
        }
        return MapScene(points: points)
    }
}

private func forecastClock(_ value: String?) -> String {
    guard let value, !value.isEmpty else { return "—" }
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.dateFormat = "yyyy-MM-dd'T'HH:mm"
    guard let date = formatter.date(from: value) else { return value.split(separator: "T").last.map(String.init) ?? value }
    formatter.locale = .current
    formatter.dateFormat = "h:mm a"
    return formatter.string(from: date)
}

private func shortWeekday(_ value: String) -> String {
    let formatter = DateFormatter()
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.dateFormat = "yyyy-MM-dd"
    guard let date = formatter.date(from: value) else { return String(value.prefix(3)).uppercased() }
    formatter.locale = .current
    formatter.dateFormat = "EEE"
    return formatter.string(from: date).uppercased()
}

private extension ISO8601DateFormatter {
    static let day: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = .current
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
}

private extension PlaceProfile {
    func withResolvedName(fallback: String) -> PlaceProfile {
        let cleanFallback = fallback.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanFallback.isEmpty,
              cleanName.isEmpty || cleanName.caseInsensitiveCompare("Unknown place") == .orderedSame else {
            return self
        }
        return PlaceProfile(
            locationId: locationId,
            name: cleanFallback,
            latitude: latitude,
            longitude: longitude,
            firstVisit: firstVisit,
            latestVisit: latestVisit,
            outingCount: outingCount,
            totalDistanceMiles: totalDistanceMiles,
            totalDurationSeconds: totalDurationSeconds,
            observationCount: observationCount,
            speciesCount: speciesCount,
            taxonCounts: taxonCounts,
            taxonGroups: taxonGroups,
            seasonalHistory: seasonalHistory,
            visits: visits,
            guidance: guidance,
            forecast: forecast,
            riverGauges: riverGauges,
            liveConditionsNotice: liveConditionsNotice
        )
    }

    func withLocalVisitEvidence(hikes: [Hike], locationID: String) -> PlaceProfile {
        let localHikes = hikes
            .filter { !$0.isStandalone && $0.primaryLocationId == locationID }
            .sorted {
                if $0.hikeDate != $1.hikeDate { return $0.hikeDate > $1.hikeDate }
                return $0.id > $1.id
            }
        guard !localHikes.isEmpty else { return self }

        let existingIDs = Set(visits.map(\.hikeId))
        let localVisits = localHikes.map { hike in
            PlaceVisit(
                hikeId: hike.id,
                title: hike.title,
                hikeDate: hike.hikeDate,
                distanceMiles: hike.distanceMiles,
                observationCount: 0,
                speciesCount: hike.speciesCount,
                newSpeciesCount: 0,
                cumulativeSpeciesCount: hike.speciesCount,
                coverUrl: hike.coverUrl
            )
        }
        let mergedVisits = (visits + localVisits.filter { !existingIDs.contains($0.hikeId) })
            .sorted {
                if $0.hikeDate != $1.hikeDate { return $0.hikeDate > $1.hikeDate }
                return $0.hikeId > $1.hikeId
            }
        let localDates = localHikes.map(\.hikeDate).filter { !$0.isEmpty }
        let localDistance = localHikes.compactMap(\.distanceMiles).reduce(0, +)
        let localDuration = localHikes.compactMap(\.durationSeconds).reduce(0, +)

        return PlaceProfile(
            locationId: self.locationId,
            name: name,
            latitude: latitude,
            longitude: longitude,
            firstVisit: minNonEmpty(firstVisit, localDates.min()),
            latestVisit: maxNonEmpty(latestVisit, localDates.max()),
            outingCount: max(outingCount, localHikes.count),
            totalDistanceMiles: max(totalDistanceMiles, localDistance),
            totalDurationSeconds: max(totalDurationSeconds, localDuration),
            observationCount: observationCount,
            speciesCount: speciesCount,
            taxonCounts: taxonCounts,
            taxonGroups: taxonGroups,
            seasonalHistory: seasonalHistory,
            visits: mergedVisits,
            guidance: guidance,
            forecast: forecast,
            riverGauges: riverGauges,
            liveConditionsNotice: liveConditionsNotice
        )
    }

    private func minNonEmpty(_ lhs: String?, _ rhs: String?) -> String? {
        [lhs, rhs].compactMap { value in
            let clean = value?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return clean.isEmpty ? nil : clean
        }.min()
    }

    private func maxNonEmpty(_ lhs: String?, _ rhs: String?) -> String? {
        [lhs, rhs].compactMap { value in
            let clean = value?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return clean.isEmpty ? nil : clean
        }.max()
    }
}
