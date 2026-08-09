#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ANDROID_DIR="$ROOT/android"
ARTIFACT_VERIFIER="$ROOT/scripts/verify_android_artifact.py"
JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@17}"
ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ANDROID_BUILD_DIR="${HIKEJOURNAL_ANDROID_BUILD_DIR:-$HOME/.cache/hikejournal-android-build}"
BUILD_MODE="${1:-debug}"

if [ ! -x "$JAVA_HOME/bin/java" ]; then
  echo "HikeJournal needs JDK 17. Install it with: brew install openjdk@17"
  exit 1
fi

if [ "$BUILD_MODE" = "debug" ] && [ ! -f "$ROOT/.env" ]; then
  echo "The root .env file is required to pair this build with the companion API."
  exit 1
fi

cd "$ANDROID_DIR"
mkdir -p "$ROOT/dist"
VERSION_NAME="$(tr -d '[:space:]' < "$ROOT/VERSION")"

EXPECTED_SIGNER_SHA256="${ANDROID_EXPECTED_SIGNER_SHA256:-}"
read_dotenv_value() {
  local requested_key="$1"
  if [ ! -f "$ROOT/.env" ]; then
    return
  fi
  python3 -c '
import pathlib, sys
value = ""
for raw_line in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, candidate = line.split("=", 1)
        if key.strip() == sys.argv[2]:
            value = candidate.strip().strip("\"\x27")
print(value)
' "$ROOT/.env" "$requested_key"
}

if [ -z "$EXPECTED_SIGNER_SHA256" ]; then
  EXPECTED_SIGNER_SHA256="$(read_dotenv_value ANDROID_EXPECTED_SIGNER_SHA256)"
fi
AAB_TRUSTSTORE_PATH="${ANDROID_KEYSTORE_PATH:-$(read_dotenv_value ANDROID_KEYSTORE_PATH)}"
AAB_TRUSTSTORE_PASSWORD="${ANDROID_KEYSTORE_PASSWORD:-$(read_dotenv_value ANDROID_KEYSTORE_PASSWORD)}"
CURRENT_KEY_ALIAS="${ANDROID_KEY_ALIAS:-$(read_dotenv_value ANDROID_KEY_ALIAS)}"
CURRENT_KEY_PASSWORD="${ANDROID_KEY_PASSWORD:-$(read_dotenv_value ANDROID_KEY_PASSWORD)}"
SIGNING_LINEAGE_PATH="${ANDROID_SIGNING_LINEAGE_PATH:-$(read_dotenv_value ANDROID_SIGNING_LINEAGE_PATH)}"
PREVIOUS_KEYSTORE_PATH="${ANDROID_PREVIOUS_KEYSTORE_PATH:-$(read_dotenv_value ANDROID_PREVIOUS_KEYSTORE_PATH)}"
PREVIOUS_KEYSTORE_PASSWORD="${ANDROID_PREVIOUS_KEYSTORE_PASSWORD:-$(read_dotenv_value ANDROID_PREVIOUS_KEYSTORE_PASSWORD)}"
PREVIOUS_KEY_ALIAS="${ANDROID_PREVIOUS_KEY_ALIAS:-$(read_dotenv_value ANDROID_PREVIOUS_KEY_ALIAS)}"
PREVIOUS_KEY_PASSWORD="${ANDROID_PREVIOUS_KEY_PASSWORD:-$(read_dotenv_value ANDROID_PREVIOUS_KEY_PASSWORD)}"
SIGNING_ROTATION_MIN_SDK="${ANDROID_SIGNING_ROTATION_MIN_SDK:-$(read_dotenv_value ANDROID_SIGNING_ROTATION_MIN_SDK)}"
SIGNING_ROTATION_MIN_SDK="${SIGNING_ROTATION_MIN_SDK:-28}"

