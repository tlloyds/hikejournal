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
if [ -z "$EXPECTED_SIGNER_SHA256" ] && [ -f "$ROOT/.env" ]; then
  EXPECTED_SIGNER_SHA256="$(python3 -c '
import pathlib, sys
value = ""
for raw_line in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, candidate = line.split("=", 1)
        if key.strip() == "ANDROID_EXPECTED_SIGNER_SHA256":
            value = candidate.strip().strip("\"\x27")
print(value)
' "$ROOT/.env")"
fi

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
      if ! AAB_SIGNATURE_OUTPUT="$(LC_ALL=C "$JAVA_HOME/bin/jarsigner" \
        -verify -strict -verbose -certs "$RELEASE_AAB" 2>&1)"; then
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
      cleanup_promotion_artifacts() {
        unlink -- "$STAGED_APK" 2>/dev/null || true
        unlink -- "$STAGED_AAB" 2>/dev/null || true
        rmdir -- "$PROMOTION_DIR" 2>/dev/null || true
      }
      trap cleanup_promotion_artifacts EXIT
      cp "$RELEASE_APK" "$STAGED_APK"
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
