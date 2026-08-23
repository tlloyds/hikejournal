import CoreLocation
import HikeJournalMaps
import HikeJournalTracking
import SwiftUI
import UIKit

struct RootShellView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var journal: JournalStore

    init(model: AppModel) {
        self.model = model
        _journal = ObservedObject(wrappedValue: model.journal)
    }

    var body: some View {
        Group {
            if journal.isPreparingAccount {
                JournalBootstrapView()
            } else {
                TabView(selection: $model.selectedTab) {
                    JournalLibraryView(model: model)
                        .tabItem { Label("Journal", systemImage: "book.closed.fill") }
                        .tag(AppTab.journal)

                    FieldGuideWorkspaceView(model: model)
                        .tabItem { Label("Field Guide", systemImage: "leaf.fill") }
                        .tag(AppTab.fieldGuide)

                    RecordingHomeView(model: model)
                        .tabItem { Label("Record", systemImage: "location.fill") }
                        .tag(AppTab.record)

                    JournalMapWorkspaceView(model: model)
                        .tabItem { Label("Map", systemImage: "map.fill") }
                        .tag(AppTab.map)

                    SettingsHomeView(model: model)
                        .tabItem { Label("Settings", systemImage: "gearshape.fill") }
                        .tag(AppTab.settings)
                }
                .toolbarBackground(HikeJournalTheme.paper, for: .tabBar)
                .toolbarBackground(.visible, for: .tabBar)
                .sheet(
                    item: Binding(
                        get: { journal.pendingCelebration },
                        set: { if $0 == nil { journal.dismissCelebration() } }
                    )
                ) { celebration in
                    FieldCelebrationView(
                        celebration: celebration,
                        dismiss: { journal.dismissCelebration() }
                    )
                }
                .sheet(
                    isPresented: Binding(
                        get: { model.isSettingsPresented },
                        set: { if !$0 { model.closeSettings() } }
                    )
                ) {
                    SettingsHomeView(model: model)
                }
            }
        }
    }
}

private struct JournalHomeView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        Text("HikeJournal")
                            .font(HikeJournalTheme.display(46, relativeTo: .largeTitle))
                            .foregroundStyle(HikeJournalTheme.moss)
                            .accessibilityAddTraits(.isHeader)

                        Text("Hikes, Photos, and Observations")
                            .font(HikeJournalTheme.body(18))
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                            .padding(.top, 2)

                        Divider()
                            .overlay(HikeJournalTheme.line)
                            .padding(.vertical, 26)

                        TrailNotebookIllustration()
                            .frame(height: 178)

                        Text("Getting Started")
                            .font(HikeJournalTheme.display(33, relativeTo: .title))
                            .foregroundStyle(HikeJournalTheme.ink)
                            .padding(.top, 24)

                        Text("Record an outing or add one after the trail. Routes, photos, and field notes will stay together here.")
                            .font(HikeJournalTheme.body())
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.top, 8)

                        Button {
                            model.openRecording()
                        } label: {
                            HStack {
                                Text("Prepare an outing")
                                Spacer()
                                Image(systemName: "arrow.right")
                            }
                        }
                        .buttonStyle(TrailButtonStyle())
                        .padding(.top, 24)
                    }
                    .padding(.horizontal, 24)
                    .padding(.top, 18)
                    .padding(.bottom, 42)
                }
                .scrollIndicators(.hidden)
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        model.openSettings()
                    } label: {
                        Image(systemName: "person.crop.circle")
                    }
                    .accessibilityLabel("Account and settings")
                }
            }
        }
    }
}

