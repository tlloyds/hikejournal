#!/bin/bash
set -euo pipefail

script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ios_directory="$(cd "${script_directory}/.." && pwd)"
repository_directory="$(cd "${ios_directory}/.." && pwd)"
canonical_version="$(/usr/bin/tr -d '[:space:]' < "${repository_directory}/VERSION")"
configuration_file="${ios_directory}/Config/Version.xcconfig"

if [[ ! "${canonical_version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "VERSION must contain a semantic version such as 1.2.3" >&2
  exit 1
fi

if [[ "${1:-}" == "--check" ]]; then
  MARKETING_VERSION="${canonical_version}" "${script_directory}/validate_version.sh"
  exit 0
fi

temporary_file="$(/usr/bin/mktemp "${TMPDIR:-/tmp}/hikejournal-version.XXXXXX")"
trap '/bin/rm -f "${temporary_file}"' EXIT
/usr/bin/printf '%s\n%s\n' '// Generated from ../VERSION by Scripts/sync_version.sh.' "MARKETING_VERSION = ${canonical_version}" > "${temporary_file}"

if ! /usr/bin/cmp -s "${temporary_file}" "${configuration_file}"; then
  /bin/cp "${temporary_file}" "${configuration_file}"
  echo "Updated ${configuration_file} to ${canonical_version}."
else
  echo "${configuration_file} is already ${canonical_version}."
fi
