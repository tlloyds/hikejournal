from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_android_build_classifies_debug_and_keeps_unsigned_outputs_explicit() -> None:
    script = (ROOT / "build_android.command").read_text(encoding="utf-8")

    assert '"$OUTPUT_APK" --mode development' in script
    assert 'HikeJournal-v${VERSION_NAME}-debug.apk' in script
    assert 'HikeJournal-v${VERSION_NAME}-unsigned.apk' in script
    assert 'HikeJournal-v${VERSION_NAME}-unsigned.aab' in script
    debug_branch = script[script.index("  debug)") : script.index("  personal)")]
    assert 'HikeJournal-v${VERSION_NAME}.apk' not in debug_branch


def test_signed_personal_apk_is_verified_before_canonical_promotion() -> None:
    script = (ROOT / "build_android.command").read_text(encoding="utf-8")

    fingerprint_gate = script.index('ANDROID_EXPECTED_SIGNER_SHA256 is required')
    strict_bundle_verifier = script.index('-verify -strict -verbose -certs')
    bundle_verifier = script.index('jar verified.')
    bundle_signer = script.index('AAB_SIGNER_NORMALIZED=')
    release_verifier = script.index('--expected-signer-sha256 "$EXPECTED_SIGNER_SHA256"')
    canonical_promotion = script.index('mv -f "$STAGED_APK" "$OUTPUT_APK"', release_verifier)

    assert (
        fingerprint_gate
        < strict_bundle_verifier
        < bundle_verifier
        < bundle_signer
        < release_verifier
        < canonical_promotion
    )


def test_build_reads_public_signer_pin_from_process_or_dotenv() -> None:
    script = (ROOT / "build_android.command").read_text(encoding="utf-8")

    assert 'EXPECTED_SIGNER_SHA256="${ANDROID_EXPECTED_SIGNER_SHA256:-}"' in script
    assert "read_dotenv_value ANDROID_EXPECTED_SIGNER_SHA256" in script


def test_strict_aab_verification_trusts_the_configured_android_signer() -> None:
    script = (ROOT / "build_android.command").read_text(encoding="utf-8")

    assert 'read_dotenv_value ANDROID_KEYSTORE_PATH' in script
    assert 'read_dotenv_value ANDROID_KEYSTORE_PASSWORD' in script
    assert '-keystore "$AAB_TRUSTSTORE_PATH"' in script
    assert '-storepass:env HIKEJOURNAL_AAB_STORE_PASSWORD' in script


def test_personal_apk_can_apply_a_verified_signing_rotation_lineage() -> None:
    script = (ROOT / "build_android.command").read_text(encoding="utf-8")

    lineage_signing = script.index('--lineage "$SIGNING_LINEAGE_PATH"')
    release_verifier = script.index(
        '--expected-signer-sha256 "$EXPECTED_SIGNER_SHA256"'
    )
    canonical_promotion = script.index(
        'mv -f "$STAGED_APK" "$OUTPUT_APK"', release_verifier
    )

    assert 'read_dotenv_value ANDROID_PREVIOUS_KEYSTORE_PATH' in script
    assert '--ks "$PREVIOUS_KEYSTORE_PATH"' in script
    assert '--next-signer' in script
    assert '--ks "$AAB_TRUSTSTORE_PATH"' in script
    assert '--rotation-min-sdk-version "$SIGNING_ROTATION_MIN_SDK"' in script
    assert lineage_signing < release_verifier < canonical_promotion


def test_personal_release_requires_a_configured_trail_map_provider() -> None:
    gradle = (ROOT / "android/app/build.gradle.kts").read_text(encoding="utf-8")
    sightings = (
        ROOT
        / "android/app/src/main/java/com/hikejournal/app/ui/SightingsMapScreen.kt"
    ).read_text(encoding="utf-8")
    quests = (
        ROOT
        / "android/app/src/main/java/com/hikejournal/app/ui/QuestSightingsMapScreen.kt"
    ).read_text(encoding="utf-8")

    assert '"MOBILE_TRAIL_MAP_STYLE_URL"' in gradle
    assert 'configuredTrailMapStyleUrl,\n            required = true' in gradle
    assert "demotiles.maplibre.org" not in sightings
    assert "demotiles.maplibre.org" not in quests
    assert "BuildConfig.TRAIL_MAP_STYLE_URL" in sightings
    assert "BuildConfig.TRAIL_MAP_STYLE_URL" in quests