resolve_root_relative_path() {
  local configured_path="$1"
  if [ -n "$configured_path" ] && [[ "$configured_path" != /* ]]; then
    printf '%s/%s\n' "$ROOT" "$configured_path"
  else
    printf '%s\n' "$configured_path"
  fi
}

AAB_TRUSTSTORE_PATH="$(resolve_root_relative_path "$AAB_TRUSTSTORE_PATH")"
SIGNING_LINEAGE_PATH="$(resolve_root_relative_path "$SIGNING_LINEAGE_PATH")"
PREVIOUS_KEYSTORE_PATH="$(resolve_root_relative_path "$PREVIOUS_KEYSTORE_PATH")"

atomic_copy() {
  local source_path="$1"
  local target_path="$2"
  local staged_path
  staged_path="$(mktemp "${target_path}.tmp.XXXXXX")"
  if ! cp "$source_path" "$staged_path"; then
    unlink -- "$staged_path" 2>/dev/null || true
    return 1
  fi
  chmod 0644 "$staged_path"
  mv -f "$staged_path" "$target_path"
}

case "$BUILD_MODE" in
  debug)
    JAVA_HOME="$JAVA_HOME" ANDROID_HOME="$ANDROID_HOME" ./gradlew --no-daemon :app:assembleDebug
    OUTPUT_APK="$ROOT/dist/HikeJournal-v${VERSION_NAME}-debug.apk"
    atomic_copy "$ANDROID_BUILD_DIR/app/outputs/apk/debug/app-debug.apk" "$OUTPUT_APK"
    python3 "$ARTIFACT_VERIFIER" "$OUTPUT_APK" --mode development
    echo
    echo "Built development APK: $OUTPUT_APK"
    echo "The explicit -debug filename prevents this personal build from replacing a signed release;"
    echo "the verifier output above is the authoritative artifact classification."
    ;;
  personal)
    JAVA_HOME="$JAVA_HOME" ANDROID_HOME="$ANDROID_HOME" ./gradlew --no-daemon \
      :app:assembleRelease :app:bundleRelease
    APK_METADATA="$ANDROID_BUILD_DIR/app/outputs/apk/release/output-metadata.json"
    RELEASE_APK_NAME="$(sed -n 's/.*"outputFile": "\([^"]*\.apk\)".*/\1/p' "$APK_METADATA" | head -1)"
    RELEASE_APK="$ANDROID_BUILD_DIR/app/outputs/apk/release/$RELEASE_APK_NAME"
    RELEASE_AAB="$ANDROID_BUILD_DIR/app/outputs/bundle/release/app-release.aab"
    if [ ! -f "$RELEASE_APK" ] || [ ! -f "$RELEASE_AAB" ]; then
      echo "The Android release build completed without the expected APK/AAB outputs."
      exit 1
    fi
    if [[ "$RELEASE_APK_NAME" != *-unsigned.apk ]]; then
      if [ -z "$EXPECTED_SIGNER_SHA256" ]; then
        echo "ANDROID_EXPECTED_SIGNER_SHA256 is required before a signed personal release can be promoted."
        exit 1
      fi
      if ! AAB_SIGNATURE_OUTPUT="$(LC_ALL=C \
        HIKEJOURNAL_AAB_STORE_PASSWORD="$AAB_TRUSTSTORE_PASSWORD" \
        "$JAVA_HOME/bin/jarsigner" -verify -strict -verbose -certs \
        -keystore "$AAB_TRUSTSTORE_PATH" \
        -storepass:env HIKEJOURNAL_AAB_STORE_PASSWORD \
        "$RELEASE_AAB" 2>&1)"; then
        echo "The release AAB did not pass strict JAR signature verification."
        exit 1
      fi
      if [[ "$AAB_SIGNATURE_OUTPUT" != *"jar verified."* ]]; then
        echo "The release AAB did not pass JAR signature verification."
        exit 1
      fi
      AAB_CERTIFICATE_OUTPUT="$(LC_ALL=C "$JAVA_HOME/bin/keytool" -printcert -jarfile "$RELEASE_AAB" 2>&1)"
      AAB_SIGNER_SHA256="$(printf '%s\n' "$AAB_CERTIFICATE_OUTPUT" | sed -n 's/^[[:space:]]*SHA256:[[:space:]]*//p' | head -1)"
      EXPECTED_SIGNER_NORMALIZED="$(PYTHONPATH="$ROOT" python3 -c \
        'import sys; from scripts.verify_android_artifact import normalize_signer_sha256; print(normalize_signer_sha256(sys.argv[1]) or "")' \
        "$EXPECTED_SIGNER_SHA256")"
      AAB_SIGNER_NORMALIZED="$(PYTHONPATH="$ROOT" python3 -c \
        'import sys; from scripts.verify_android_artifact import normalize_signer_sha256; print(normalize_signer_sha256(sys.argv[1]) or "")' \
        "$AAB_SIGNER_SHA256")"
      if [ -z "$EXPECTED_SIGNER_NORMALIZED" ] || [ "$AAB_SIGNER_NORMALIZED" != "$EXPECTED_SIGNER_NORMALIZED" ]; then
        echo "The release AAB signer does not match ANDROID_EXPECTED_SIGNER_SHA256."
        exit 1
      fi
      PROMOTION_DIR="$(mktemp -d "$ROOT/dist/.hikejournal-release.XXXXXX")"
      STAGED_APK="$PROMOTION_DIR/HikeJournal-v${VERSION_NAME}.apk"
      STAGED_AAB="$PROMOTION_DIR/HikeJournal-v${VERSION_NAME}.aab"
      STAGED_APK_IDSIG="$STAGED_APK.idsig"
      cleanup_promotion_artifacts() {
        unlink -- "$STAGED_APK" 2>/dev/null || true
        unlink -- "$STAGED_APK_IDSIG" 2>/dev/null || true
        unlink -- "$STAGED_AAB" 2>/dev/null || true
        rmdir -- "$PROMOTION_DIR" 2>/dev/null || true
      }
      trap cleanup_promotion_artifacts EXIT
      if [ -n "$SIGNING_LINEAGE_PATH" ]; then
        if [ ! -f "$SIGNING_LINEAGE_PATH" ] || [ ! -f "$PREVIOUS_KEYSTORE_PATH" ]; then
          echo "Android signing rotation requires existing lineage and previous-keystore files."
          exit 1
        fi
        if [ -z "$PREVIOUS_KEYSTORE_PASSWORD" ] || [ -z "$PREVIOUS_KEY_ALIAS" ] || \
          [ -z "$PREVIOUS_KEY_PASSWORD" ] || [ -z "$CURRENT_KEY_ALIAS" ] || \
          [ -z "$CURRENT_KEY_PASSWORD" ]; then
          echo "Android signing rotation configuration is incomplete."
          exit 1
        fi
        if ! [[ "$SIGNING_ROTATION_MIN_SDK" =~ ^[0-9]+$ ]] || [ "$SIGNING_ROTATION_MIN_SDK" -lt 28 ]; then
          echo "ANDROID_SIGNING_ROTATION_MIN_SDK must be an integer of at least 28."
          exit 1
        fi
        APK_SIGNER="$(find "$ANDROID_HOME/build-tools" -type f -name apksigner | sort -V | tail -1)"
        if [ ! -x "$APK_SIGNER" ]; then
          echo "apksigner is required to apply the configured Android signing lineage."
          exit 1
        fi
        HIKEJOURNAL_PREVIOUS_STORE_PASSWORD="$PREVIOUS_KEYSTORE_PASSWORD" \
        HIKEJOURNAL_PREVIOUS_KEY_PASSWORD="$PREVIOUS_KEY_PASSWORD" \
        HIKEJOURNAL_CURRENT_STORE_PASSWORD="$AAB_TRUSTSTORE_PASSWORD" \
        HIKEJOURNAL_CURRENT_KEY_PASSWORD="$CURRENT_KEY_PASSWORD" \
        "$APK_SIGNER" sign \
          --in "$RELEASE_APK" \
          --out "$STAGED_APK" \
          --lineage "$SIGNING_LINEAGE_PATH" \
          --rotation-min-sdk-version "$SIGNING_ROTATION_MIN_SDK" \
          --v4-signing-enabled false \
          --ks "$PREVIOUS_KEYSTORE_PATH" \
          --ks-key-alias "$PREVIOUS_KEY_ALIAS" \
          --ks-pass env:HIKEJOURNAL_PREVIOUS_STORE_PASSWORD \
          --key-pass env:HIKEJOURNAL_PREVIOUS_KEY_PASSWORD \
          --next-signer \
          --ks "$AAB_TRUSTSTORE_PATH" \
          --ks-key-alias "$CURRENT_KEY_ALIAS" \
          --ks-pass env:HIKEJOURNAL_CURRENT_STORE_PASSWORD \
          --key-pass env:HIKEJOURNAL_CURRENT_KEY_PASSWORD
      else
        cp "$RELEASE_APK" "$STAGED_APK"
      fi
      cp "$RELEASE_AAB" "$STAGED_AAB"
      chmod 0644 "$STAGED_APK" "$STAGED_AAB"
      if ! python3 "$ARTIFACT_VERIFIER" \
        "$STAGED_APK" \
        --mode release \
        --expected-signer-sha256 "$EXPECTED_SIGNER_SHA256"; then
        exit 1
      fi
      OUTPUT_APK="$ROOT/dist/HikeJournal-v${VERSION_NAME}.apk"
      OUTPUT_AAB="$ROOT/dist/HikeJournal-v${VERSION_NAME}.aab"
      mv -f "$STAGED_AAB" "$OUTPUT_AAB"
      mv -f "$STAGED_APK" "$OUTPUT_APK"
      rmdir -- "$PROMOTION_DIR"
      trap - EXIT
      echo
      echo "Built signed personal release:"
      echo "  $OUTPUT_APK"
      echo "  $OUTPUT_AAB"
      echo "The APK and AAB passed signature identity checks before promotion."
    else
      OUTPUT_APK="$ROOT/dist/HikeJournal-v${VERSION_NAME}-unsigned.apk"
      OUTPUT_AAB="$ROOT/dist/HikeJournal-v${VERSION_NAME}-unsigned.aab"
      atomic_copy "$RELEASE_APK" "$OUTPUT_APK"
      atomic_copy "$RELEASE_AAB" "$OUTPUT_AAB"
      echo
      echo "Built unsigned release artifacts for verification:"
      echo "  $OUTPUT_APK"
      echo "  $OUTPUT_AAB"
      echo "Configure the Android keystore values to create an installable personal release."
      if [ -f "$ROOT/dist/HikeJournal-v${VERSION_NAME}.apk" ]; then
        echo "An existing canonical APK was intentionally left untouched; it may be a development build."
      fi
    fi
    ;;
  *)
    echo "Usage: ./build_android.command [debug|personal]"
    exit 2
    ;;
esac
