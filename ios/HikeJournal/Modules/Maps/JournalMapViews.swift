import Foundation
import HikeJournalDomain
import HikeJournalMaps
import SwiftUI

struct JournalMapWorkspaceView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var journal: JournalStore
    @ObservedObject private var maps: MapStore
    @ObservedObject private var recording: RecordingStore
    @ObservedObject private var authentication: AuthenticationStore

    @State private var showingTrails = false
    @State private var showingOfflineMaps = false
    @State private var showingTextAlternative = false
    @State private var selectedPoint: MapPointSelection?

    init(model: AppModel) {
        self.model = model
        _journal = ObservedObject(wrappedValue: model.journal)
        _maps = ObservedObject(wrappedValue: model.maps)
        _recording = ObservedObject(wrappedValue: model.recording)
        _authentication = ObservedObject(wrappedValue: model.authentication)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                mapHeader
                mapContent
                mapControls
            }
            .background(HikeJournalTheme.paper)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await refresh() }
                    } label: {
                        if journal.activeLoads.contains("map") {
                            ProgressView()
                        } else {
                            Image(systemName: "arrow.clockwise")
                        }
                    }
                    .accessibilityLabel("Refresh map")
                    .disabled(journal.activeLoads.contains("map"))
                }
            }
            .task(id: accountIdentity) {
                await maps.start()
                await refresh()
            }
            .sheet(isPresented: $showingTrails) {
                TrailOverlayPicker(maps: maps)
            }
            .sheet(isPresented: $showingOfflineMaps) {
                OfflineMapsView(
                    maps: maps,
                    authentication: authentication,
                    storefront: model.storefront,
                    webBaseURL: model.configuration.webBaseURL,
                    scene: scene
                )
            }
            .sheet(isPresented: $showingTextAlternative) {
                MapTextAlternativeView(snapshot: MapAccessibility.snapshot(for: scene))
            }
            .sheet(item: $selectedPoint) { selection in
                MapPointInspector(selection: selection) {
                    openHike(selection.hikeID)
                }
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
            }
            .onAppear {
                // Returning from a journal detail must restore the global map
                // dataset; a detail load should never become the map's filter.
                Task { await refresh() }
            }
        }
    }

    private var mapHeader: some View {
        HStack(alignment: .lastTextBaseline) {
            VStack(alignment: .leading, spacing: 0) {
                Text("HIKEJOURNAL")
                    .font(HikeJournalTheme.display(31, relativeTo: .title))
                    .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.91))
                    .accessibilityAddTraits(.isHeader)
                Text("Routes, sightings, and trail lines")
                    .font(HikeJournalTheme.label(12))
                    .tracking(0.5)
                    .foregroundStyle(Color(red: 0.72, green: 0.80, blue: 0.73))
            }
            Spacer()
            if recording.phase == .recording || recording.phase == .paused {
                Label(
                    recording.phase == .paused ? "Paused" : "Recording",
                    systemImage: recording.phase == .paused ? "pause.fill" : "location.fill"
                )
                .font(HikeJournalTheme.label(12))
                .foregroundStyle(HikeJournalTheme.trail)
                .accessibilityLabel(recording.phase == .paused ? "Route recording paused" : "Route recording active")
            }
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 12)
        .background(Color(red: 0.07, green: 0.16, blue: 0.12))
    }

    @ViewBuilder
    private var mapContent: some View {
        if let style = maps.style,
           let surface = try? HikeJournalMapSurface(
               scene: scene,
               style: style,
               styleCredential: maps.styleCredential,
               cameraBehavior: .fitOnce,
               cameraPadding: EdgeInsets(top: 44, leading: 34, bottom: 58, trailing: 34),
               onSelectPoint: { point in
                   selectedPoint = selection(for: point)
               }
           ) {
            surface
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .transition(.opacity)
        } else {
            MapPreparationView(
                isLoading: maps.isStarting,
                errorMessage: maps.errorMessage,
                retry: { Task { await maps.start() } }
            )
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .transition(.opacity)
        }
    }

    private var mapControls: some View {
        VStack(spacing: 0) {
            if scene.allCoordinates.isEmpty {
                HStack(spacing: 9) {
                    Image(systemName: "map")
                        .foregroundStyle(HikeJournalTheme.trailText)
                    Text(emptyMapMessage)
                        .font(HikeJournalTheme.body(14))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 9)
                Divider().overlay(HikeJournalTheme.line)
            } else if let status = journal.statusMessage ?? maps.statusMessage {
                Text(status)
                    .font(HikeJournalTheme.body(13))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 18)
                    .padding(.vertical, 7)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                Divider().overlay(HikeJournalTheme.line)
            }

            HStack(spacing: 0) {
                MapControlButton(
                    title: "Trails",
                    symbol: maps.selectedTrailOverlayIDs.isEmpty ? "point.topleft.down.to.point.bottomright.curvepath" : "point.topleft.down.to.point.bottomright.curvepath.fill"
                ) { showingTrails = true }
                MapControlButton(title: "Offline", symbol: "arrow.down.circle") {
                    showingOfflineMaps = true
                }
                MapControlButton(title: "Map details", symbol: "list.bullet") {
                    showingTextAlternative = true
                }
            }
            .frame(minHeight: 58)
        }
        .background(HikeJournalTheme.paper)
    }

    private var scene: MapScene {
        JournalMapSceneFactory.make(
            routes: journal.routes,
            hikes: journal.hikes,
            details: journal.details,
            sightings: journal.sightings,
            tracking: recording.snapshot,
            selectedTrailOverlayIDs: maps.selectedTrailOverlayIDs
        )
    }

    private var accountIdentity: String {
        switch authentication.phase {
        case .restoring: "restoring"
        case .signedOut: "signed-out"
        case let .signedIn(account): account.userID ?? account.subject
        }
    }

    private var emptyMapMessage: String {
        switch authentication.phase {
        case .restoring:
            "Opening your saved map…"
        case .signedOut:
            "Sign in to place your routes and sightings on the map."
        case .signedIn:
            "Record an outing or add a geotagged photo to begin this map."
        }
    }

    private func refresh() async {
        async let mapRefresh: Void = journal.refreshMap()
        if journal.hikes.isEmpty {
            await journal.refreshHikes()
        }
        await mapRefresh
    }

    private func selection(for point: MapPoint) -> MapPointSelection {
        let sourceID = point.id.split(separator: ":", maxSplits: 1).dropFirst().first.map(String.init)
        if point.id.hasPrefix("media:"),
           let sourceID,
           let sighting = journal.sightings.first(where: { $0.id == sourceID }) {
            return MapPointSelection(
                point: point,
                imageURL: URL(string: sighting.url),
                hikeID: sighting.hikeId,
                outingTitle: sighting.hikeTitle,
                observedAt: sighting.takenAt ?? sighting.hikeDate
            )
        }
        if point.id.hasPrefix("media:"), let sourceID {
            for hike in journal.details.values {
                if let photo = hike.photos.first(where: { $0.id == sourceID }) {
                    return MapPointSelection(
                        point: point,
                        imageURL: URL(string: photo.url),
                        hikeID: hike.id,
                        outingTitle: hike.title,
                        observedAt: photo.takenAt ?? hike.hikeDate
                    )
                }
            }
        }
        if point.id.hasPrefix("field-mark:"), let sourceID {
            for hike in journal.details.values where hike.fieldMarks.contains(where: { $0.id == sourceID }) {
                return MapPointSelection(
                    point: point,
                    imageURL: nil,
                    hikeID: hike.id,
                    outingTitle: hike.title,
                    observedAt: hike.fieldMarks.first(where: { $0.id == sourceID })?.markedAt
                )
            }
        }
        return MapPointSelection(
            point: point,
            imageURL: nil,
            hikeID: nil,
            outingTitle: point.detail,
            observedAt: nil
        )
    }

    private func openHike(_ hikeID: String?) {
        guard let hikeID, UUID(uuidString: hikeID) != nil,
              let url = URL(string: "\(model.configuration.callbackScheme)://hike/\(hikeID)") else {
            model.selectedTab = .journal
            return
        }
        selectedPoint = nil
        _ = model.handleDeepLink(url)
    }
}

