#!/bin/bash
set -euo pipefail

ios_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
developer_directory="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
derived_data_directory="${HIKEJOURNAL_DERIVED_DATA_PATH:-${TMPDIR:-/tmp}/HikeJournalDerivedData}"
destination="${HIKEJOURNAL_DESTINATION:-platform=iOS Simulator,name=iPhone 17 Pro}"

if [[ ! -x "${developer_directory}/usr/bin/xcodebuild" ]]; then
  echo "Full Xcode was not found at ${developer_directory}. Set DEVELOPER_DIR explicitly." >&2
  exit 1
fi

export DEVELOPER_DIR="${developer_directory}"
"${ios_directory}/Scripts/sync_version.sh" --check

common_arguments=(
  -project "${ios_directory}/HikeJournal.xcodeproj"
  -scheme HikeJournal
  -configuration Debug
  -destination "${destination}"
  -derivedDataPath "${derived_data_directory}"
)

echo "Building with DEVELOPER_DIR=${DEVELOPER_DIR}"
echo "DerivedData: ${derived_data_directory}"
"${DEVELOPER_DIR}/usr/bin/xcodebuild" "${common_arguments[@]}" build
"${DEVELOPER_DIR}/usr/bin/xcodebuild" "${common_arguments[@]}" test
