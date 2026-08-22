import HikeJournalDomain
import MapKit
import SwiftUI
import UIKit

struct HikeShareSheet: View {
    private static let maximumPhotos = 19

    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    let hike: Hike

    @State private var selectedPhotoIDs: [String] = []
    @State private var satelliteMap: UIImage?
    @State private var preparing = false
    @State private var errorMessage: String?
    @State private var activityItems: [Any]?

    var body: some View {
        NavigationStack {
            ZStack {
                LinearGradient(
                    colors: [Color(red: 0.19, green: 0.35, blue: 0.27), Color(red: 0.06, green: 0.16, blue: 0.12)],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        HikeShareCard(hike: hike, satelliteMap: satelliteMap)
                            .aspectRatio(4 / 5, contentMode: .fit)
                            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                            .shadow(color: .black.opacity(0.25), radius: 18, y: 10)
                            .accessibilityLabel("HikeJournal trail keepsake for \(hike.title)")

                        if !availablePhotos.isEmpty {
                            photoPicker
                        }

                        if let errorMessage {
                            Text(errorMessage)
                                .font(HikeJournalTheme.body(15))
                                .foregroundStyle(Color(red: 1, green: 0.79, blue: 0.75))
                                .accessibilityLabel("Sharing error: \(errorMessage)")
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 8)
                    .padding(.bottom, 110)
                }
            }
            .safeAreaInset(edge: .bottom) {
                Button(action: prepareShare) {
                    HStack(spacing: 9) {
                        if preparing { ProgressView().tint(.white) }
                        else { Image(systemName: "square.and.arrow.up") }
                        Text(preparing ? "Preparing images…" : shareButtonTitle)
                    }
                }
                .buttonStyle(TrailButtonStyle())
                .disabled(preparing)
                .padding(.horizontal, 20)
                .padding(.vertical, 12)
                .background(.ultraThinMaterial)
            }
            .navigationTitle("Share your outing")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Close") { dismiss() }
                        .disabled(preparing)
                }
            }
            .task(id: hike.id) {
                guard !hike.routeSegments.isEmpty else { return }
                satelliteMap = await HikeShareMapSnapshotter.snapshot(routeSegments: hike.routeSegments)
            }
            .sheet(
                isPresented: Binding(
                    get: { activityItems != nil },
                    set: { if !$0 { activityItems = nil } }
                )
            ) {
                ActivityShareView(items: activityItems ?? [])
                    .ignoresSafeArea()
            }
        }
    }

    private var photoPicker: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .bottom) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("ADD HIKE PHOTOS")
                        .font(HikeJournalTheme.label(11))
                        .tracking(1.2)
                        .foregroundStyle(Color(red: 0.95, green: 0.73, blue: 0.45))
                    Text("Choose up to \(Self.maximumPhotos)")
                        .font(HikeJournalTheme.display(27, relativeTo: .title2))
                        .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.93))
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 1) {
                    Text("\(selectedPhotoIDs.count)/\(Self.maximumPhotos)")
                        .font(HikeJournalTheme.label(13))
                        .foregroundStyle(Color(red: 0.76, green: 0.83, blue: 0.78))
                    Button(allSelected ? "Clear" : "Select all") {
                        withAnimation(reduceMotion ? nil : .snappy(duration: 0.25)) {
                            selectedPhotoIDs = allSelected
                                ? []
                                : availablePhotos.prefix(Self.maximumPhotos).map(\.id)
                        }
                    }
                    .font(HikeJournalTheme.label(14, relativeTo: .headline))
                    .foregroundStyle(Color(red: 0.95, green: 0.73, blue: 0.45))
                }
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                ForEach(availablePhotos) { photo in
                    let selectedIndex = selectedPhotoIDs.firstIndex(of: photo.id)
                    Button {
                        toggle(photo)
                    } label: {
                        ZStack(alignment: .topTrailing) {
                            JournalRemoteImage(urlString: photo.url, fallback: "photo")
                                .frame(height: 142)
                                .clipped()
                                .overlay {
                                    Rectangle().stroke(
                                        selectedIndex == nil ? Color.white.opacity(0.16) : Color(red: 0.95, green: 0.60, blue: 0.34),
                                        lineWidth: selectedIndex == nil ? 1 : 4
                                    )
                                }
                            if let selectedIndex {
                                Text(String(selectedIndex + 1))
                                    .font(HikeJournalTheme.label(13))
                                    .foregroundStyle(.white)
                                    .frame(width: 28, height: 28)
                                    .background(Color(red: 0.82, green: 0.42, blue: 0.20), in: Circle())
                                    .padding(8)
                            }
                        }
                    }
                    .buttonStyle(.plain)
                    .disabled(selectedIndex == nil && selectedPhotoIDs.count >= Self.maximumPhotos)
                    .accessibilityLabel(photo.caption.isEmpty ? "Hike photo" : photo.caption)
                    .accessibilityValue(selectedIndex.map { "Selected \($0 + 1)" } ?? "Not selected")
                }
            }

            Text("The trail keepsake shares first, followed by selected photos. Videos are excluded from the image carousel.")
                .font(HikeJournalTheme.body(13))
                .foregroundStyle(Color(red: 0.72, green: 0.79, blue: 0.74))
        }
    }

    private var availablePhotos: [Photo] {
        hike.photos.filter {
            !$0.contentType.lowercased().hasPrefix("video/") && !$0.url.isEmpty
        }
    }

    private var selectedPhotos: [Photo] {
        let photosByID = Dictionary(uniqueKeysWithValues: availablePhotos.map { ($0.id, $0) })
        return selectedPhotoIDs.compactMap { photosByID[$0] }.prefix(Self.maximumPhotos).map { $0 }
    }

    private var allSelected: Bool {
        !availablePhotos.isEmpty
            && selectedPhotoIDs.count == min(availablePhotos.count, Self.maximumPhotos)
    }

    private var shareButtonTitle: String {
        let count = selectedPhotoIDs.count + 1
        return "Share \(count) image\(count == 1 ? "" : "s")"
    }

    private func toggle(_ photo: Photo) {
        withAnimation(reduceMotion ? nil : .snappy(duration: 0.22)) {
            if let index = selectedPhotoIDs.firstIndex(of: photo.id) {
                selectedPhotoIDs.remove(at: index)
            } else if selectedPhotoIDs.count < Self.maximumPhotos {
                selectedPhotoIDs.append(photo.id)
            }
        }
    }

    private func prepareShare() {
        guard !preparing else { return }
        preparing = true
        errorMessage = nil
        Task { @MainActor in
            defer { preparing = false }
            let card = HikeShareCard(hike: hike, satelliteMap: satelliteMap)
                .frame(width: 1_080, height: 1_350)
                .environment(\.colorScheme, .dark)
            let renderer = ImageRenderer(content: card)
            renderer.scale = 1
            guard let image = renderer.uiImage,
                  let jpeg = image.jpegData(compressionQuality: 0.94) else {
                errorMessage = "HikeJournal could not render this trail keepsake."
                return
            }
            do {
                let prepared = try await HikeSharePreparer.prepare(
                    cardData: jpeg,
                    hike: hike,
                    photos: selectedPhotos
                )
                activityItems = prepared.items
                if prepared.omittedPhotoCount > 0 {
                    errorMessage = "\(prepared.omittedPhotoCount) selected photo\(prepared.omittedPhotoCount == 1 ? " was" : "s were") unavailable; the remaining images are ready."
                }
            } catch is CancellationError {
                return
            } catch {
                errorMessage = (error as? LocalizedError)?.errorDescription
                    ?? "HikeJournal could not prepare these images."
            }
        }
    }
}

