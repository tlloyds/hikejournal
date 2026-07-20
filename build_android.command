#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ANDROID_DIR="$ROOT/android"
JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@17}"
ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ANDROID_BUILD_DIR="${HIKEJOURNAL_ANDROID_BUILD_DIR:-$HOME/.cache/hikejournal-android-build}"

if [ ! -x "$JAVA_HOME/bin/java" ]; then
  echo "HikeJournal needs JDK 17. Install it with: brew install openjdk@17"
  exit 1
fi

if [ ! -f "$ROOT/.env" ]; then
  echo "The root .env file is required to pair this build with the companion API."
  exit 1
fi

cd "$ANDROID_DIR"
JAVA_HOME="$JAVA_HOME" ANDROID_HOME="$ANDROID_HOME" ./gradlew --no-daemon :app:assembleDebug

mkdir -p "$ROOT/dist"
cp "$ANDROID_BUILD_DIR/app/outputs/apk/debug/app-debug.apk" "$ROOT/dist/HikeJournal.apk"

echo
echo "Built: $ROOT/dist/HikeJournal.apk"
