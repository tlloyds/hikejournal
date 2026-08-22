import Photos
import PhotosUI
import SwiftUI
import UIKit

@MainActor
final class PhotoLibraryBrowserModel: ObservableObject {
    @Published private(set) var authorization: PHAuthorizationStatus
    @Published private(set) var assets: [PHAsset] = []
    @Published var selection: Set<String> = []
    @Published private(set) var isLoading = false

    let selectionLimit: Int
    private var observer: PhotoLibraryChangeObserver?

    init(selectionLimit: Int) {
        self.selectionLimit = max(0, min(selectionLimit, 500))
        authorization = PHPhotoLibrary.authorizationStatus(for: .readWrite)
    }

    func start() {
        guard observer == nil else { return }
        let observer = PhotoLibraryChangeObserver { [weak self] in
            Task { @MainActor [weak self] in self?.reload() }
        }
        self.observer = observer
        PHPhotoLibrary.shared().register(observer)
        reload()
    }

    func stop() {
        if let observer {
            PHPhotoLibrary.shared().unregisterChangeObserver(observer)
        }
        observer = nil
    }

    func requestAccess() async {
        authorization = await PHPhotoLibrary.requestAuthorization(for: .readWrite)
        reload()
    }

    func reload() {
        authorization = PHPhotoLibrary.authorizationStatus(for: .readWrite)
        guard authorization == .authorized || authorization == .limited else {
            assets = []
            selection = []
            return
        }
        isLoading = true
        let options = PHFetchOptions()
        options.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: false)]
        options.predicate = NSPredicate(
            format: "mediaType == %d OR mediaType == %d",
            PHAssetMediaType.image.rawValue,
            PHAssetMediaType.video.rawValue
        )
        let result = PHAsset.fetchAssets(with: options)
        var fetched: [PHAsset] = []
        fetched.reserveCapacity(result.count)
        result.enumerateObjects { asset, _, _ in fetched.append(asset) }
        assets = fetched
        selection.formIntersection(Set(fetched.map(\.localIdentifier)))
        isLoading = false
    }

    func toggle(_ asset: PHAsset) {
        if selection.remove(asset.localIdentifier) != nil { return }
        guard selection.count < selectionLimit else { return }
        selection.insert(asset.localIdentifier)
    }

    func orderedSelection() -> [String] {
        assets.compactMap { selection.contains($0.localIdentifier) ? $0.localIdentifier : nil }
    }
}