private struct MapPointSelection: Identifiable {
    let point: MapPoint
    let imageURL: URL?
    let hikeID: String?
    let outingTitle: String?
    let observedAt: String?

    var id: String { point.id }
}

private struct MapPointInspector: View {
    let selection: MapPointSelection
    let openHike: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        if let imageURL = selection.imageURL {
                            JournalRemoteImage(
                                urlString: imageURL.absoluteString,
                                fallback: "photo"
                            )
                                .frame(height: 270)
                                .clipped()
                        }
                        Text(selection.point.kind.accessibilityName.uppercased())
                            .font(HikeJournalTheme.label(11))
                            .tracking(1.2)
                            .foregroundStyle(HikeJournalTheme.trailText)
                            .padding(.top, selection.imageURL == nil ? 12 : 22)
                        Text(selection.point.title)
                            .font(HikeJournalTheme.display(34, relativeTo: .title))
                            .foregroundStyle(HikeJournalTheme.ink)
                            .padding(.top, 3)
                        if let outingTitle = selection.outingTitle, !outingTitle.isEmpty {
                            Text(outingTitle)
                                .font(HikeJournalTheme.body())
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                                .padding(.top, 5)
                        }
                        if let observedAt = selection.observedAt, !observedAt.isEmpty {
                            Text(observedAt)
                                .font(HikeJournalTheme.body(14))
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                                .padding(.top, 3)
                        }
                        if selection.hikeID != nil {
                            Button {
                                dismiss()
                                openHike()
                            } label: {
                                HStack {
                                    Text("Open journal")
                                    Spacer()
                                    Image(systemName: "arrow.right")
                                }
                            }
                            .buttonStyle(TrailButtonStyle())
                            .padding(.top, 24)
                        }
                    }
                    .padding(.horizontal, 22)
                    .padding(.bottom, 36)
                }
                .scrollIndicators(.hidden)
            }
            .navigationTitle("Map point")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

