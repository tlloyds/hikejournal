import Foundation
import UniformTypeIdentifiers

public struct MediaResourceSelectionPolicy: Sendable {
    public init() {}

    public func selectResources(
        for asset: MediaAssetSnapshot,
        representation: MediaRepresentationPolicy
    ) throws -> [SelectedMediaResource] {
        switch asset.kind {
        case .image:
            return [
                SelectedMediaResource(
                    role: .primary,
                    resource: try select(
                        from: asset,
                        role: .primary,
                        priorities: representation == .originalsOnly
                            ? [.photo, .alternatePhoto]
                            : [.fullSizePhoto, .photo, .alternatePhoto]
                    )
                )
            ]
        case .video:
            return [
                SelectedMediaResource(
                    role: .primary,
                    resource: try select(
                        from: asset,
                        role: .primary,
                        priorities: representation == .originalsOnly
                            ? [.video]
                            : [.fullSizeVideo, .video]
                    )
                )
            ]
        case .livePhoto:
            let still = try select(
                from: asset,
                role: .primary,
                priorities: representation == .originalsOnly
                    ? [.photo, .alternatePhoto]
                    : [.fullSizePhoto, .photo, .alternatePhoto]
            )
            let motion = try select(
                from: asset,
                role: .livePhotoMotion,
                priorities: representation == .originalsOnly
                    ? [.pairedVideo]
                    : [.fullSizePairedVideo, .pairedVideo]
            )
            return [
                SelectedMediaResource(role: .primary, resource: still),
                SelectedMediaResource(role: .livePhotoMotion, resource: motion),
            ]
        case .unsupported:
            throw MediaIngestionError.unsupportedAsset(asset.localIdentifier)
        }
    }

    private func select(
        from asset: MediaAssetSnapshot,
        role: StagedMediaRole,
        priorities: [MediaResourceKind]
    ) throws -> MediaResourceDescriptor {
        for kind in priorities {
            if let resource = asset.resources
                .filter({ $0.kind == kind })
                .sorted(by: { $0.sourceIndex < $1.sourceIndex })
                .first {
                return resource
            }
        }
        throw MediaIngestionError.requiredResourceMissing(
            assetIdentifier: asset.localIdentifier,
            role: role
        )
    }
}

enum MediaTypeResolver {
    static func metadata(
        for resource: MediaResourceDescriptor,
        role: StagedMediaRole,
        assetKind: MediaAssetKind
    ) -> (originalFilename: String, stagedFilename: String, contentType: String) {
        let originalFilename = safeOriginalFilename(
            resource.originalFilename,
            fallbackStem: role.rawValue
        )
        let declaredType = UTType(resource.uniformTypeIdentifier)
        let extensionType = UTType(filenameExtension: (originalFilename as NSString).pathExtension)
        let resolvedType = declaredType ?? extensionType
        let fallbackExtension: String
        let fallbackMIME: String
        if role == .livePhotoMotion || assetKind == .video {
            fallbackExtension = "mov"
            fallbackMIME = "video/quicktime"
        } else {
            fallbackExtension = "jpg"
            fallbackMIME = "image/jpeg"
        }
        let fileExtension = safeExtension(resolvedType?.preferredFilenameExtension)
            ?? safeExtension((originalFilename as NSString).pathExtension)
            ?? fallbackExtension
        return (
            originalFilename,
            "\(role.rawValue).\(fileExtension.lowercased())",
            resolvedType?.preferredMIMEType ?? fallbackMIME
        )
    }

    private static func safeOriginalFilename(_ value: String, fallbackStem: String) -> String {
        let withoutDirectories = value
            .replacingOccurrences(of: "\\", with: "/")
            .split(separator: "/")
            .last
            .map(String.init)
            ?? ""
        let filtered = withoutDirectories.unicodeScalars.filter {
            !CharacterSet.controlCharacters.contains($0) && $0.value != 0
        }
        let clean = String(String.UnicodeScalarView(filtered))
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let usable = clean.isEmpty || clean == "." || clean == ".."
            ? fallbackStem
            : clean
        return String(usable.prefix(180))
    }

    private static func safeExtension(_ value: String?) -> String? {
        guard let value = value?.lowercased(),
              (1...12).contains(value.count),
              value.unicodeScalars.allSatisfy({ CharacterSet.alphanumerics.contains($0) }) else {
            return nil
        }
        return value
    }
}