struct PhotoLibraryBrowser: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @StateObject private var model: PhotoLibraryBrowserModel
    @State private var isImporting = false
    @State private var errorMessage: String?

    let importSelection: ([String]) async throws -> Void

    init(
        selectionLimit: Int,
        importSelection: @escaping ([String]) async throws -> Void
    ) {
        _model = StateObject(
            wrappedValue: PhotoLibraryBrowserModel(selectionLimit: selectionLimit)
        )
        self.importSelection = importSelection
    }

    var body: some View {
        NavigationStack {
            Group {
                switch model.authorization {
                case .notDetermined:
                    permissionPrimer
                case .denied, .restricted:
                    permissionDenied
                case .authorized, .limited:
                    library
                @unknown default:
                    permissionDenied
                }
            }
            .background(ParchmentBackground())
            .navigationTitle("Add original media")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                if model.authorization == .authorized || model.authorization == .limited {
                    ToolbarItem(placement: .confirmationAction) {
                        Button(isImporting ? "Securing…" : "Add \(model.selection.count)") {
                            importSelected()
                        }
                        .disabled(model.selection.isEmpty || isImporting)
                    }
                }
            }
            .alert("Media import paused", isPresented: Binding(
                get: { errorMessage != nil },
                set: { if !$0 { errorMessage = nil } }
            )) {
                Button("OK") { errorMessage = nil }
            } message: {
                Text(errorMessage ?? "")
            }
        }
        .onAppear { model.start() }
        .onDisappear { model.stop() }
    }

    private var permissionPrimer: some View {
        VStack(alignment: .leading, spacing: 14) {
            Spacer()
            Image(systemName: "photo.on.rectangle.angled")
                .font(.system(size: 52, weight: .light))
                .foregroundStyle(HikeJournalTheme.moss)
                .accessibilityHidden(true)
            Text("Keep where the moment happened.")
                .font(HikeJournalTheme.display(38, relativeTo: .largeTitle))
                .foregroundStyle(HikeJournalTheme.ink)
            Text("HikeJournal reads only the photos and videos you allow. It uses the Photos-library location when one exists, then copies the original into private app storage before upload.")
                .font(HikeJournalTheme.body(18))
                .foregroundStyle(HikeJournalTheme.inkMuted)
            Spacer()
            Button("Choose photo access") {
                Task { await model.requestAccess() }
            }
            .buttonStyle(TrailButtonStyle())
        }
        .padding(24)
    }

    private var permissionDenied: some View {
        VStack(alignment: .leading, spacing: 14) {
            Spacer()
            Image(systemName: "photo.badge.exclamationmark")
                .font(.system(size: 52, weight: .light))
                .foregroundStyle(HikeJournalTheme.trailText)
                .accessibilityHidden(true)
            Text("Photos access is off.")
                .font(HikeJournalTheme.display(38, relativeTo: .largeTitle))
                .foregroundStyle(HikeJournalTheme.ink)
            Text("Turn on full or limited access in Settings. HikeJournal never substitutes a cloud-provider file that might omit its GPS metadata.")
                .font(HikeJournalTheme.body(18))
                .foregroundStyle(HikeJournalTheme.inkMuted)
            Spacer()
            Button("Open iPhone Settings") {
                if let url = URL(string: UIApplication.openSettingsURLString) {
                    openURL(url)
                }
            }
            .buttonStyle(TrailButtonStyle())
        }
        .padding(24)
    }

    private var library: some View {
        VStack(spacing: 0) {
            if model.authorization == .limited {
                HStack(spacing: 10) {
                    Image(systemName: "photo.stack")
                    Text("Limited Photos access")
                        .font(HikeJournalTheme.label(15, relativeTo: .headline))
                    Spacer()
                    Button("Manage") { presentLimitedLibraryPicker() }
                }
                .foregroundStyle(HikeJournalTheme.moss)
                .padding(.horizontal, 16)
                .frame(minHeight: 48)
                .background(HikeJournalTheme.paper.opacity(0.96))
            }

            if model.selectionLimit == 0 {
                ContentUnavailableView {
                    Label("Cloud media limit reached", systemImage: "icloud.slash")
                } description: {
                    Text("Delete cloud media or choose Plus before adding another item.")
                }
            } else if model.assets.isEmpty && !model.isLoading {
                ContentUnavailableView(
                    "No allowed media",
                    systemImage: "photo",
                    description: Text("Choose more items if Photos access is limited.")
                )
            } else {
                ScrollView {
                    LazyVGrid(
                        columns: [GridItem(.adaptive(minimum: 106), spacing: 2)],
                        spacing: 2
                    ) {
                        ForEach(model.assets, id: \.localIdentifier) { asset in
                            PhotoAssetTile(
                                asset: asset,
                                selectedIndex: selectionIndex(asset),
                                selectionEnabled: model.selection.contains(asset.localIdentifier)
                                    || model.selection.count < model.selectionLimit
                            ) {
                                model.toggle(asset)
                            }
                        }
                    }
                }
                .overlay(alignment: .bottom) {
                    if isImporting {
                        HStack(spacing: 10) {
                            ProgressView()
                            Text("Downloading originals and securing them…")
                                .font(HikeJournalTheme.label(14, relativeTo: .subheadline))
                        }
                        .padding(.horizontal, 16)
                        .frame(minHeight: 50)
                        .background(.regularMaterial)
                        .accessibilityElement(children: .combine)
                    }
                }
            }
        }
    }

    private func selectionIndex(_ asset: PHAsset) -> Int? {
        model.orderedSelection().firstIndex(of: asset.localIdentifier).map { $0 + 1 }
    }

    private func importSelected() {
        let identifiers = model.orderedSelection()
        guard !identifiers.isEmpty else { return }
        isImporting = true
        Task {
            do {
                try await importSelection(identifiers)
                isImporting = false
                dismiss()
            } catch is CancellationError {
                isImporting = false
            } catch {
                isImporting = false
                errorMessage = (error as? LocalizedError)?.errorDescription
                    ?? "HikeJournal couldn't secure those items."
            }
        }
    }

    private func presentLimitedLibraryPicker() {
        guard let presenter = UIApplication.shared.hikeJournalPhotoPresenter else { return }
        PHPhotoLibrary.shared().presentLimitedLibraryPicker(from: presenter)
    }
}