private struct RecordingHomeView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var recording: RecordingStore
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.openURL) private var openURL
    @State private var showingLocationPrimer = false
    @State private var compassPulse = false
    @State private var showingFieldMark = false
    @State private var showingFinish = false
    @State private var showingDiscard = false

    init(model: AppModel) {
        self.model = model
        _recording = ObservedObject(wrappedValue: model.recording)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                if recording.phase == .idle || recording.phase == .finished {
                    trailhead
                } else {
                    activeRecorder
                }
            }
            .navigationTitle("Record")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showingLocationPrimer) {
                LocationPrimerView {
                    showingLocationPrimer = false
                    model.requestWhenInUseLocation()
                }
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
            }
            .sheet(isPresented: $showingFieldMark) {
                FieldMarkComposer { type, note in
                    let saved = await recording.addFieldMark(type: type, note: note)
                    if saved { showingFieldMark = false }
                }
                .presentationDetents([.medium])
                .presentationDragIndicator(.visible)
            }
            .sheet(isPresented: $showingFinish) {
                FinishRecordingSheet { title, notes in
                    await recording.finish(title: title, notes: notes)
                    if recording.phase == .finished { showingFinish = false }
                }
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
            }
            .confirmationDialog(
                "Discard this recording?",
                isPresented: $showingDiscard,
                titleVisibility: .visible
            ) {
                Button("Discard recording", role: .destructive) {
                    Task { await recording.discard() }
                }
                Button("Keep it", role: .cancel) {}
            } message: {
                Text("Its saved route and unsynced field marks will be removed from this iPhone.")
            }
            .alert(
                "Recording needs attention",
                isPresented: Binding(
                    get: { recording.errorMessage != nil },
                    set: { if !$0 { recording.clearError() } }
                )
            ) {
                Button("OK") { recording.clearError() }
            } message: {
                Text(recording.errorMessage ?? "")
            }
        }
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.35).repeatForever(autoreverses: true)) {
                compassPulse = true
            }
        }
        .onChange(of: model.pendingDeepLink) { _, value in
            guard case let .tracking(action)? = value else { return }
            Task {
                switch action {
                case .open:
                    break
                case .start:
                    if recording.phase == .idle || recording.phase == .finished {
                        await recording.start()
                    }
                case .pause:
                    if recording.phase == .recording { await recording.pause() }
                case .resume:
                    if recording.phase == .paused { await recording.resume() }
                case .stop:
                    if recording.phase == .recording { await recording.pause() }
                    if recording.phase == .paused { showingFinish = true }
                }
                model.consumeDeepLink()
            }
        }
        .task(id: recording.phase) {
            guard recording.phase != .idle, recording.phase != .finished else { return }
            await model.maps.start()
            guard recording.phase == .recording else { return }
            while !Task.isCancelled {
                await recording.refreshSnapshot()
                try? await Task.sleep(nanoseconds: 1_000_000_000)
            }
        }
    }

    private var trailhead: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                ZStack(alignment: .bottomLeading) {
                    BrandLandscape()
                        .frame(height: 238)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(recording.phase == .finished ? "ROUTE SAVED" : "TRAILHEAD")
                            .font(HikeJournalTheme.label(12))
                            .tracking(1.4)
                        Text(recording.phase == .finished ? "A walk worth keeping." : "Ready when you are.")
                            .font(HikeJournalTheme.display(38, relativeTo: .largeTitle))
                    }
                    .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.91))
                    .padding(22)
                }

                VStack(alignment: .leading, spacing: 0) {
                    if let finished = recording.lastFinishedRecording {
                        Text("The route is safe on this iPhone and queued with its journal for cloud sync.")
                            .font(HikeJournalTheme.body(18))
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                        HStack(spacing: 30) {
                            RecorderMetric(
                                value: finished.snapshot.distanceMeters.milesText,
                                label: "distance"
                            )
                            RecorderMetric(
                                value: finished.snapshot.activeElapsedMilliseconds.elapsedText,
                                label: "active time"
                            )
                            RecorderMetric(
                                value: "\(finished.snapshot.pointCount)",
                                label: "points"
                            )
                        }
                        .padding(.vertical, 24)
                    } else {
                        Text("HikeJournal keeps the route on this iPhone, so a missing signal never has to mean a missing walk.")
                            .font(HikeJournalTheme.body(18))
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                            .fixedSize(horizontal: false, vertical: true)

                        VStack(spacing: 0) {
                            CapabilityRow(symbol: "point.topleft.down.to.point.bottomright.curvepath", title: "Route and distance", detail: "A continuous path with active time")
                            Divider().overlay(HikeJournalTheme.line)
                            CapabilityRow(symbol: "wifi.slash", title: "Made for no signal", detail: "Every accepted point is saved immediately")
                            Divider().overlay(HikeJournalTheme.line)
                            CapabilityRow(symbol: "camera.macro", title: "Field moments", detail: "Marks stay with the outing")
                        }
                        .padding(.top, 22)
                    }

                    locationAction
                        .padding(.top, 26)
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 28)
            }
        }
        .scrollIndicators(.hidden)
    }

    private var activeRecorder: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                recordingMap

                VStack(alignment: .leading, spacing: 0) {
                    HStack(alignment: .top, spacing: 26) {
                        RecorderMetric(
                            value: (recording.snapshot?.distanceMeters ?? 0).milesText,
                            label: "miles"
                        )
                        RecorderMetric(
                            value: (recording.snapshot?.activeElapsedMilliseconds ?? 0).elapsedText,
                            label: "active"
                        )
                        RecorderMetric(
                            value: recording.snapshot?.lastAccuracyMeters.map { "±\(Int($0.rounded()))m" } ?? "—",
                            label: "GPS"
                        )
                    }
                    .accessibilityElement(children: .combine)

                    Divider().overlay(HikeJournalTheme.line).padding(.vertical, 22)

                    if recording.phase == .paused {
                        Button {
                            Task { await recording.resume() }
                        } label: {
                            Label("Resume route", systemImage: "play.fill")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(TrailButtonStyle())
                    } else {
                        Button {
                            Task { await recording.pause() }
                        } label: {
                            Label("Pause route", systemImage: "pause.fill")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(TrailButtonStyle())
                    }

                    HStack(spacing: 12) {
                        Button {
                            showingFieldMark = true
                        } label: {
                            Label("Field mark", systemImage: "mappin.and.ellipse")
                                .frame(maxWidth: .infinity, minHeight: 48)
                        }
                        .buttonStyle(.bordered)
                        .tint(HikeJournalTheme.moss)

                        Button {
                            if recording.phase == .recording {
                                Task {
                                    await recording.pause()
                                    showingFinish = true
                                }
                            } else {
                                showingFinish = true
                            }
                        } label: {
                            Label("Finish", systemImage: "flag.checkered")
                                .frame(maxWidth: .infinity, minHeight: 48)
                        }
                        .buttonStyle(.bordered)
                        .tint(HikeJournalTheme.trailText)
                    }
                    .padding(.top, 12)

                    Button("Discard recording", role: .destructive) {
                        showingDiscard = true
                    }
                    .font(HikeJournalTheme.label(15, relativeTo: .headline))
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .padding(.top, 8)
                }
                .padding(24)
            }
        }
        .scrollIndicators(.hidden)
    }

    @ViewBuilder
    private var recordingMap: some View {
        ZStack(alignment: .topLeading) {
            if let style = model.maps.style,
               let surface = try? HikeJournalMapSurface(
                   scene: recordingScene,
                   style: style,
                   styleCredential: model.maps.styleCredential,
                   cameraBehavior: .fitOnEveryUpdate,
                   cameraPadding: EdgeInsets(top: 62, leading: 28, bottom: 52, trailing: 28)
               ) {
                surface
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                RouteTraceView(segments: recording.snapshot?.routeSegments ?? [])
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color(red: 0.06, green: 0.15, blue: 0.11))
            }

            LinearGradient(
                colors: [.black.opacity(0.62), .black.opacity(0.08), .clear],
                startPoint: .top,
                endPoint: .bottom
            )
            .frame(height: 128)
            .allowsHitTesting(false)

            VStack(alignment: .leading, spacing: 3) {
                Text(recording.phase == .paused ? "PAUSED" : "RECORDING")
                    .font(HikeJournalTheme.label(12))
                    .tracking(1.5)
                Text(recording.phase == .paused ? "The route is safe." : "Following your line.")
                    .font(HikeJournalTheme.display(32, relativeTo: .title))
            }
            .foregroundStyle(Color(red: 1, green: 0.97, blue: 0.89))
            .padding(22)
        }
        .frame(height: 330)
        .clipped()
    }

    private var recordingScene: MapScene {
        JournalMapSceneFactory.make(
            // Keep the tracking camera focused on the active outing rather
            // than fitting every saved journal point into the initial view.
            routes: [],
            hikes: [],
            details: [:],
            sightings: [],
            tracking: recording.snapshot,
            selectedTrailOverlayIDs: model.maps.selectedTrailOverlayIDs
        )
    }

    @ViewBuilder
    private var locationAction: some View {
        if case .signedOut = model.authentication.phase {
            Button {
                model.openSettings()
            } label: {
                HStack {
                    Image(systemName: "person.crop.circle.badge.plus")
                    Text("Sign in before recording")
                    Spacer()
                    Image(systemName: "arrow.right")
                }
            }
            .buttonStyle(TrailButtonStyle())
        } else {
            locationPermissionAction
        }
    }

    @ViewBuilder
    private var locationPermissionAction: some View {
        switch recording.locationAuthorization {
        case .notDetermined:
            Button {
                showingLocationPrimer = true
            } label: {
                HStack {
                    Image(systemName: "location.circle.fill")
                        .scaleEffect(compassPulse ? 1.08 : 0.94)
                    Text("Set up location access")
                    Spacer()
                    Image(systemName: "arrow.right")
                }
            }
            .buttonStyle(TrailButtonStyle())
        case .denied, .restricted:
            VStack(alignment: .leading, spacing: 12) {
                StatusLine(symbol: "location.slash.fill", title: "Location access is off", color: HikeJournalTheme.error)
                Button("Open iPhone Settings") {
                    if let settingsURL = URL(string: UIApplication.openSettingsURLString) {
                        openURL(settingsURL)
                    }
                }
                .font(HikeJournalTheme.label(16, relativeTo: .headline))
                .foregroundStyle(HikeJournalTheme.trailText)
                .frame(minHeight: 44)
            }
        case .authorizedWhenInUse:
            VStack(alignment: .leading, spacing: 12) {
                StatusLine(symbol: "lock.iphone", title: "Keep recording with the screen locked", color: HikeJournalTheme.moss)
                Text("An outing can last beyond the time HikeJournal is on screen. Allow Always access now; location runs only while you actively record.")
                    .font(HikeJournalTheme.body(15))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                Button("Allow background recording") {
                    recording.requestBackgroundLocation()
                }
                .buttonStyle(TrailButtonStyle())
            }
        case .authorizedAlways:
            VStack(alignment: .leading, spacing: 12) {
                StatusLine(symbol: "checkmark.circle.fill", title: "Background route recording is ready", color: HikeJournalTheme.moss)
                Button {
                    Task { await recording.start() }
                } label: {
                    HStack {
                        Image(systemName: "location.north.fill")
                            .scaleEffect(compassPulse ? 1.08 : 0.94)
                        Text(recording.phase == .finished ? "Record another outing" : "Start recording")
                        Spacer()
                        Image(systemName: "arrow.right")
                    }
                }
                .buttonStyle(TrailButtonStyle())
            }
        @unknown default:
            StatusLine(symbol: "questionmark.circle", title: "Location status unavailable", color: HikeJournalTheme.inkMuted)
        }
    }
}