private struct MapControlButton: View {
    let title: String
    let symbol: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: symbol)
                    .font(.system(size: 18, weight: .semibold))
                Text(title)
                    .font(HikeJournalTheme.label(12))
            }
            .foregroundStyle(HikeJournalTheme.moss)
            .frame(maxWidth: .infinity, minHeight: 52)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

private struct MapPreparationView: View {
    let isLoading: Bool
    let errorMessage: String?
    let retry: () -> Void

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.10, green: 0.25, blue: 0.18),
                    Color(red: 0.28, green: 0.39, blue: 0.25)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            TrailNotebookIllustration()
                .opacity(0.32)
                .padding(34)
            VStack(spacing: 10) {
                if isLoading {
                    ProgressView()
                        .tint(Color(red: 1, green: 0.96, blue: 0.86))
                    Text("Preparing the trail map…")
                } else {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.title2)
                    Text(errorMessage ?? "The map isn't ready yet.")
                        .multilineTextAlignment(.center)
                    Button("Try again", action: retry)
                        .font(HikeJournalTheme.label(15, relativeTo: .headline))
                        .foregroundStyle(HikeJournalTheme.trail)
                        .padding(.top, 4)
                }
            }
            .font(HikeJournalTheme.body())
            .foregroundStyle(Color(red: 1, green: 0.96, blue: 0.86))
            .padding(28)
        }
        .accessibilityElement(children: .combine)
    }
}

private struct TrailOverlayPicker: View {
    @ObservedObject var maps: MapStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(NationalScenicTrailCatalog.all) { trail in
                        Button {
                            if maps.selectedTrailOverlayIDs.contains(trail.id) {
                                maps.selectedTrailOverlayIDs.remove(trail.id)
                            } else {
                                maps.selectedTrailOverlayIDs.insert(trail.id)
                            }
                        } label: {
                            HStack(alignment: .top, spacing: 13) {
                                Image(systemName: maps.selectedTrailOverlayIDs.contains(trail.id) ? "checkmark.circle.fill" : "circle")
                                    .foregroundStyle(maps.selectedTrailOverlayIDs.contains(trail.id) ? HikeJournalTheme.trailText : HikeJournalTheme.inkMuted)
                                    .padding(.top, 2)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(trail.name)
                                        .font(HikeJournalTheme.label(16, relativeTo: .headline))
                                        .foregroundStyle(HikeJournalTheme.ink)
                                    Text("\(trail.shortName) · \(trail.states)")
                                        .font(HikeJournalTheme.body(14))
                                        .foregroundStyle(HikeJournalTheme.inkMuted)
                                }
                            }
                        }
                        .buttonStyle(.plain)
                        .accessibilityAddTraits(maps.selectedTrailOverlayIDs.contains(trail.id) ? .isSelected : [])
                    }
                } header: {
                    Text("National Scenic Trails")
                } footer: {
                    Text("Trail centerlines stream from their credited public ArcGIS sources. Base-map downloads do not cache these dynamic trail overlays.")
                }
            }
            .scrollContentBackground(.hidden)
            .background(ParchmentBackground())
            .navigationTitle("Trail lines")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Clear") { maps.selectedTrailOverlayIDs.removeAll() }
                        .disabled(maps.selectedTrailOverlayIDs.isEmpty)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

