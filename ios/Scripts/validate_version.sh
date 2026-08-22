#!/bin/bash
set -euo pipefail

script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ios_directory="$(cd "${script_directory}/.." && pwd)"
repository_directory="$(cd "${ios_directory}/.." && pwd)"
canonical_version="$(/usr/bin/tr -d '[:space:]' < "${repository_directory}/VERSION")"

if [[ ! "${canonical_version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "error: VERSION must contain a semantic version such as 1.2.3" >&2
  exit 1
fi

configured_version="${MARKETING_VERSION:-}"
if [[ -z "${configured_version}" ]]; then
  configured_version="$(/usr/bin/sed -n 's/^[[:space:]]*MARKETING_VERSION[[:space:]]*=[[:space:]]*//p' "${ios_directory}/Config/Version.xcconfig" | /usr/bin/tr -d '[:space:]')"
fi

if [[ "${configured_version}" != "${canonical_version}" ]]; then
  echo "error: iOS MARKETING_VERSION ${configured_version:-<unset>} does not match root VERSION ${canonical_version}. Run ios/Scripts/sync_version.sh." >&2
  exit 1
fi

echo "HikeJournal version ${canonical_version} matches root VERSION."