private struct RecorderMetric: View {
    let value: String
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value)
                .font(HikeJournalTheme.display(28, relativeTo: .title2))
                .foregroundStyle(HikeJournalTheme.ink)
                .monospacedDigit()
            Text(label.uppercased())
                .font(HikeJournalTheme.label(10))
                .tracking(1.2)
                .foregroundStyle(HikeJournalTheme.inkMuted)
        }
    }
}

private struct RouteTraceView: View {
    let segments: [[HikeJournalTracking.TrackingPoint]]

    var body: some View {
        Canvas { context, size in
            let points = segments.flatMap { $0 }
            guard let minimumLatitude = points.map(\.latitude).min(),
                  let maximumLatitude = points.map(\.latitude).max(),
                  let minimumLongitude = points.map(\.longitude).min(),
                  let maximumLongitude = points.map(\.longitude).max() else {
                return
            }
            let latitudeRange = max(0.0001, maximumLatitude - minimumLatitude)
            let longitudeRange = max(0.0001, maximumLongitude - minimumLongitude)
            for segment in segments where !segment.isEmpty {
                var path = Path()
                for (index, point) in segment.enumerated() {
                    let x = 24 + ((point.longitude - minimumLongitude) / longitudeRange) * (size.width - 48)
                    let y = 74 + (1 - (point.latitude - minimumLatitude) / latitudeRange) * (size.height - 98)
                    if index == 0 { path.move(to: CGPoint(x: x, y: y)) }
                    else { path.addLine(to: CGPoint(x: x, y: y)) }
                }
                context.stroke(
                    path,
                    with: .color(Color(red: 0.96, green: 0.55, blue: 0.26)),
                    style: StrokeStyle(lineWidth: 4, lineCap: .round, lineJoin: .round)
                )
            }
        }
        .background {
            BrandLandscape().opacity(0.18)
        }
        .accessibilityElement()
        .accessibilityLabel("Recorded route")
        .accessibilityValue("\(segments.flatMap { $0 }.count) saved GPS points")
    }
}