private struct MapTextAlternativeView: View {
    let snapshot: MapAccessibilitySnapshot
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Everything on the map, in words.")
                            .font(HikeJournalTheme.display(34, relativeTo: .title))
                            .foregroundStyle(HikeJournalTheme.ink)
                        Text(snapshot.summary)
                            .font(HikeJournalTheme.body())
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                            .padding(.top, 8)
                        Divider().overlay(HikeJournalTheme.line).padding(.vertical, 22)
                        if snapshot.items.isEmpty {
                            Text("No mapped items yet.")
                                .font(HikeJournalTheme.body())
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        } else {
                            ForEach(snapshot.items) { item in
                                Text(item.label)
                                    .font(HikeJournalTheme.body(16))
                                    .foregroundStyle(HikeJournalTheme.ink)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.vertical, 10)
                                Divider().overlay(HikeJournalTheme.line)
                            }
                        }
                    }
                    .padding(24)
                }
            }
            .navigationTitle("Map details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

private struct OfflineRegionChoice: Identifiable {
    let id: String
    let name: String
    let coordinates: [GeoCoordinate]
    let detail: String
}

private struct OfflineMapsView: View {
    @ObservedObject var maps: MapStore
    @ObservedObject var authentication: AuthenticationStore
    @ObservedObject var storefront: StorefrontStore
    let webBaseURL: URL?
    let scene: MapScene

    @Environment(\.dismiss) private var dismiss
    @State private var selectedChoiceID = ""
    @State private var downloadName = ""
    @State private var minimumZoom = 8.0
    @State private var maximumZoom = 14.0
    @State private var showingPaywall = false
    @State private var packPendingDeletion: OfflinePackSnapshot?

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        intro
                        Divider().overlay(HikeJournalTheme.line).padding(.vertical, 24)
                        downloadSection
                        Divider().overlay(HikeJournalTheme.line).padding(.vertical, 24)
                        savedSection
                    }
                    .padding(.horizontal, 22)
                    .padding(.vertical, 20)
                }
                .scrollIndicators(.hidden)
            }
            .navigationTitle("Offline maps")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
            .task {
                await maps.refreshOfflinePacks()
                establishSelection()
            }
            .onChange(of: selectedChoiceID) { _, _ in
                if let choice = selectedChoice { downloadName = choice.name }
            }
            .sheet(isPresented: $showingPaywall) {
                PlusPaywallView(
                    storefront: storefront,
                    privacyURL: webBaseURL?.appendingPathComponent("privacy")
                )
            }
            .confirmationDialog(
                "Remove this offline region?",
                isPresented: Binding(
                    get: { packPendingDeletion != nil },
                    set: { if !$0 { packPendingDeletion = nil } }
                ),
                titleVisibility: .visible,
                presenting: packPendingDeletion
            ) { pack in
                Button("Remove “\(pack.context.name)”", role: .destructive) {
                    Task { await maps.delete(packID: pack.id) }
                }
                Button("Keep region", role: .cancel) {}
            } message: { _ in
                Text("The downloaded map data will be removed from this iPhone. Your journal and recorded route stay intact.")
            }
        }
    }

    private var intro: some View {
        VStack(alignment: .leading, spacing: 7) {
            Text("Carry the trail beyond signal.")
                .font(HikeJournalTheme.display(34, relativeTo: .title))
                .foregroundStyle(HikeJournalTheme.ink)
            Text("Download the base map around a recorded outing. Route lines and journal data already remain available from HikeJournal's encrypted offline store.")
                .font(HikeJournalTheme.body())
                .foregroundStyle(HikeJournalTheme.inkMuted)
                .fixedSize(horizontal: false, vertical: true)
            Label(networkDescription, systemImage: maps.activeNetworkPolicy == .wifiOnly ? "wifi" : "antenna.radiowaves.left.and.right")
                .font(HikeJournalTheme.label(13))
                .foregroundStyle(HikeJournalTheme.moss)
                .padding(.top, 5)
        }
    }

    @ViewBuilder
    private var downloadSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("DOWNLOAD A REGION")
                .font(HikeJournalTheme.label(12))
                .tracking(1.2)
                .foregroundStyle(HikeJournalTheme.trailText)

            if authentication.entitlement?.allows("offline_maps") != true {
                Text("Offline base maps are a HikeJournal Plus feature.")
                    .font(HikeJournalTheme.body())
                    .foregroundStyle(HikeJournalTheme.ink)
                Text("Your routes, field notes, and cached journal remain available without a map download.")
                    .font(HikeJournalTheme.body(14))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                Button("Explore HikeJournal Plus") { showingPaywall = true }
                    .buttonStyle(TrailButtonStyle())
            } else if choices.isEmpty {
                Text("Record a route first")
                    .font(HikeJournalTheme.label(17, relativeTo: .headline))
                    .foregroundStyle(HikeJournalTheme.ink)
                Text("A completed or in-progress GPS route gives HikeJournal safe download bounds and prevents unexpectedly large map downloads.")
                    .font(HikeJournalTheme.body(15))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            } else {
                Picker("Recorded route", selection: $selectedChoiceID) {
                    ForEach(choices) { choice in
                        Text(choice.name).tag(choice.id)
                    }
                }
                .pickerStyle(.menu)
                .tint(HikeJournalTheme.moss)

                if let selectedChoice {
                    Text(selectedChoice.detail)
                        .font(HikeJournalTheme.body(14))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }

                TextField("Offline region name", text: $downloadName)
                    .textInputAutocapitalization(.words)
                    .padding(.horizontal, 12)
                    .frame(minHeight: 46)
                    .background(HikeJournalTheme.paper)
                    .overlay {
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(HikeJournalTheme.line, lineWidth: 1)
                    }

                Stepper("Map detail: zoom \(Int(maximumZoom))", value: $maximumZoom, in: 12...16, step: 1)
                    .font(HikeJournalTheme.body(15))

                if let estimate {
                    Text("Estimated \(formatBytes(estimate.lowerBoundBytes))–\(formatBytes(estimate.upperBoundBytes)), depending on the map provider's tiles.")
                        .font(HikeJournalTheme.body(13))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }

                Button {
                    guard let selectedChoice else { return }
                    Task {
                        _ = await maps.createOfflinePack(
                            name: downloadName,
                            coordinates: selectedChoice.coordinates,
                            minimumZoomLevel: minimumZoom,
                            maximumZoomLevel: maximumZoom
                        )
                    }
                } label: {
                    HStack {
                        if maps.isManagingOfflinePacks { ProgressView().tint(HikeJournalTheme.paper) }
                        Text("Download map")
                        Spacer()
                        Image(systemName: "arrow.down")
                    }
                }
                .buttonStyle(TrailButtonStyle())
                .disabled(downloadName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || maps.isManagingOfflinePacks)
            }

            if let error = maps.errorMessage {
                Label(error, systemImage: "exclamationmark.triangle.fill")
                    .font(HikeJournalTheme.body(14))
                    .foregroundStyle(HikeJournalTheme.error)
                    .fixedSize(horizontal: false, vertical: true)
            } else if let status = maps.statusMessage {
                Label(status, systemImage: "checkmark.circle.fill")
                    .font(HikeJournalTheme.body(14))
                    .foregroundStyle(HikeJournalTheme.moss)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private var savedSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("ON THIS IPHONE")
                    .font(HikeJournalTheme.label(12))
                    .tracking(1.2)
                    .foregroundStyle(HikeJournalTheme.trailText)
                Spacer()
                Text(formatBytes(maps.totalStorageBytes))
                    .font(HikeJournalTheme.label(12))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }
            .padding(.bottom, 10)

            if maps.offlinePacks.isEmpty {
                Text("No offline regions downloaded yet.")
                    .font(HikeJournalTheme.body())
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                    .padding(.vertical, 12)
            } else {
                ForEach(maps.offlinePacks) { pack in
                    OfflinePackRow(
                        pack: pack,
                        isBusy: maps.isManagingOfflinePacks,
                        resume: { Task { await maps.resume(packID: pack.id) } },
                        suspend: { Task { await maps.suspend(packID: pack.id) } },
                        remove: { packPendingDeletion = pack }
                    )
                    Divider().overlay(HikeJournalTheme.line)
                }
            }
        }
    }

    private var choices: [OfflineRegionChoice] {
        scene.routes.compactMap { route in
            let coordinates = route.segments.flatMap(\.coordinates)
            guard MapStore.downloadBounds(for: coordinates) != nil else { return nil }
            let pointCount = coordinates.count
            return OfflineRegionChoice(
                id: route.id,
                name: route.name.isEmpty ? "Recorded outing" : route.name,
                coordinates: coordinates,
                detail: "\(route.segments.count) route \(route.segments.count == 1 ? "segment" : "segments") · \(pointCount) GPS points"
            )
        }
    }

    private var selectedChoice: OfflineRegionChoice? {
        choices.first { $0.id == selectedChoiceID } ?? choices.first
    }

    private var estimate: OfflineStorageEstimate? {
        guard let selectedChoice,
              let bounds = MapStore.downloadBounds(for: selectedChoice.coordinates) else { return nil }
        return OfflineStorageEstimate.estimate(
            bounds: bounds,
            minimumZoomLevel: minimumZoom,
            maximumZoomLevel: maximumZoom
        )
    }

    private var networkDescription: String {
        maps.activeNetworkPolicy == .wifiOnly
            ? "Downloads wait for Wi-Fi; map browsing can still use the configured provider."
            : "Offline map downloads may use Wi-Fi or cellular data."
    }

    private func establishSelection() {
        guard selectedChoiceID.isEmpty, let first = choices.first else { return }
        selectedChoiceID = first.id
        downloadName = first.name
    }
}

