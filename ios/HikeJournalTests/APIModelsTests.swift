import XCTest
@testable import HikeJournal

final class APIModelsTests: XCTestCase {
    func testDecodesAdditiveMobileConfiguration() throws {
        let data = Data(
            #"""
            {
              "web_url": "https://hikejournal.example",
              "api_version": "0.8.6",
              "capabilities": ["offline_sync", "apple_auth", "offline_sync"],
              "contract_version": "1",
              "compatibility": {
                "minimum_android_version": null,
                "recommended_android_version": "0.8.6"
              },
              "authentication": {
                "mode": "google",
                "google_client_id": "server.apps.googleusercontent.com"
              }
            }
            """#.utf8
        )

        let configuration = try JSONDecoder.hikeJournal.decode(MobileConfiguration.self, from: data)

        XCTAssertEqual(configuration.webURL.host, "hikejournal.example")
        XCTAssertEqual(configuration.apiVersion, "0.8.6")
        XCTAssertEqual(configuration.capabilities, ["offline_sync", "apple_auth"])
        XCTAssertEqual(configuration.contractVersion, "1")
        XCTAssertEqual(configuration.authentication.mode, "google")
        XCTAssertEqual(configuration.compatibility.recommendedAndroidVersion, "0.8.6")
        XCTAssertNil(configuration.compatibility.minimumIOSVersion)
    }

    func testDecodesProviderNeutralSessionWithoutBreakingLegacyFields() throws {
        let payload = try JSONDecoder.hikeJournal.decode(
            MobileSessionPayload.self,
            from: Data(
                #"""
                {
                  "access_token": "access-value",
                  "refresh_token": "refresh-value",
                  "expires_in": 1200,
                  "token_type": "Bearer",
                  "account": {
                    "subject": "apple:000123",
                    "email": "relay@privaterelay.appleid.com",
                    "display_name": "Avery",
                    "picture_url": "",
                    "user_id": "00000000-0000-0000-0000-000000000123",
                    "identity_provider": "apple"
                  }
                }
                """#.utf8
            )
        )
        let obtainedAt = Date(timeIntervalSince1970: 1_000)
        let session = AuthSession(payload: payload, obtainedAt: obtainedAt)

        XCTAssertEqual(session.account.subject, "apple:000123")
        XCTAssertEqual(session.account.userID, "00000000-0000-0000-0000-000000000123")
        XCTAssertEqual(session.account.identityProvider, "apple")
        XCTAssertNil(session.account.pictureURL)
        XCTAssertFalse(session.needsRefresh(at: obtainedAt.addingTimeInterval(1_100)))
        XCTAssertTrue(session.needsRefresh(at: obtainedAt.addingTimeInterval(1_141)))
    }

    func testEncodesAppleNonceContractWithServerKeys() throws {
        let request = AppleAuthenticationRequest(
            identityToken: "signed.identity.token",
            deviceID: "device-12345678",
            nonce: "raw-nonce-1234567890",
            displayName: "River Hiker"
        )

        let object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: JSONEncoder().encode(request)) as? [String: String]
        )

        XCTAssertEqual(object["identity_token"], "signed.identity.token")
        XCTAssertEqual(object["device_id"], "device-12345678")
        XCTAssertEqual(object["nonce"], "raw-nonce-1234567890")
        XCTAssertEqual(object["display_name"], "River Hiker")
    }

    func testDecodesServerAuthoritativeLifetimeWithoutUpgradePrompt() throws {
        let entitlement = try JSONDecoder.hikeJournal.decode(
            EntitlementSnapshot.self,
            from: entitlementData(
                plan: "lifetime",
                source: "google_play_legacy",
                billingPeriod: "lifetime",
                status: "active",
                expiresAt: nil
            )
        )

        XCTAssertEqual(entitlement.plan, .lifetime)
        XCTAssertEqual(entitlement.source, .googlePlayLegacy)
        XCTAssertEqual(entitlement.billingPeriod, .lifetime)
        XCTAssertFalse(entitlement.shouldOfferUpgrade)
        XCTAssertTrue(entitlement.allows("offline_maps"))
        XCTAssertNil(entitlement.limits.cloudHikes)
    }

    func testUnknownPlanAndFeatureFailClosed() throws {
        let entitlement = try JSONDecoder.hikeJournal.decode(
            EntitlementSnapshot.self,
            from: entitlementData(
                plan: "future_plan",
                source: "future_source",
                billingPeriod: nil,
                status: "future_status",
                expiresAt: "2026-09-21T12:00:00.123Z"
            )
        )

        XCTAssertEqual(entitlement.plan, .unknown("future_plan"))
        XCTAssertEqual(entitlement.status, .unknown("future_status"))
        XCTAssertFalse(entitlement.shouldOfferUpgrade)
        XCTAssertFalse(entitlement.allows("unannounced_feature"))
        XCTAssertNotNil(entitlement.expiresAt)
    }

    func testStoredSessionRoundTripsDeterministically() throws {
        let account = AuthAccount(
            subject: "google-subject",
            email: "hiker@example.com",
            displayName: "Hiker",
            pictureURL: URL(string: "https://images.example/hiker.jpg"),
            userID: "00000000-0000-0000-0000-000000000001",
            identityProvider: "google"
        )
        let original = AuthSession(
            accessToken: "access",
            refreshToken: "refresh",
            expiresIn: 1_200,
            account: account,
            obtainedAt: Date(timeIntervalSince1970: 1_777_777_777)
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .millisecondsSince1970
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .millisecondsSince1970

        let restored = try decoder.decode(AuthSession.self, from: encoder.encode(original))

        XCTAssertEqual(restored, original)
    }

    private func entitlementData(
        plan: String,
        source: String,
        billingPeriod: String?,
        status: String,
        expiresAt: String?
    ) throws -> Data {
        let payload: [String: Any] = [
            "plan": plan,
            "source": source,
            "billing_period": billingPeriod.map { $0 as Any } ?? NSNull(),
            "status": status,
            "product_id": "com.hikejournal.app.plus.annual",
            "expires_at": expiresAt.map { $0 as Any } ?? NSNull(),
            "grace_expires_at": NSNull(),
            "limits": ["cloud_hikes": NSNull(), "cloud_media": 10_000],
            "usage": ["cloud_hikes": 9, "cloud_media": 47],
            "features": ["offline_maps": true, "field_briefing": true],
            "policy": ["version": "2026-08-21", "android_paid_compatibility": "observe_only"]
        ]
        return try JSONSerialization.data(withJSONObject: payload)
    }
}