private struct FieldMarkComposer: View {
    @Environment(\.dismiss) private var dismiss
    @State private var type = HikeJournalTracking.FieldMarkType.wildlife
    @State private var note = ""
    let save: (HikeJournalTracking.FieldMarkType, String) async -> Void

    var body: some View {
        NavigationStack {
            Form {
                Picker("Kind", selection: $type) {
                    ForEach(HikeJournalTracking.FieldMarkType.allCases, id: \.self) { type in
                        Text(type.title).tag(type)
                    }
                }
                TextField("What did you notice?", text: $note, axis: .vertical)
                    .lineLimit(3...6)
            }
            .navigationTitle("Field mark")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await save(type, note) } }
                }
            }
        }
    }
}

private struct FinishRecordingSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var notes = ""
    let finish: (String, String) async -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section("Journal") {
                    TextField("Outing title", text: $title)
                    TextField("Trail notes", text: $notes, axis: .vertical)
                        .lineLimit(4...8)
                }
                Section {
                    Text("The TCX route is written locally first, then the journal and route are queued in order for sync.")
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }
            }
            .navigationTitle("Finish outing")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Keep outing") { Task { await finish(title, notes) } }
                }
            }
        }
    }
}

private extension HikeJournalTracking.FieldMarkType {
    var title: String {
        switch self {
        case .wildlife: "Wildlife"
        case .plant: "Plant"
        case .trailCondition: "Trail condition"
        case .bridge: "Bridge"
        case .boardwalk: "Boardwalk"
        case .water: "Water"
        case .campsite: "Campsite"
        case .hazard: "Hazard"
        case .note: "Note"
        }
    }
}