private struct OfflinePackRow: View {
    let pack: OfflinePackSnapshot
    let isBusy: Bool
    let resume: () -> Void
    let suspend: () -> Void
    let remove: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(pack.context.name)
                        .font(HikeJournalTheme.label(17, relativeTo: .headline))
                        .foregroundStyle(HikeJournalTheme.ink)
                    Text(stateLabel)
                        .font(HikeJournalTheme.body(13))
                        .foregroundStyle(stateColor)
                }
                Spacer()
                Menu {
                    if pack.state == .downloading {
                        Button("Pause download", action: suspend)
                    } else if !pack.isComplete {
                        Button("Resume download", action: resume)
                    }
                    Button("Remove download", role: .destructive, action: remove)
                } label: {
                    Image(systemName: "ellipsis.circle")
                        .font(.title3)
                        .foregroundStyle(HikeJournalTheme.moss)
                        .frame(width: 44, height: 44)
                }
                .disabled(isBusy)
            }
            if let fraction = pack.progress.fractionCompleted, !pack.isComplete {
                ProgressView(value: fraction)
                    .tint(HikeJournalTheme.trailText)
                    .contentTransition(.numericText())
            }
            Text("\(formatBytes(pack.progress.bytesCompleted)) downloaded · zoom \(Int(pack.context.minimumZoomLevel))–\(Int(pack.context.maximumZoomLevel))")
                .font(HikeJournalTheme.body(12, relativeTo: .caption))
                .foregroundStyle(HikeJournalTheme.inkMuted)
            if let failure = pack.failure {
                Text(failure.message)
                    .font(HikeJournalTheme.body(13))
                    .foregroundStyle(HikeJournalTheme.error)
            }
        }
        .padding(.vertical, 12)
    }

    private var stateLabel: String {
        switch pack.state {
        case .unknown: "Checking download…"
        case .inactive: "Paused"
        case .downloading: "Downloading"
        case .complete: "Ready offline"
        case .failed: "Needs attention"
        case .invalid: "Unavailable"
        }
    }

    private var stateColor: Color {
        pack.state == .failed || pack.state == .invalid
            ? HikeJournalTheme.error
            : HikeJournalTheme.inkMuted
    }
}

private func formatBytes(_ bytes: UInt64) -> String {
    ByteCountFormatter.string(fromByteCount: Int64(clamping: bytes), countStyle: .file)
}