private struct PhotoAssetTile: View {
    let asset: PHAsset
    let selectedIndex: Int?
    let selectionEnabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            GeometryReader { proxy in
                ZStack {
                    PhotoAssetThumbnail(asset: asset, targetSize: proxy.size)
                    LinearGradient(
                        colors: [.clear, .black.opacity(0.48)],
                        startPoint: .center,
                        endPoint: .bottom
                    )
                    if let selectedIndex {
                        Color.black.opacity(0.12)
                        Image(systemName: "\(min(selectedIndex, 50)).circle.fill")
                            .font(.system(size: 27, weight: .semibold))
                            .foregroundStyle(.white, HikeJournalTheme.trail)
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                            .padding(7)
                    }
                    HStack(spacing: 6) {
                        if asset.mediaType == .video {
                            Label(duration, systemImage: "video.fill")
                        }
                        Spacer()
                        if asset.location != nil {
                            Image(systemName: "location.fill")
                                .accessibilityLabel("Has a Photos location")
                        }
                    }
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.white)
                    .padding(7)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
                }
            }
            .aspectRatio(1, contentMode: .fit)
            .opacity(selectionEnabled ? 1 : 0.45)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!selectionEnabled)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityValue(selectedIndex.map { "Selected, item \($0)" } ?? "Not selected")
    }

    private var duration: String {
        let seconds = max(0, Int(asset.duration.rounded()))
        return String(format: "%d:%02d", seconds / 60, seconds % 60)
    }

    private var accessibilityLabel: String {
        var parts = [asset.mediaType == .video ? "Video" : "Photo"]
        if let date = asset.creationDate {
            parts.append(date.formatted(date: .abbreviated, time: .shortened))
        }
        parts.append(asset.location == nil ? "No Photos location" : "Has Photos location")
        return parts.joined(separator: ", ")
    }
}

private struct PhotoAssetThumbnail: View {
    let asset: PHAsset
    let targetSize: CGSize
    @State private var image: UIImage?
    @State private var requestID: PHImageRequestID?

    var body: some View {
        ZStack {
            Color(red: 0.12, green: 0.20, blue: 0.14)
            if let image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
            } else {
                ProgressView().tint(.white)
            }
        }
        .clipped()
        .task(id: asset.localIdentifier + "\(targetSize.width)") {
            requestThumbnail()
        }
        .onDisappear {
            if let requestID { PHImageManager.default().cancelImageRequest(requestID) }
        }
    }

    private func requestThumbnail() {
        let scale = UIScreen.main.scale
        let options = PHImageRequestOptions()
        options.deliveryMode = .opportunistic
        options.resizeMode = .fast
        options.isNetworkAccessAllowed = true
        requestID = PHImageManager.default().requestImage(
            for: asset,
            targetSize: CGSize(
                width: max(160, targetSize.width * scale),
                height: max(160, targetSize.height * scale)
            ),
            contentMode: .aspectFill,
            options: options
        ) { result, _ in
            if let result { image = result }
        }
    }
}

private final class PhotoLibraryChangeObserver: NSObject, PHPhotoLibraryChangeObserver {
    let changed: @Sendable () -> Void

    init(changed: @escaping @Sendable () -> Void) {
        self.changed = changed
    }

    func photoLibraryDidChange(_ changeInstance: PHChange) {
        changed()
    }
}

private extension UIApplication {
    var hikeJournalPhotoPresenter: UIViewController? {
        connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .filter { $0.activationState == .foregroundActive }
            .flatMap(\.windows)
            .first(where: \.isKeyWindow)?
            .rootViewController
    }
}