private extension Double {
    var milesText: String {
        String(format: "%.2f", self / HikeJournalTracking.WholeMileAnnouncementScheduler.metersPerMile)
    }
}

private extension Int64 {
    var elapsedText: String {
        HikeJournalTracking.MileAnnouncement.formatElapsed(self)
    }
}

private struct FieldGuideHomeView: View {
    @State private var search = ""

    var body: some View {
        NavigationStack {
            ZStack {
                ParchmentBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        Image(systemName: "leaf.circle.fill")
                            .font(.system(size: 62, weight: .light))
                            .foregroundStyle(HikeJournalTheme.fern)
                            .accessibilityHidden(true)
                        Text("Notice more over time.")
                            .font(HikeJournalTheme.display(38, relativeTo: .largeTitle))
                            .foregroundStyle(HikeJournalTheme.ink)
                            .padding(.top, 18)
                        Text("Confirmed plants, animals, fungi, and other finds will form a field guide rooted in your own outings.")
                            .font(HikeJournalTheme.body(18))
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.top, 8)

                        Divider().overlay(HikeJournalTheme.line).padding(.vertical, 28)

                        Text(search.isEmpty ? "No observations yet" : "No observations match “\(search)”")
                            .font(HikeJournalTheme.label(16, relativeTo: .headline))
                            .foregroundStyle(HikeJournalTheme.ink)
                        Text("Your guide begins with the first species you confirm.")
                            .font(HikeJournalTheme.body())
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                            .padding(.top, 4)
                    }
                    .padding(24)
                }
            }
            .navigationTitle("Field Guide")
            .searchable(text: $search, prompt: "Search your field guide")
        }
    }
}

private struct MapHomeView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        NavigationStack {
            ZStack {
                Color(red: 0.07, green: 0.16, blue: 0.12).ignoresSafeArea()
                VStack(spacing: 0) {
                    BrandLandscape()
                        .overlay {
                            Image(systemName: "mappin.and.ellipse")
                                .font(.system(size: 44, weight: .medium))
                                .foregroundStyle(Color(red: 1, green: 0.94, blue: 0.81))
                                .accessibilityHidden(true)
                        }

                    VStack(alignment: .leading, spacing: 10) {
                        Text("Your routes meet here.")
                            .font(HikeJournalTheme.display(35, relativeTo: .title))
                            .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.91))
                        Text("Recorded trails, GPS-tagged photos, and field marks will remain legible together—with a text alternative for every mapped item.")
                            .font(HikeJournalTheme.body())
                            .foregroundStyle(Color(red: 0.77, green: 0.83, blue: 0.78))
                            .fixedSize(horizontal: false, vertical: true)
                        Button("Prepare an outing") {
                            model.openRecording()
                        }
                        .font(HikeJournalTheme.label(16, relativeTo: .headline))
                        .foregroundStyle(HikeJournalTheme.trail)
                        .frame(minHeight: 44)
                    }
                    .padding(24)
                }
            }
            .navigationTitle("Map")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
    }
}

