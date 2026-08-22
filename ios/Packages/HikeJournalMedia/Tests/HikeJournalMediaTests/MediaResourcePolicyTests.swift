import Foundation
import XCTest
@testable import HikeJournalMedia

final class MediaResourcePolicyTests: XCTestCase {
    private let policy = MediaResourceSelectionPolicy()

    func testCurrentEditAndOriginalPoliciesChooseDifferentPhotoResources() throws {
        let assetID = "edited-photo"
        let original = makeResource(
            assetID: assetID,
            index: 0,
            kind: .photo,
            filename: "IMG_1000.HEIC",
            uniformTypeIdentifier: "public.heic"
        )
        let adjustment = makeResource(
            assetID: assetID,
            index: 1,
            kind: .adjustmentData,
            filename: "Adjustments.plist",
            uniformTypeIdentifier: "com.apple.property-list"
        )
        let edited = makeResource(
            assetID: assetID,
            index: 2,
            kind: .fullSizePhoto,
            filename: "IMG_E1000.JPG",
            uniformTypeIdentifier: "public.jpeg"
        )
        let asset = makeImageAsset(
            id: assetID,
            resources: [original, adjustment, edited]
        )

        let current = try policy.selectResources(
            for: asset,
            representation: .currentEditsWhenAvailable
        )
        let originals = try policy.selectResources(
            for: asset,
            representation: .originalsOnly
        )

        XCTAssertEqual(current.map(\.resource), [edited])
        XCTAssertEqual(originals.map(\.resource), [original])
        XCTAssertFalse(current.contains { $0.resource.kind == .adjustmentData })
    }

    func testCurrentVideoPrefersFullSizeEditAndOriginalPolicyDoesNotFallbackToIt() throws {
        let assetID = "edited-video"
        let original = makeResource(
            assetID: assetID,
            index: 0,
            kind: .video,
            filename: "IMG_2000.MOV",
            uniformTypeIdentifier: "com.apple.quicktime-movie"
        )
        let edited = makeResource(
            assetID: assetID,
            index: 1,
            kind: .fullSizeVideo,
            filename: "IMG_E2000.MOV",
            uniformTypeIdentifier: "com.apple.quicktime-movie"
        )
        let asset = MediaAssetSnapshot(
            localIdentifier: assetID,
            kind: .video,
            creationDate: nil,
            sourceLocation: nil,
            pixelWidth: 1_920,
            pixelHeight: 1_080,
            duration: 4,
            resources: [edited, original]
        )

        XCTAssertEqual(
            try policy.selectResources(
                for: asset,
                representation: .currentEditsWhenAvailable
            ).map(\.resource),
            [edited]
        )
        XCTAssertEqual(
            try policy.selectResources(
                for: asset,
                representation: .originalsOnly
            ).map(\.resource),
            [original]
        )
    }

    func testLivePhotoPreservesStillAndMotionForBothPolicies() throws {
        let asset = makeLivePhotoAsset()

        let current = try policy.selectResources(
            for: asset,
            representation: .currentEditsWhenAvailable
        )
        let original = try policy.selectResources(
            for: asset,
            representation: .originalsOnly
        )

        XCTAssertEqual(current.map(\.role), [.primary, .livePhotoMotion])
        XCTAssertEqual(current.map(\.resource.kind), [.fullSizePhoto, .fullSizePairedVideo])
        XCTAssertEqual(original.map(\.resource.kind), [.photo, .pairedVideo])
    }

    func testLivePhotoWithoutMotionFailsInsteadOfSilentlyDiscardingMotion() throws {
        let asset = MediaAssetSnapshot(
            localIdentifier: "broken-live",
            kind: .livePhoto,
            creationDate: nil,
            sourceLocation: nil,
            pixelWidth: 10,
            pixelHeight: 10,
            duration: nil,
            resources: [
                makeResource(
                    assetID: "broken-live",
                    index: 0,
                    kind: .photo,
                    filename: "still.heic",
                    uniformTypeIdentifier: "public.heic"
                )
            ]
        )

        XCTAssertThrowsError(
            try policy.selectResources(for: asset, representation: .originalsOnly)
        ) { error in
            XCTAssertEqual(
                error as? MediaIngestionError,
                .requiredResourceMissing(
                    assetIdentifier: "broken-live",
                    role: .livePhotoMotion
                )
            )
        }
    }

    func testCoordinateValidationNeverClampsOrInvents() throws {
        let boundary = try XCTUnwrap(
            MediaCoordinate(
                validating: MediaSourceLocation(latitude: 90, longitude: -180)
            )
        )
        XCTAssertEqual(boundary.latitude, 90)
        XCTAssertEqual(boundary.longitude, -180)
        XCTAssertNil(MediaCoordinate(validating: nil))
        XCTAssertNil(
            MediaCoordinate(
                validating: MediaSourceLocation(latitude: .nan, longitude: 0)
            )
        )
        XCTAssertNil(
            MediaCoordinate(
                validating: MediaSourceLocation(latitude: 0, longitude: .infinity)
            )
        )
        XCTAssertNil(
            MediaCoordinate(
                validating: MediaSourceLocation(latitude: 90.000_001, longitude: 0)
            )
        )
        XCTAssertNil(
            MediaCoordinate(
                validating: MediaSourceLocation(latitude: 0, longitude: -180.000_001)
            )
        )
        XCTAssertThrowsError(
            try JSONDecoder().decode(
                MediaCoordinate.self,
                from: Data(#"{"latitude":90.000001,"longitude":0}"#.utf8)
            )
        )
    }

    func testUnsupportedAssetHasTypedFailure() {
        let asset = MediaAssetSnapshot(
            localIdentifier: "audio-1",
            kind: .unsupported,
            creationDate: nil,
            sourceLocation: nil,
            pixelWidth: 0,
            pixelHeight: 0,
            duration: nil,
            resources: []
        )

        XCTAssertThrowsError(
            try policy.selectResources(for: asset, representation: .originalsOnly)
        ) { error in
            XCTAssertEqual(error as? MediaIngestionError, .unsupportedAsset("audio-1"))
        }
    }
}
