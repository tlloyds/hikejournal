import HikeJournalDomain
import XCTest
@testable import HikeJournal

@MainActor
final class HikeSharePreparationTests: XCTestCase {
    func testEveryModeExportsTheCorrectOrderAndMaximumPhotoCount() async throws {
        let session = makeSession()
        defer { session.invalidateAndCancel() }
        let photos = (0..<24).map { photo("photo-\($0)") }
        for mode in HikeShareKeepsake.allCases {
            let prepared = try await HikeSharePreparer.prepare(
                cardData: mode.includesKeepsake ? Data("keepsake".utf8) : nil,
                hike: hike(), photos: photos, keepsake: mode, session: session
            )
            let urls = prepared.items.compactMap { $0 as? URL }
            let contents = try urls.map { String(decoding: try Data(contentsOf: $0), as: UTF8.self) }
            let expectedPhotos = photos.prefix(mode.includesKeepsake ? 19 : 20).map(\.id)
            let expected = mode == .first ? ["keepsake"] + expectedPhotos
                : mode == .last ? expectedPhotos + ["keepsake"] : expectedPhotos
            XCTAssertEqual(contents, expected, mode.rawValue)
            XCTAssertEqual(urls.count, 20)
            XCTAssertEqual(prepared.omittedPhotoCount, 0)
        }
    }

    func testUnavailablePhotosAreOmittedWhileKeepsakeRemainsLast() async throws {
        let session = makeSession()
        defer { session.invalidateAndCancel() }
        let prepared = try await HikeSharePreparer.prepare(
            cardData: Data("keepsake".utf8), hike: hike(),
            photos: [photo("second"), photo("unavailable"), photo("first")],
            keepsake: .last, session: session
        )
        let contents = try prepared.items.compactMap { $0 as? URL }.map {
            String(decoding: try Data(contentsOf: $0), as: UTF8.self)
        }
        XCTAssertEqual(contents, ["second", "first", "keepsake"])
        XCTAssertEqual(prepared.omittedPhotoCount, 1)
    }

    func testNoKeepsakeRejectsEmptyOrEntirelyUnavailablePhotos() async {
        let session = makeSession()
        defer { session.invalidateAndCancel() }
        for photos in [[], [photo("unavailable")]] {
            do {
                _ = try await HikeSharePreparer.prepare(
                    cardData: nil, hike: hike(), photos: photos, keepsake: .none, session: session
                )
                XCTFail("An empty image share must fail before opening the share sheet")
            } catch {
                XCTAssertTrue(error.localizedDescription.contains("No selected photos were available"))
            }
        }
    }

    func testKeepsakeCanBeSharedAloneInEitherPosition() async throws {
        for mode in [HikeShareKeepsake.first, .last] {
            let prepared = try await HikeSharePreparer.prepare(
                cardData: Data("keepsake".utf8), hike: hike(), photos: [], keepsake: mode
            )
            XCTAssertEqual(prepared.items.compactMap { $0 as? URL }.count, 1)
        }
    }

    func testPhotoEligibilityExcludesVideosAndBlankURLsInEveryMode() {
        let photos = [photo("image"), photo("video", contentType: "VIDEO/MP4"), photo("blank", url: "   ")]
        for mode in HikeShareKeepsake.allCases {
            XCTAssertEqual(mode.shareablePhotos(photos).map(\.id), ["image"])
        }
    }

    private func makeSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [SharePhotoURLProtocol.self]
        return URLSession(configuration: configuration)
    }

    private func hike() -> Hike {
        Hike(id: "share-test-\(UUID())", title: "Pine Loop", hikeDate: "2026-10-22",
             distanceMiles: 3.2, locationName: "Pine Woods", notes: "", isArchived: false,
             coverUrl: "", photoCount: 24, speciesCount: 0)
    }

    private func photo(_ id: String, contentType: String = "image/jpeg", url: String? = nil) -> Photo {
        Photo(id: id, hikeId: "share-test", url: url ?? "https://share.test/\(id)", caption: "",
              takenAt: nil, createdAt: nil, latitude: nil, longitude: nil, width: nil, height: nil,
              contentType: contentType, processingStatus: "ready", species: [])
    }
}

private final class SharePhotoURLProtocol: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        guard let url = request.url,
              let response = HTTPURLResponse(
                url: url, statusCode: url.lastPathComponent == "unavailable" ? 404 : 200,
                httpVersion: nil, headerFields: ["Content-Type": "image/jpeg"]
              ) else { return }
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(url.lastPathComponent.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}