private struct SettingsHomeView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var authentication: AuthenticationStore
    @ObservedObject private var sync: SyncStore
    @ObservedObject private var recording: RecordingStore
    @ObservedObject private var maps: MapStore
    @ObservedObject private var journal: JournalStore
    @ObservedObject private var riverGauges: RiverGaugePreferencesStore
    @StateObject private var oauth = INaturalistWebSession()
    @Environment(\.openURL) private var openURL

    init(model: AppModel) {
        self.model = model
        _authentication = ObservedObject(wrappedValue: model.authentication)
        _sync = ObservedObject(wrappedValue: model.sync)
        _recording = ObservedObject(wrappedValue: model.recording)
        _maps = ObservedObject(wrappedValue: model.maps)
        _journal = ObservedObject(wrappedValue: model.journal)
        _riverGauges = ObservedObject(wrappedValue: model.riverGauges)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("HikeJournal") {
                    NavigationLink {
                        AccountView(
                            authentication: authentication,
                            storefront: model.storefront,
                            webBaseURL: model.configuration.webBaseURL
                        )
                    } label: {
                        LabeledContent("Account", value: accountSummary)
                    }
                    LabeledContent("App version", value: model.version.displayName)
                    Button("View getting started") {
                        model.replayOnboarding()
                    }
                }

                Section("Recording") {
                    Toggle(isOn: $recording.voiceAnnouncementsEnabled) {
                        Label("Mile announcements", systemImage: "speaker.wave.2.fill")
                    }
                    LabeledContent("Background location", value: model.locationAuthorization.readableName)
                    if model.locationAuthorization == .denied || model.locationAuthorization == .restricted {
                        Button("Open iPhone Settings") {
                            if let settings = URL(string: UIApplication.openSettingsURLString) {
                                openURL(settings)
                            }
                        }
                    }
                }

                Section {
                    NavigationLink {
                        MapStorageSettingsView(model: model)
                    } label: {
                        LabeledContent("Offline maps") {
                            Text(mapStorageSummary)
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                    }
                    LabeledContent("National Scenic Trails") {
                        Text(maps.selectedTrailOverlayIDs.isEmpty
                             ? "None shown"
                             : "\(maps.selectedTrailOverlayIDs.count) shown")
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                    }
                    Button("Choose trail overlays") {
                        model.selectedTab = .map
                    }
                } header: {
                    Text("Maps")
                } footer: {
                    Text("Offline base maps are downloaded from the Map tab around a recorded route. Journal routes and notes remain cached separately.")
                }

                Section {
                    NavigationLink {
                        RiverGaugeSettingsView(store: riverGauges)
                    } label: {
                        LabeledContent("Followed gauges") {
                            Text(riverGauges.followedGauges.isEmpty
                                 ? "None"
                                 : String(riverGauges.followedGauges.count))
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                    }
                } header: {
                    Text("River conditions")
                } footer: {
                    Text("Place Profiles automatically show the closest active USGS gauges. Follow one there to keep it associated with nearby places.")
                }

                Section {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(sync.summary)
                            .foregroundStyle(HikeJournalTheme.ink)
                        Text(sync.statusMessage)
                            .font(HikeJournalTheme.body(14))
                            .foregroundStyle(HikeJournalTheme.inkMuted)
                    }
                    if sync.progress.totalPhotoUploads > 0, sync.isDraining {
                        ProgressView(
                            value: Double(sync.progress.completedPhotoUploads),
                            total: Double(max(1, sync.progress.totalPhotoUploads))
                        )
                        .tint(HikeJournalTheme.trailText)
                    }
                    if let error = sync.errorMessage {
                        Text(error)
                            .foregroundStyle(HikeJournalTheme.error)
                    }
                    Button {
                        Task { await sync.retryNeedsAttention() }
                    } label: {
                        Label("Retry sync", systemImage: "arrow.clockwise")
                    }
                    .disabled(!sync.canRetry)
                } header: {
                    Text("Offline sync")
                } footer: {
                    Text("Queued changes stay in this signed-in account. Server authentication and cloud limits still apply to every retry.")
                }

                if isSignedIn {
                    Section {
                        LabeledContent("Connection") {
                            Text(journal.publishQueue?.connected == true ? "Connected" : "Not connected")
                                .foregroundStyle(journal.publishQueue?.connected == true
                                    ? HikeJournalTheme.moss
                                    : HikeJournalTheme.inkMuted)
                        }
                        if journal.publishQueue?.connected != true {
                            Button(oauth.isAuthenticating ? "Connecting…" : "Connect iNaturalist") {
                                connectINaturalist()
                            }
                            .disabled(oauth.isAuthenticating)
                        }
                        Button("Open publishing workspace") {
                            model.selectedTab = .fieldGuide
                        }
                    } header: {
                        Text("iNaturalist")
                    } footer: {
                        Text("Publishing is always explicit. You choose location privacy before each observation is shared.")
                    }
                }

                Section("Privacy & help") {
                    if let privacy = model.configuration.webBaseURL?.appendingPathComponent("privacy") {
                        Link(destination: privacy) {
                            Label("Privacy policy", systemImage: "hand.raised")
                        }
                    }
                    if let support = model.configuration.webBaseURL?.appendingPathComponent("support") {
                        Link(destination: support) {
                            Label("HikeJournal support", systemImage: "questionmark.circle")
                        }
                    }
                    Text("Original photo and video files are copied into HikeJournal's protected storage before upload. Photo locations are never invented.")
                        .font(HikeJournalTheme.body(14))
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                }
            }
            .font(HikeJournalTheme.body())
            .scrollContentBackground(.hidden)
            .background(ParchmentBackground())
            .navigationTitle("Settings")
            .task(id: accountIdentity) {
                await maps.start()
                guard isSignedIn else { return }
                await journal.loadReviewAndPublishing()
            }
            .onChange(of: model.pendingDeepLink) { _, value in
                guard case .inaturalist = value else { return }
                Task {
                    await journal.loadReviewAndPublishing()
                    model.consumeDeepLink()
                }
            }
            .alert(
                "Connection needs attention",
                isPresented: Binding(
                    get: { oauth.errorMessage != nil },
                    set: { if !$0 { oauth.clearError() } }
                )
            ) {
                Button("OK") { oauth.clearError() }
            } message: {
                Text(oauth.errorMessage ?? "")
            }
        }
    }

    private var accountSummary: String {
        switch authentication.phase {
        case .restoring:
            return "Checking…"
        case .signedOut:
            return "Sign in"
        case .signedIn:
            return authentication.entitlement?.plan.displayName ?? "Signed in"
        }
    }

    private var isSignedIn: Bool {
        if case .signedIn = authentication.phase { return true }
        return false
    }

    private var accountIdentity: String {
        if case let .signedIn(account) = authentication.phase {
            return account.userID ?? account.subject
        }
        return "signed-out"
    }

    private var mapStorageSummary: String {
        guard !maps.offlinePacks.isEmpty else { return "None downloaded" }
        let size = ByteCountFormatter.string(
            fromByteCount: Int64(clamping: maps.totalStorageBytes),
            countStyle: .file
        )
        return "\(maps.offlinePacks.count) · \(size)"
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

private struct RiverGaugeSettingsView: View {
    @ObservedObject var store: RiverGaugePreferencesStore

    var body: some View {
        List {
            Section {
                Text("HikeJournal automatically finds the closest active USGS water gauges for each Place Profile. Follow a station when you want it kept in the nearby mix.")
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }

            Section("Followed USGS stations") {
                if store.followedGauges.isEmpty {
                    ContentUnavailableView(
                        "No followed gauges",
                        systemImage: "drop",
                        description: Text("Open a Place Profile and choose Follow gauge beside a station.")
                    )
                } else {
                    ForEach(store.followedGauges, id: \.siteId) { gauge in
                        VStack(alignment: .leading, spacing: 3) {
                            Text(gauge.name)
                                .font(HikeJournalTheme.label(16, relativeTo: .headline))
                            Text(gauge.siteId)
                                .font(HikeJournalTheme.body(13))
                                .foregroundStyle(HikeJournalTheme.inkMuted)
                        }
                        .swipeActions {
                            Button("Unfollow", role: .destructive) {
                                store.remove(siteID: gauge.siteId)
                            }
                        }
                        .accessibilityAction(named: "Unfollow") {
                            store.remove(siteID: gauge.siteId)
                        }
                    }
                }
            }

            Section {
                Link(
                    "About USGS water data",
                    destination: URL(string: "https://waterdata.usgs.gov/")!
                )
            } footer: {
                Text("Gauge readings may be provisional. Water height is station-specific and is not a trail-crossing safety rating.")
            }
        }
        .font(HikeJournalTheme.body())
        .scrollContentBackground(.hidden)
        .background(ParchmentBackground())
        .navigationTitle("River gauges")
    }
}

private struct MapStorageSettingsView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var maps: MapStore
    @State private var pendingDeletion: HikeJournalMaps.OfflinePackSnapshot?

    init(model: AppModel) {
        self.model = model
        _maps = ObservedObject(wrappedValue: model.maps)
    }

    var body: some View {
        List {
            Section {
                LabeledContent("Downloaded regions", value: String(maps.offlinePacks.count))
                LabeledContent(
                    "Map storage",
                    value: ByteCountFormatter.string(
                        fromByteCount: Int64(clamping: maps.totalStorageBytes),
                        countStyle: .file
                    )
                )
                LabeledContent(
                    "Download network",
                    value: maps.activeNetworkPolicy == .wifiOnly ? "Wi-Fi only" : "Wi-Fi or cellular"
                )
            }

            Section("Saved on this iPhone") {
                if maps.offlinePacks.isEmpty {
                    Text("No offline base-map regions yet.")
                        .foregroundStyle(HikeJournalTheme.inkMuted)
                } else {
                    ForEach(maps.offlinePacks) { pack in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(pack.context.name)
                                        .font(HikeJournalTheme.label(16, relativeTo: .headline))
                                    Text(pack.isComplete ? "Ready offline" : "\(Int((pack.progress.fractionCompleted ?? 0) * 100))% downloaded")
                                        .font(HikeJournalTheme.body(13))
                                        .foregroundStyle(HikeJournalTheme.inkMuted)
                                }
                                Spacer()
                                Button(role: .destructive) {
                                    pendingDeletion = pack
                                } label: {
                                    Image(systemName: "trash")
                                }
                                .accessibilityLabel("Remove \(pack.context.name)")
                            }
                            if !pack.isComplete {
                                ProgressView(value: pack.progress.fractionCompleted ?? 0)
                                    .tint(HikeJournalTheme.trailText)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
            }

            Section {
                Button {
                    model.selectedTab = .map
                } label: {
                    Label("Download around a recorded route", systemImage: "map")
                }
            } footer: {
                Text("Choose Offline on the Map tab. HikeJournal estimates the region before downloading it.")
            }
        }
        .font(HikeJournalTheme.body())
        .scrollContentBackground(.hidden)
        .background(ParchmentBackground())
        .navigationTitle("Map storage")
        .task { await maps.refreshOfflinePacks() }
        .confirmationDialog(
            "Remove this offline map?",
            isPresented: Binding(
                get: { pendingDeletion != nil },
                set: { if !$0 { pendingDeletion = nil } }
            ),
            titleVisibility: .visible,
            presenting: pendingDeletion
        ) { pack in
            Button("Remove \(pack.context.name)", role: .destructive) {
                Task { await maps.delete(packID: pack.id) }
            }
            Button("Keep map", role: .cancel) {}
        } message: { _ in
            Text("The base-map download will be removed. Your journals, routes, and field notes stay on this iPhone.")
        }
    }
}

private struct LocationPrimerView: View {
    @Environment(\.dismiss) private var dismiss
    let continueAction: () -> Void

    var body: some View {
        ZStack {
            ParchmentBackground()
            VStack(alignment: .leading, spacing: 0) {
                Image(systemName: "location.north.circle.fill")
                    .font(.system(size: 56, weight: .light))
                    .foregroundStyle(HikeJournalTheme.moss)
                    .accessibilityHidden(true)
                Text("Your route stays yours.")
                    .font(HikeJournalTheme.display(39, relativeTo: .largeTitle))
                    .foregroundStyle(HikeJournalTheme.ink)
                    .padding(.top, 18)
                Text("Allow location while using HikeJournal so it can place you on the trail. This step does not start recording, and background access is explained later in context.")
                    .font(HikeJournalTheme.body(18))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 10)
                Spacer(minLength: 20)
                Button("Continue") {
                    continueAction()
                }
                .buttonStyle(TrailButtonStyle())
                Button("Not now") {
                    dismiss()
                }
                .font(HikeJournalTheme.label(16, relativeTo: .headline))
                .foregroundStyle(HikeJournalTheme.moss)
                .frame(maxWidth: .infinity, minHeight: 48)
            }
            .padding(24)
        }
    }
}