struct HikeShareCard: View {
    let hike: Hike
    let satelliteMap: UIImage?

    var body: some View {
        GeometryReader { geometry in
            let scale = geometry.size.width / 1_080
            ZStack {
                LinearGradient(
                    colors: [Color(red: 0.19, green: 0.35, blue: 0.27), Color(red: 0.06, green: 0.16, blue: 0.12)],
                    startPoint: .top,
                    endPoint: .bottom
                )
                ShareContourTexture().opacity(0.45)

                VStack(alignment: .leading, spacing: 0) {
                    Text("HIKEJOURNAL")
                        .font(HikeJournalTheme.label(24 * scale))
                        .tracking(2.8 * scale)
                        .foregroundStyle(Color(red: 0.95, green: 0.73, blue: 0.45))
                    Text("Trail keepsake")
                        .font(HikeJournalTheme.display(55 * scale))
                        .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.93))
                        .padding(.top, 2 * scale)

                    ZStack(alignment: .bottomLeading) {
                        if let satelliteMap {
                            Image(uiImage: satelliteMap)
                                .resizable()
                                .scaledToFill()
                        } else {
                            RouteSketch(routeSegments: hike.routeSegments)
                        }
                        LinearGradient(
                            colors: [.clear, Color(red: 0.06, green: 0.16, blue: 0.12).opacity(0.72)],
                            startPoint: .center,
                            endPoint: .bottom
                        )
                        Text(satelliteMap == nil
                             ? "RECORDED ROUTE"
                             : "SATELLITE IMAGERY © APPLE MAPS")
                            .font(HikeJournalTheme.label(17 * scale))
                            .tracking(0.8 * scale)
                            .foregroundStyle(.white.opacity(0.9))
                            .padding(18 * scale)
                    }
                    .frame(height: 555 * scale)
                    .clipped()
                    .padding(.top, 28 * scale)

                    Rectangle()
                        .fill(.white.opacity(0.2))
                        .frame(height: max(1, 2 * scale))
                        .padding(.top, 48 * scale)

                    Text(locationLabel)
                        .font(HikeJournalTheme.label(23 * scale))
                        .tracking(2 * scale)
                        .foregroundStyle(Color(red: 0.95, green: 0.73, blue: 0.45))
                        .lineLimit(1)
                        .padding(.top, 52 * scale)
                    Text(hike.title.isEmpty ? "A day on the trail" : hike.title)
                        .font(HikeJournalTheme.display(72 * scale))
                        .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.93))
                        .lineLimit(2)
                        .minimumScaleFactor(0.72)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.top, 7 * scale)
                    Text(JournalDate.display(hike.hikeDate))
                        .font(HikeJournalTheme.body(28 * scale))
                        .foregroundStyle(Color(red: 0.84, green: 0.88, blue: 0.83))
                        .padding(.top, 8 * scale)

                    Spacer(minLength: 10 * scale)

                    Rectangle()
                        .fill(.white.opacity(0.2))
                        .frame(height: max(1, 2 * scale))
                    HStack(alignment: .top, spacing: 0) {
                        shareMetric(distanceLabel, label: "MILES", scale: scale)
                        Spacer()
                        shareMetric(durationLabel, label: "ACTIVE TIME", scale: scale)
                            .frame(width: 418 * scale, alignment: .leading)
                    }
                    .padding(.top, 22 * scale)

                    Label("Field notes from HikeJournal", systemImage: "sparkles")
                        .font(HikeJournalTheme.body(22 * scale))
                        .foregroundStyle(Color(red: 0.84, green: 0.88, blue: 0.83))
                        .padding(.top, 29 * scale)
                }
                .padding(.horizontal, 72 * scale)
                .padding(.top, 49 * scale)
                .padding(.bottom, 48 * scale)
            }
        }
    }

    private var locationLabel: String {
        let value = hike.locationName.isEmpty ? hike.primaryLocationName : hike.locationName
        return value.isEmpty ? "FIELD JOURNAL" : String(value.uppercased().prefix(52))
    }

    private var distanceLabel: String {
        hike.distanceMiles.map { String(format: "%.2f", $0) } ?? "—"
    }

    private var durationLabel: String {
        hike.durationSeconds.map(JournalDate.duration) ?? "—"
    }

    private func shareMetric(_ value: String, label: String, scale: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(value)
                .font(HikeJournalTheme.label(62 * scale, relativeTo: .largeTitle))
                .foregroundStyle(Color(red: 1, green: 0.98, blue: 0.93))
                .lineLimit(1)
                .minimumScaleFactor(0.65)
            Text(label)
                .font(HikeJournalTheme.label(20 * scale))
                .tracking(2.1 * scale)
                .foregroundStyle(Color(red: 0.72, green: 0.79, blue: 0.74))
        }
    }
}

