import XCTest
@testable import HikeJournal

final class AppConfigurationTests: XCTestCase {
    func testLoadsSafePublicConfiguration() {
        let configuration = AppConfiguration(infoDictionary: [
            "HikeJournalAPIBaseURL": "https://api.hikejournal.example",
            "HikeJournalAPIKey": "paired-device-key",
            "HikeJournalWebBaseURL": "https://hikejournal.example",
            "HikeJournalMapStyleURL": "https://tiles.hikejournal.example/style.json",
            "HikeJournalMapAttributionTitle": "Open map contributors",
            "HikeJournalMapAttributionURL": "https://tiles.hikejournal.example/attribution",
            "HikeJournalMapStyleToken": "public-map-token",
            "HikeJournalMapStyleTokenQueryItemName": "access_token",
            "HikeJournalCallbackScheme": "hikejournal",
            "GoogleIOSClientID": "123-ios.apps.googleusercontent.com",
            "GoogleServerClientID": "123-server.apps.googleusercontent.com",
            "GoogleReversedClientID": "com.googleusercontent.apps.123-ios"
        ])

        XCTAssertEqual(configuration.apiBaseURL?.absoluteString, "https://api.hikejournal.example")
        XCTAssertEqual(configuration.apiKey, "paired-device-key")
        XCTAssertEqual(configuration.mapStyleURL?.path, "/style.json")
        XCTAssertEqual(configuration.mapAttributionTitle, "Open map contributors")
        XCTAssertEqual(configuration.mapAttributionURL?.path, "/attribution")
        XCTAssertEqual(configuration.mapStyleToken, "public-map-token")
        XCTAssertEqual(configuration.mapStyleTokenQueryItemName, "access_token")
        XCTAssertEqual(configuration.callbackScheme, "hikejournal")
        XCTAssertTrue(configuration.isGoogleSignInConfigured)
    }

    func testRejectsCredentialsEmbeddedInBaseURL() {
        let configuration = AppConfiguration(infoDictionary: [
            "HikeJournalAPIBaseURL": "https://user:password@api.hikejournal.example"
        ])

        XCTAssertNil(configuration.apiBaseURL)
    }

    func testTreatsProviderPlaceholdersAsUnconfigured() {
        let configuration = AppConfiguration(infoDictionary: [
            "HikeJournalAPIKey": "CONFIGURE_ME",
            "GoogleIOSClientID": "CONFIGURE_ME.apps.googleusercontent.com",
            "GoogleServerClientID": "CONFIGURE_ME.apps.googleusercontent.com",
            "GoogleReversedClientID": "com.googleusercontent.apps.CONFIGURE_ME"
        ])

        XCTAssertNil(configuration.googleIOSClientID)
        XCTAssertNil(configuration.apiKey)
        XCTAssertFalse(configuration.isGoogleSignInConfigured)
    }

    func testRejectsURLQueryAndFragment() {
        let configuration = AppConfiguration(infoDictionary: [
            "HikeJournalAPIBaseURL": "https://api.hikejournal.example?token=nope",
            "HikeJournalWebBaseURL": "https://hikejournal.example/#account"
        ])

        XCTAssertNil(configuration.apiBaseURL)
        XCTAssertNil(configuration.webBaseURL)
    }

    func testRejectsUnsafeMapProviderConfiguration() {
        let configuration = AppConfiguration(infoDictionary: [
            "HikeJournalMapAttributionURL": "http://tiles.hikejournal.example/attribution",
            "HikeJournalMapStyleToken": "CONFIGURE_ME",
            "HikeJournalMapStyleTokenQueryItemName": "access token"
        ])

        XCTAssertNil(configuration.mapAttributionURL)
        XCTAssertNil(configuration.mapStyleToken)
        XCTAssertNil(configuration.mapStyleTokenQueryItemName)
    }
}