private struct CapabilityRow: View {
    let symbol: String
    let title: String
    let detail: String

    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: symbol)
                .font(.system(size: 20, weight: .semibold))
                .foregroundStyle(HikeJournalTheme.trailText)
                .frame(width: 32)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(HikeJournalTheme.label(16, relativeTo: .headline))
                    .foregroundStyle(HikeJournalTheme.ink)
                Text(detail)
                    .font(HikeJournalTheme.body(15))
                    .foregroundStyle(HikeJournalTheme.inkMuted)
            }
            Spacer()
        }
        .padding(.vertical, 16)
    }
}

private struct StatusLine: View {
    let symbol: String
    let title: String
    let color: Color

    var body: some View {
        Label(title, systemImage: symbol)
            .font(HikeJournalTheme.label(16, relativeTo: .headline))
            .foregroundStyle(color)
            .fixedSize(horizontal: false, vertical: true)
    }
}

struct TrailNotebookIllustration: View {
    var body: some View {
        GeometryReader { proxy in
            let size = proxy.size
            ZStack {
                RoundedRectangle(cornerRadius: 4)
                    .fill(HikeJournalTheme.paper)
                    .shadow(color: HikeJournalTheme.ink.opacity(0.10), radius: 16, y: 8)
                ForEach(1..<5, id: \.self) { line in
                    Rectangle()
                        .fill(HikeJournalTheme.line.opacity(0.7))
                        .frame(height: 1)
                        .position(x: size.width / 2, y: CGFloat(line) * size.height / 6)
                }
                Path { path in
                    path.move(to: CGPoint(x: size.width * 0.08, y: size.height * 0.78))
                    path.addCurve(
                        to: CGPoint(x: size.width * 0.92, y: size.height * 0.30),
                        control1: CGPoint(x: size.width * 0.35, y: size.height * 0.30),
                        control2: CGPoint(x: size.width * 0.65, y: size.height * 0.92)
                    )
                }
                .stroke(HikeJournalTheme.trail, style: StrokeStyle(lineWidth: 7, lineCap: .round))
                Image(systemName: "leaf.fill")
                    .foregroundStyle(HikeJournalTheme.fern)
                    .position(x: size.width * 0.77, y: size.height * 0.25)
            }
            .rotationEffect(.degrees(-1.4))
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("An empty field journal page with a trail line")
    }
}

private extension CLAuthorizationStatus {
    var readableName: String {
        switch self {
        case .notDetermined: "Not requested"
        case .restricted: "Restricted"
        case .denied: "Off"
        case .authorizedAlways: "Always"
        case .authorizedWhenInUse: "While using"
        @unknown default: "Unknown"
        }
    }
}