private struct ShareContourTexture: View {
    var body: some View {
        Canvas { context, size in
            for index in 0..<9 {
                let inset = CGFloat(index * 54) - 95
                let rect = CGRect(
                    x: -140 + inset,
                    y: 120 + inset * 0.32,
                    width: size.width * 0.76 + inset,
                    height: size.height * 0.42 + inset * 0.6
                )
                context.stroke(
                    Path(ellipseIn: rect),
                    with: .color(.white.opacity(index.isMultiple(of: 2) ? 0.08 : 0.05)),
                    lineWidth: 2
                )
            }
        }
        .accessibilityHidden(true)
    }
}

private struct RouteSketch: View {
    let routeSegments: [[RoutePoint]]

    var body: some View {
        Canvas { context, size in
            let projected = projectedSegments(in: size)
            if projected.isEmpty {
                context.draw(
                    Text("NO RECORDED ROUTE")
                        .font(HikeJournalTheme.label(22))
                        .foregroundStyle(.white.opacity(0.65)),
                    at: CGPoint(x: size.width / 2, y: size.height / 2)
                )
                return
            }
            for segment in projected {
                var path = Path()
                path.move(to: segment[0])
                segment.dropFirst().forEach { path.addLine(to: $0) }
                context.stroke(path, with: .color(.black.opacity(0.5)), style: StrokeStyle(lineWidth: 18, lineCap: .round, lineJoin: .round))
                context.stroke(path, with: .color(Color(red: 0.94, green: 0.55, blue: 0.30)), style: StrokeStyle(lineWidth: 9, lineCap: .round, lineJoin: .round))
            }
            if let start = projected.first?.first, let end = projected.last?.last {
                context.fill(Path(ellipseIn: CGRect(x: start.x - 12, y: start.y - 12, width: 24, height: 24)), with: .color(.white))
                context.fill(Path(ellipseIn: CGRect(x: start.x - 5, y: start.y - 5, width: 10, height: 10)), with: .color(Color(red: 0.09, green: 0.23, blue: 0.17)))
                context.fill(Path(ellipseIn: CGRect(x: end.x - 12, y: end.y - 12, width: 24, height: 24)), with: .color(Color(red: 0.94, green: 0.55, blue: 0.30)))
            }
        }
        .background(
            LinearGradient(
                colors: [Color(red: 0.12, green: 0.28, blue: 0.20), Color(red: 0.31, green: 0.43, blue: 0.26)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .accessibilityHidden(true)
    }

    private func projectedSegments(in size: CGSize) -> [[CGPoint]] {
        let segments = routeSegments.map { $0.filter(Self.valid) }.filter { $0.count >= 2 }
        let points = segments.flatMap { $0 }
        guard let minLatitude = points.map(\.latitude).min(),
              let maxLatitude = points.map(\.latitude).max(),
              let minLongitude = points.map(\.longitude).min(),
              let maxLongitude = points.map(\.longitude).max() else { return [] }
        let latitudeSpan = max(0.000_1, maxLatitude - minLatitude)
        let longitudeSpan = max(0.000_1, maxLongitude - minLongitude)
        let padding: CGFloat = 44
        return segments.map { segment in
            segment.map { point in
                CGPoint(
                    x: padding + CGFloat((point.longitude - minLongitude) / longitudeSpan) * (size.width - 2 * padding),
                    y: padding + CGFloat((maxLatitude - point.latitude) / latitudeSpan) * (size.height - 2 * padding)
                )
            }
        }
    }

    private static func valid(_ point: RoutePoint) -> Bool {
        point.latitude.isFinite && point.longitude.isFinite
            && (-90...90).contains(point.latitude) && (-180...180).contains(point.longitude)
    }
}

@MainActor
private enum HikeShareMapSnapshotter {
    static func snapshot(routeSegments: [[RoutePoint]]) async -> UIImage? {
        let segments = routeSegments.map { $0.filter(valid) }.filter { $0.count >= 2 }
        let points = segments.flatMap { $0 }
        guard !points.isEmpty else { return nil }

        let latitudes = points.map(\.latitude)
        let longitudes = points.map(\.longitude)
        guard let north = latitudes.max(), let south = latitudes.min(),
              let east = longitudes.max(), let west = longitudes.min() else { return nil }
        let latitudeDelta = min(170, max(0.002, (north - south) * 1.24))
        let longitudeDelta = min(350, max(0.002, (east - west) * 1.24))
        let options = MKMapSnapshotter.Options()
        options.mapType = .satellite
        options.region = MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: (north + south) / 2, longitude: (east + west) / 2),
            span: MKCoordinateSpan(latitudeDelta: latitudeDelta, longitudeDelta: longitudeDelta)
        )
        options.size = CGSize(width: 968, height: 555)
        options.scale = 1

        guard let snapshot = try? await MKMapSnapshotter(options: options).start() else { return nil }
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        return UIGraphicsImageRenderer(size: options.size, format: format).image { renderer in
            snapshot.image.draw(at: .zero)
            let context = renderer.cgContext
            context.setLineCap(.round)
            context.setLineJoin(.round)
            for segment in segments {
                let path = CGMutablePath()
                let first = snapshot.point(for: CLLocationCoordinate2D(latitude: segment[0].latitude, longitude: segment[0].longitude))
                path.move(to: first)
                for point in segment.dropFirst() {
                    path.addLine(to: snapshot.point(for: CLLocationCoordinate2D(latitude: point.latitude, longitude: point.longitude)))
                }
                context.addPath(path)
                context.setStrokeColor(UIColor(red: 0.08, green: 0.15, blue: 0.12, alpha: 0.78).cgColor)
                context.setLineWidth(10)
                context.strokePath()
                context.addPath(path)
                context.setStrokeColor(UIColor(red: 0.94, green: 0.55, blue: 0.30, alpha: 1).cgColor)
                context.setLineWidth(6)
                context.strokePath()
            }
            if let start = segments.first?.first, let end = segments.last?.last {
                drawMarker(snapshot.point(for: CLLocationCoordinate2D(latitude: start.latitude, longitude: start.longitude)), fill: .white, stroke: UIColor(red: 0.09, green: 0.23, blue: 0.17, alpha: 1), context: context)
                drawMarker(snapshot.point(for: CLLocationCoordinate2D(latitude: end.latitude, longitude: end.longitude)), fill: UIColor(red: 0.94, green: 0.55, blue: 0.30, alpha: 1), stroke: .white, context: context)
            }
        }
    }

    private static func drawMarker(_ point: CGPoint, fill: UIColor, stroke: UIColor, context: CGContext) {
        let rect = CGRect(x: point.x - 8, y: point.y - 8, width: 16, height: 16)
        context.setFillColor(fill.cgColor)
        context.fillEllipse(in: rect)
        context.setStrokeColor(stroke.cgColor)
        context.setLineWidth(3)
        context.strokeEllipse(in: rect)
    }

    private static func valid(_ point: RoutePoint) -> Bool {
        point.latitude.isFinite && point.longitude.isFinite
            && (-90...90).contains(point.latitude) && (-180...180).contains(point.longitude)
    }
}

private enum HikeSharePreparationError: LocalizedError {
    case storageUnavailable

    var errorDescription: String? {
        "HikeJournal could not create a protected temporary share copy."
    }
}

private enum HikeSharePreparer {
    struct Prepared {
        let items: [Any]
        let omittedPhotoCount: Int
    }

    @MainActor
    static func prepare(cardData: Data, hike: Hike, photos: [Photo]) async throws -> Prepared {
        let fileManager = FileManager.default
        let directory = fileManager.temporaryDirectory
            .appendingPathComponent("HikeJournalSharedOutings", isDirectory: true)
        try fileManager.createDirectory(at: directory, withIntermediateDirectories: true)
        cleanExpiredFiles(in: directory, fileManager: fileManager)

        let safeID = safeComponent(hike.id)
        let cardURL = directory.appendingPathComponent("HikeJournal-\(safeID).jpg")
        do {
            try cardData.write(to: cardURL, options: [.atomic, .completeFileProtectionUnlessOpen])
        } catch {
            throw HikeSharePreparationError.storageUnavailable
        }

        var attachments = [cardURL]
        var omitted = 0
        for (index, photo) in photos.prefix(19).enumerated() {
            do {
                if let url = try await cachedPhoto(
                    photo,
                    index: index,
                    safeHikeID: safeID,
                    directory: directory
                ) {
                    attachments.append(url)
                } else {
                    omitted += 1
                }
            } catch is CancellationError {
                throw CancellationError()
            } catch {
                omitted += 1
            }
        }
        return Prepared(items: attachments + [caption(for: hike)], omittedPhotoCount: omitted)
    }

    @MainActor
    private static func cachedPhoto(
        _ photo: Photo,
        index: Int,
        safeHikeID: String,
        directory: URL
    ) async throws -> URL? {
        guard let source = URL(string: photo.url), source.scheme?.lowercased() == "https" else {
            return nil
        }
        var request = URLRequest(url: source, cachePolicy: .returnCacheDataElseLoad, timeoutInterval: 30)
        request.setValue("image/*", forHTTPHeaderField: "Accept")
        let (data, response) = try await URLSession.shared.data(for: request)
        try Task.checkCancellation()
        guard let http = response as? HTTPURLResponse,
              (200..<300).contains(http.statusCode),
              !data.isEmpty,
              data.count <= 35 * 1_024 * 1_024 else { return nil }
        let contentType = (http.mimeType ?? photo.contentType).lowercased()
        guard contentType.hasPrefix("image/") else { return nil }
        let destination = directory.appendingPathComponent(
            "HikeJournal-\(safeHikeID)-photo-\(index + 1).\(fileExtension(for: contentType))"
        )
        try data.write(to: destination, options: [.atomic, .completeFileProtectionUnlessOpen])
        return destination
    }

    private static func caption(for hike: Hike) -> String {
        var values = [
            hike.title.isEmpty ? "A day on the trail" : hike.title,
            JournalDate.display(hike.hikeDate),
        ]
        if let miles = hike.distanceMiles { values.append(String(format: "%.2f miles", miles)) }
        values.append("HikeJournal")
        return values.joined(separator: " · ")
    }

    private static func fileExtension(for contentType: String) -> String {
        switch contentType {
        case "image/png": "png"
        case "image/webp": "webp"
        case "image/heic", "image/heif": "heic"
        default: "jpg"
        }
    }

    private static func safeComponent(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-._"))
        let cleaned = value.unicodeScalars.map { allowed.contains($0) ? Character(String($0)) : "-" }
        let result = String(cleaned.prefix(64))
        return result.isEmpty ? "outing" : result
    }

    private static func cleanExpiredFiles(in directory: URL, fileManager: FileManager) {
        let cutoff = Date().addingTimeInterval(-24 * 60 * 60)
        guard let files = try? fileManager.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: [.contentModificationDateKey],
            options: [.skipsHiddenFiles]
        ) else { return }
        for file in files {
            guard let values = try? file.resourceValues(forKeys: [.contentModificationDateKey]),
                  let modified = values.contentModificationDate,
                  modified < cutoff else { continue }
            try? fileManager.removeItem(at: file)
        }
    }
}

private struct ActivityShareView: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
