#!/usr/bin/env python3
"""Verify that a HikeJournal APK is safe to treat as a release artifact.

The verifier deliberately reports only non-sensitive classifications. It never
prints compiled credential values or full URLs discovered inside an APK.
"""

from __future__ import annotations

import argparse
import ipaddress
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence
from urllib.parse import urlsplit


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE = "com.hikejournal.app"
DEFAULT_LABEL = "HikeJournal"
DEFAULT_DEVELOPMENT_HOSTS = frozenset(
    {
        "demotiles.maplibre.org",
        "localhost",
        "10.0.2.2",
        "10.0.3.2",
        "example.com",
        "example.net",
        "example.org",
    }
)
NON_RUNTIME_HTTP_HOSTS = frozenset(
    {
        "schemas.android.com",
        "www.w3.org",
        "xml.org",
        "xmlpull.org",
        "ns.adobe.com",
        "purl.org",
        "www.apache.org",
        "apache.org",
        "creativecommons.org",
        "g.co",
        "opensource.org",
        "schemas.microsoft.com",
        "scripts.sil.org",
        "www.adobe.com",
        "www.garmin.com",
    }
)
DEFAULT_SECRET_ENV_NAMES = ("MOBILE_API_TOKEN", "HIKEJOURNAL_PAIRING_KEY")
DEFAULT_EXPECTED_SIGNER_SHA256_ENV_NAME = "ANDROID_EXPECTED_SIGNER_SHA256"

ASCII_URL_RE = re.compile(
    rb"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{3,512}", re.IGNORECASE
)
UTF16_PRINTABLE_RE = re.compile(rb"(?:[\x20-\x7e]\x00){8,}")
TOKEN_RE = re.compile(
    rb"(?<![A-Za-z0-9_-])(?:[A-Fa-f0-9]{32,128}|[A-Za-z0-9_-]{40,256})(?![A-Za-z0-9_-])"
)
PAIRING_MARKERS = (b"MOBILE_API_TOKEN", b"X-HikeJournal-Key")


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


CommandRunner = Callable[[Sequence[str]], CommandResult]


@dataclass(frozen=True)
class AndroidTools:
    aapt2: Path | None = None
    apksigner: Path | None = None
    zipalign: Path | None = None
    dexdump: Path | None = None


@dataclass(frozen=True)
class VerificationConfig:
    apk_path: Path
    version_file: Path = REPOSITORY_ROOT / "VERSION"
    mode: str = "release"
    expected_package: str = DEFAULT_PACKAGE
    expected_label: str = DEFAULT_LABEL
    required_abis: tuple[str, ...] = ("arm64-v8a",)
    forbidden_hosts: frozenset[str] = DEFAULT_DEVELOPMENT_HOSTS
    secret_values: tuple[bytes, ...] = field(default=(), repr=False)
    expected_signer_sha256: str | None = None

    @property
    def is_release(self) -> bool:
        return self.mode == "release"


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str


@dataclass
class VerificationReport:
    mode: str
    artifact_name: str
    facts: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return any(finding.severity == "ERROR" for finding in self.findings)

    def add(self, severity: str, code: str, message: str) -> None:
        item = Finding(severity, code, message)
        if item not in self.findings:
            self.findings.append(item)


def subprocess_runner(args: Sequence[str]) -> CommandResult:
    completed = subprocess.run(
        list(args),
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _version_key(path: Path) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", path.name)
    return tuple(int(number) for number in numbers) or (0,)


def discover_android_tools(sdk_root: Path | None = None) -> AndroidTools:
    roots: list[Path] = []
    if sdk_root is not None:
        roots.append(sdk_root.expanduser())
    for env_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(env_name):
            roots.append(Path(os.environ[env_name]).expanduser())
    roots.extend(
        [
            Path.home() / "Library/Android/sdk",
            Path.home() / "Android/Sdk",
        ]
    )

    build_tool_dirs: list[Path] = []
    for root in roots:
        candidate = root / "build-tools"
        if candidate.is_dir():
            build_tool_dirs.extend(path for path in candidate.iterdir() if path.is_dir())
    build_tool_dirs.sort(key=_version_key, reverse=True)

    def locate(name: str) -> Path | None:
        direct = shutil.which(name)
        if direct:
            return Path(direct)
        for directory in build_tool_dirs:
            candidate = directory / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
        return None

    return AndroidTools(
        aapt2=locate("aapt2"),
        apksigner=locate("apksigner"),
        zipalign=locate("zipalign"),
        dexdump=locate("dexdump"),
    )


def parse_badging(output: str) -> dict[str, str]:
    package_line = next(
        (line for line in output.splitlines() if line.startswith("package:")), ""
    )
    metadata = {
        key: value
        for key, value in re.findall(r"(\w+)='([^']*)'", package_line)
    }
    label_match = re.search(r"^application-label:'([^']*)'", output, re.MULTILINE)
    if label_match:
        metadata["applicationLabel"] = label_match.group(1)
    target_match = re.search(r"^targetSdkVersion:'([^']*)'", output, re.MULTILINE)
    if target_match:
        metadata["targetSdkVersion"] = target_match.group(1)
    return metadata


def normalize_signer_sha256(value: str) -> str | None:
    """Normalize common SHA-256 certificate fingerprint representations."""

    candidate = value.strip()
    if not candidate:
        return None
    candidate = re.sub(
        r"^sha-?256(?:\s+fingerprint)?\s*[:=]\s*",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"[\s:-]", "", candidate).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        return None
    return normalized


def signer_sha256_fingerprints(output: str) -> frozenset[str]:
    fingerprints: set[str] = set()
    for line in output.splitlines():
        match = re.search(
            r"Signer\s+#\d+\s+certificate\s+SHA-256\s+digest\s*:\s*(.+?)\s*$",
            line,
            re.IGNORECASE,
        )
        if not match:
            continue
        normalized = normalize_signer_sha256(match.group(1))
        if normalized:
            fingerprints.add(normalized)
    return frozenset(fingerprints)


def _display_fingerprint(value: str) -> str:
    return ":".join(value[index : index + 2] for index in range(0, len(value), 2)).upper()


def manifest_is_debuggable(output: str) -> bool:
    return bool(re.search(r"debuggable[^\n]*=true(?:\s|$)", output, re.IGNORECASE))


def manifest_allows_cleartext(output: str) -> bool:
    return bool(
        re.search(r"usesCleartextTraffic[^\n]*=true(?:\s|$)", output, re.IGNORECASE)
        or re.search(
            r"cleartextTrafficPermitted[^\n]*=true(?:\s|$)", output, re.IGNORECASE
        )
    )


def manifest_references_network_security_config(output: str) -> bool:
    return "networkSecurityConfig" in output


def resource_file_path(output: str, resource_name: str) -> str | None:
    match = re.search(
        rf"resource\s+0x[0-9a-f]+\s+{re.escape(resource_name)}\s+.*?\(file\)\s+(\S+)",
        output,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(1) if match else None


def build_config_has_pairing_credential(output: str, package_name: str) -> bool:
    descriptor = f"L{package_name.replace('.', '/')}/BuildConfig;"
    start = output.find(f"Class descriptor  : '{descriptor}'")
    if start < 0:
        return False
    end = output.find("\nClass #", start + 1)
    block = output[start : end if end >= 0 else None]
    match = re.search(
        r"name\s*:\s*'MOBILE_API_TOKEN'.*?value\s*:\s*\"([^\"]*)\"",
        block,
        re.DOTALL,
    )
    return bool(match and match.group(1).strip())


def _printable_strings(data: bytes) -> Iterable[bytes]:
    yield from re.findall(rb"[\x20-\x7e]{8,}", data)
    for match in UTF16_PRINTABLE_RE.finditer(data):
        yield match.group(0)[::2]


def extract_url_hosts(data: bytes) -> set[tuple[str, str]]:
    discovered: set[tuple[str, str]] = set()
    for printable in _printable_strings(data):
        for match in ASCII_URL_RE.finditer(printable):
            try:
                parsed = urlsplit(match.group(0).decode("ascii", errors="ignore"))
            except ValueError:
                continue
            hostname = (parsed.hostname or "").lower().rstrip(".")
            if hostname:
                discovered.add((parsed.scheme.lower(), hostname))
    return discovered


def classify_host(hostname: str, forbidden_hosts: frozenset[str]) -> str | None:
    lowered = hostname.lower().rstrip(".")
    try:
        address = ipaddress.ip_address(lowered.strip("[]"))
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_unspecified
    ):
        return "local-network-url"
    if lowered == "localhost" or lowered.endswith((".localhost", ".local")):
        return "local-network-url"
    if lowered in forbidden_hosts:
        return "development-host"
    if lowered.endswith((".test", ".invalid", ".example")):
        return "development-host"
    if any(lowered.endswith(f".{host}") for host in ("example.com", "example.net", "example.org")):
        return "development-host"
    return None


def _entropy(value: bytes) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    size = len(value)
    return -sum((count / size) * math.log2(count / size) for count in counts.values())


def has_pairing_credential_heuristic(data: bytes) -> bool:
    marker_positions = [
        match.start()
        for marker in PAIRING_MARKERS
        for match in re.finditer(re.escape(marker), data)
    ]
    if not marker_positions:
        return False
    for candidate in TOKEN_RE.finditer(data):
        value = candidate.group(0)
        if len(set(value)) < 10 or _entropy(value) < 3.25:
            continue
        if any(abs(candidate.start() - marker) <= 4096 for marker in marker_positions):
            return True
    return False


def elf_load_segments_are_16k_aligned(data: bytes) -> bool | None:
    if len(data) < 64 or data[:4] != b"\x7fELF":
        return None
    elf_class = data[4]
    byte_order = data[5]
    if elf_class not in (1, 2) or byte_order not in (1, 2):
        return None
    endian = "<" if byte_order == 1 else ">"
    try:
        if elf_class == 1:
            phoff = struct.unpack_from(endian + "I", data, 28)[0]
            phentsize, phnum = struct.unpack_from(endian + "HH", data, 42)
            expected_size = 32
        else:
            phoff = struct.unpack_from(endian + "Q", data, 32)[0]
            phentsize, phnum = struct.unpack_from(endian + "HH", data, 54)
            expected_size = 56
        if phentsize < expected_size or phnum == 0:
            return None
        load_segments = 0
        for index in range(phnum):
            offset = phoff + index * phentsize
            if offset + expected_size > len(data):
                return None
            p_type = struct.unpack_from(endian + "I", data, offset)[0]
            if p_type != 1:  # PT_LOAD
                continue
            load_segments += 1
            if elf_class == 1:
                p_offset = struct.unpack_from(endian + "I", data, offset + 4)[0]
                p_vaddr = struct.unpack_from(endian + "I", data, offset + 8)[0]
                p_align = struct.unpack_from(endian + "I", data, offset + 28)[0]
            else:
                p_offset = struct.unpack_from(endian + "Q", data, offset + 8)[0]
                p_vaddr = struct.unpack_from(endian + "Q", data, offset + 16)[0]
                p_align = struct.unpack_from(endian + "Q", data, offset + 48)[0]
            if p_align < 0x4000 or (p_vaddr - p_offset) % 0x4000 != 0:
                return False
        return True if load_segments else None
    except (IndexError, struct.error):
        return None


def _policy_severity(config: VerificationConfig) -> str:
    return "ERROR" if config.is_release else "WARN"


def _run_tool(
    path: Path,
    arguments: Sequence[str],
    runner: CommandRunner,
) -> CommandResult:
    return runner([str(path), *arguments])


def verify_apk(
    config: VerificationConfig,
    tools: AndroidTools,
    runner: CommandRunner = subprocess_runner,
) -> VerificationReport:
    report = VerificationReport(config.mode, config.apk_path.name)
    policy = _policy_severity(config)
    configured_signer = (config.expected_signer_sha256 or "").strip()
    expected_signer = (
        normalize_signer_sha256(configured_signer) if configured_signer else None
    )
    if config.is_release and not configured_signer:
        report.add(
            "ERROR",
            "signer-fingerprint-required",
            "Release verification requires the expected permanent signer SHA-256 fingerprint.",
        )
    if configured_signer and expected_signer is None:
        report.add(
            policy,
            "signer-fingerprint-invalid",
            "Configured signer SHA-256 fingerprint is not a valid 32-byte hexadecimal digest.",
        )

    if not config.apk_path.is_file():
        report.add("ERROR", "artifact-missing", "APK path does not identify a file.")
        return report
    try:
        canonical_version = config.version_file.read_text(encoding="utf-8").strip()
    except OSError:
        report.add("ERROR", "version-file-unreadable", "Canonical VERSION could not be read.")
        return report
    report.facts["canonical version"] = canonical_version

    expected_name = f"HikeJournal-v{canonical_version}.apk"
    accepted_names = {expected_name}
    if not config.is_release:
        accepted_names.add(f"HikeJournal-v{canonical_version}-debug.apk")
    if config.apk_path.name not in accepted_names:
        report.add(
            policy,
            "artifact-name-mismatch",
            f"APK filename must be {expected_name} for canonical release versioning.",
        )

    try:
        archive = zipfile.ZipFile(config.apk_path)
        bad_entry = archive.testzip()
    except (OSError, zipfile.BadZipFile):
        report.add("ERROR", "invalid-apk", "Artifact is not a readable ZIP/APK archive.")
        return report
    if bad_entry is not None:
        archive.close()
        report.add("ERROR", "corrupt-apk", "APK contains a corrupt archive entry.")
        return report

    names = archive.namelist()
    entry_data: dict[str, bytes] = {}
    native_entries: list[str] = []
    url_sources: dict[tuple[str, str], set[str]] = {}
    exact_secret_found = False
    heuristic_secret_found = False
    for name in names:
        try:
            data = archive.read(name)
        except (KeyError, RuntimeError, zipfile.BadZipFile):
            archive.close()
            report.add("ERROR", "corrupt-apk", "APK entry could not be inspected.")
            return report
        if name.endswith(".so") and name.startswith("lib/"):
            native_entries.append(name)
            entry_data[name] = data
        if name.endswith(".dex"):
            entry_data[name] = data
            if has_pairing_credential_heuristic(data):
                heuristic_secret_found = True
        for discovered_url in extract_url_hosts(data):
            url_sources.setdefault(discovered_url, set()).add(name)
        if any(secret and secret in data for secret in config.secret_values):
            exact_secret_found = True
    archive.close()

    metadata: dict[str, str] = {}
    manifest_dump = ""
    if tools.aapt2 is None:
        report.add(policy, "aapt2-unavailable", "aapt2 is required to inspect APK metadata and manifest policy.")
    else:
        badging = _run_tool(tools.aapt2, ["dump", "badging", str(config.apk_path)], runner)
        if badging.returncode != 0:
            report.add(policy, "badging-unavailable", "aapt2 could not read APK package metadata.")
        else:
            metadata = parse_badging(badging.stdout)
            for source, label in (
                ("name", "package"),
                ("versionName", "version name"),
                ("versionCode", "version code"),
                ("applicationLabel", "application label"),
                ("targetSdkVersion", "target SDK"),
            ):
                if metadata.get(source):
                    report.facts[label] = metadata[source]
            if metadata.get("name") != config.expected_package:
                report.add(
                    policy,
                    "package-mismatch",
                    f"Package must be {config.expected_package}.",
                )
            if metadata.get("versionName") != canonical_version:
                report.add(
                    policy,
                    "version-mismatch",
                    "APK versionName does not match canonical VERSION.",
                )
            if metadata.get("applicationLabel") != config.expected_label:
                report.add(
                    policy,
                    "application-label-mismatch",
                    f"Base application label must be {config.expected_label}.",
                )

        manifest = _run_tool(
            tools.aapt2,
            ["dump", "xmltree", str(config.apk_path), "--file", "AndroidManifest.xml"],
            runner,
        )
        if manifest.returncode != 0:
            report.add(policy, "manifest-unavailable", "aapt2 could not inspect AndroidManifest.xml.")
        else:
            manifest_dump = manifest.stdout
            if manifest_is_debuggable(manifest_dump):
                report.add(policy, "debuggable", "Application is compiled as debuggable.")
            if manifest_allows_cleartext(manifest_dump):
                report.add(policy, "cleartext-policy", "Manifest permits cleartext production traffic.")

            if manifest_references_network_security_config(manifest_dump):
                config_names = [
                    name
                    for name in names
                    if name.startswith("res/xml/") and "network_security_config" in name
                ]
                if not config_names:
                    resources = _run_tool(
                        tools.aapt2,
                        ["dump", "resources", str(config.apk_path)],
                        runner,
                    )
                    resolved = (
                        resource_file_path(resources.stdout, "xml/network_security_config")
                        if resources.returncode == 0
                        else None
                    )
                    if resolved and resolved in names:
                        config_names = [resolved]
                if not config_names:
                    report.add(
                        policy,
                        "cleartext-policy-uninspected",
                        "Referenced network security configuration could not be located in the APK.",
                    )
                else:
                    for resource_name in config_names:
                        network = _run_tool(
                            tools.aapt2,
                            [
                                "dump",
                                "xmltree",
                                str(config.apk_path),
                                "--file",
                                resource_name,
                            ],
                            runner,
                        )
                        if network.returncode != 0:
                            report.add(
                                policy,
                                "cleartext-policy-uninspected",
                                "Network security configuration could not be decoded.",
                            )
                        elif manifest_allows_cleartext(network.stdout):
                            report.add(
                                policy,
                                "cleartext-policy",
                                "Network security configuration permits cleartext production traffic.",
                            )

    if tools.apksigner is None:
        report.add(policy, "apksigner-unavailable", "apksigner is required to inspect APK signing.")
        if expected_signer:
            report.add(
                policy,
                "signer-fingerprint-unavailable",
                "Configured signer identity could not be verified because signer certificate evidence is unavailable.",
            )
    else:
        signing = _run_tool(
            tools.apksigner,
            ["verify", "--verbose", "--print-certs", str(config.apk_path)],
            runner,
        )
        signing_output = f"{signing.stdout}\n{signing.stderr}"
        if signing.returncode != 0:
            report.add("ERROR", "invalid-signature", "APK signature verification failed.")
            if expected_signer:
                report.add(
                    policy,
                    "signer-fingerprint-unavailable",
                    "Configured signer identity could not be verified from a valid APK signature.",
                )
        else:
            signer_count = re.search(r"Number of signers:\s*(\d+)", signing_output)
            if signer_count:
                report.facts["signers"] = signer_count.group(1)
            signer_fingerprints = signer_sha256_fingerprints(signing_output)
            if signer_fingerprints:
                report.facts["signer SHA-256"] = ", ".join(
                    _display_fingerprint(value) for value in sorted(signer_fingerprints)
                )
            if expected_signer:
                if not signer_fingerprints:
                    report.add(
                        policy,
                        "signer-fingerprint-unavailable",
                        "Configured signer identity could not be verified because the certificate SHA-256 digest is unavailable.",
                    )
                elif signer_fingerprints != {expected_signer}:
                    report.add(
                        policy,
                        "signer-fingerprint-mismatch",
                        "APK signer certificate identity does not match the configured SHA-256 fingerprint.",
                    )
            if re.search(r"CN\s*=\s*Android Debug|Android Debug", signing_output, re.IGNORECASE):
                report.add(policy, "debug-signing", "APK is signed with an Android debug certificate.")
            scheme_results = re.findall(
                r"Verified using v(?:2|3|3\.1) scheme[^:]*:\s*(true|false)",
                signing_output,
                re.IGNORECASE,
            )
            if not scheme_results or not any(
                value.lower() == "true" for value in scheme_results
            ):
                report.add(
                    policy,
                    "legacy-signature-only",
                    "APK lacks affirmative evidence of a verified modern APK signature scheme.",
                )

    if tools.zipalign is None:
        report.add(policy, "zipalign-unavailable", "zipalign is required to verify 16 KB APK alignment.")
    else:
        alignment = _run_tool(
            tools.zipalign,
            ["-c", "-P", "16", "-v", "4", str(config.apk_path)],
            runner,
        )
        if alignment.returncode != 0:
            report.add(policy, "zip-page-alignment", "APK does not pass zipalign 16 KB verification.")

    abis = sorted({name.split("/", 2)[1] for name in native_entries})
    report.facts["native ABIs"] = ", ".join(abis) if abis else "none"
    if native_entries:
        for required_abi in config.required_abis:
            if required_abi not in abis:
                report.add(policy, "missing-64-bit-abi", f"Required 64-bit ABI is missing: {required_abi}.")
        for thirty_two, sixty_four in (("armeabi-v7a", "arm64-v8a"), ("x86", "x86_64")):
            if thirty_two in abis and sixty_four not in abis:
                report.add(
                    policy,
                    "missing-64-bit-abi",
                    f"APK includes {thirty_two} native code without its {sixty_four} counterpart.",
                )

        misaligned = 0
        unreadable = 0
        alignment_entries = [
            name
            for name in native_entries
            if name.split("/", 2)[1] in {"arm64-v8a", "x86_64"}
        ]
        for name in alignment_entries:
            aligned = elf_load_segments_are_16k_aligned(entry_data[name])
            if aligned is False:
                misaligned += 1
            elif aligned is None:
                unreadable += 1
        if misaligned:
            report.add(
                policy,
                "elf-page-alignment",
                f"{misaligned} native library/libraries have LOAD segments incompatible with 16 KB pages.",
            )
        if unreadable:
            report.add(
                policy,
                "elf-uninspected",
                f"{unreadable} native library/libraries could not be parsed for 16 KB alignment.",
            )

    classified_hosts: dict[str, set[str]] = {}
    cleartext_hosts: set[str] = set()
    for (scheme, hostname), sources in url_sources.items():
        # MapLibre's native SDK ships an unreachable demo URL constant even
        # when the app supplies its own release style. Ignore only that exact
        # dependency-only occurrence; the same host in DEX/resources remains a
        # release error and the required release BuildConfig is checked by the
        # Gradle gate.
        dependency_only_maplibre_demo = hostname == "demotiles.maplibre.org" and all(
            source.startswith("lib/") and source.endswith("/libmaplibre.so")
            for source in sources
        )
        if dependency_only_maplibre_demo:
            continue
        category = classify_host(hostname, config.forbidden_hosts)
        if category:
            classified_hosts.setdefault(category, set()).add(hostname)
        if scheme == "http" and hostname not in NON_RUNTIME_HTTP_HOSTS:
            cleartext_hosts.add(hostname)
    for code, hosts in sorted(classified_hosts.items()):
        report.add(
            policy,
            code,
            f"Compiled artifact references prohibited host(s): {', '.join(sorted(hosts))}.",
        )
    if cleartext_hosts:
        report.add(
            policy,
            "compiled-cleartext-url",
            f"Compiled artifact contains cleartext runtime URL host(s): {', '.join(sorted(cleartext_hosts))}.",
        )

    build_config_secret = False
    if tools.dexdump is not None:
        for name, data in entry_data.items():
            if not name.endswith(".dex") or b"BuildConfig" not in data:
                continue
            import tempfile

            with tempfile.TemporaryDirectory(prefix="hikejournal-apk-") as directory:
                dex_path = Path(directory) / Path(name).name
                dex_path.write_bytes(data)
                dumped = _run_tool(tools.dexdump, ["-d", str(dex_path)], runner)
                if dumped.returncode == 0 and build_config_has_pairing_credential(
                    dumped.stdout, metadata.get("name", config.expected_package)
                ):
                    build_config_secret = True
                    break
    if build_config_secret or exact_secret_found or heuristic_secret_found:
        report.add(
            policy,
            "embedded-pairing-credential",
            "APK contains an apparent configured pairing credential; value is intentionally redacted.",
        )

    return report


def format_report(report: VerificationReport) -> str:
    lines = [
        "HikeJournal APK artifact verification",
        f"Mode: {report.mode}",
        f"Artifact: {report.artifact_name}",
    ]
    for name, value in report.facts.items():
        lines.append(f"{name.capitalize()}: {value}")
    if report.findings:
        lines.append("Findings:")
        for finding in sorted(report.findings, key=lambda item: (item.severity != "ERROR", item.code)):
            lines.append(f"  {finding.severity} [{finding.code}] {finding.message}")
    else:
        lines.append("Findings: none")
    if report.failed:
        lines.append("Result: FAIL")
    elif report.mode == "development":
        lines.append("Result: DEVELOPMENT CHARACTERIZATION COMPLETE (not a release certification)")
    else:
        lines.append("Result: PASS")
    return "\n".join(lines)


def _secret_values_from_environment(names: Iterable[str]) -> tuple[bytes, ...]:
    values: list[bytes] = []
    for name in names:
        value = os.environ.get(name, "")
        if len(value) >= 8:
            values.append(value.encode("utf-8"))
    return tuple(values)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path, help="APK artifact to inspect")
    parser.add_argument(
        "--mode",
        choices=("release", "development"),
        default="release",
        help="release fails unsafe/incomplete checks; development characterizes them",
    )
    parser.add_argument("--version-file", type=Path, default=REPOSITORY_ROOT / "VERSION")
    parser.add_argument("--expected-package", default=DEFAULT_PACKAGE)
    parser.add_argument("--expected-label", default=DEFAULT_LABEL)
    parser.add_argument(
        "--expected-signer-sha256",
        default=os.environ.get(DEFAULT_EXPECTED_SIGNER_SHA256_ENV_NAME),
        help=(
            "expected APK signer certificate SHA-256 fingerprint "
            f"(default: ${DEFAULT_EXPECTED_SIGNER_SHA256_ENV_NAME}, when set)"
        ),
    )
    parser.add_argument("--sdk-root", type=Path)
    parser.add_argument(
        "--required-abi",
        action="append",
        dest="required_abis",
        help="required native ABI; repeat as needed (default: arm64-v8a)",
    )
    parser.add_argument(
        "--forbidden-host",
        action="append",
        default=[],
        help="additional compiled development/placeholder host to reject",
    )
    parser.add_argument(
        "--secret-env",
        action="append",
        default=[],
        help="additional environment variable whose value must not be embedded",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    secret_names = (*DEFAULT_SECRET_ENV_NAMES, *args.secret_env)
    config = VerificationConfig(
        apk_path=args.apk.resolve(),
        version_file=args.version_file.resolve(),
        mode=args.mode,
        expected_package=args.expected_package,
        expected_label=args.expected_label,
        expected_signer_sha256=args.expected_signer_sha256,
        required_abis=tuple(args.required_abis or ("arm64-v8a",)),
        forbidden_hosts=frozenset(
            {*DEFAULT_DEVELOPMENT_HOSTS, *(host.lower() for host in args.forbidden_host)}
        ),
        secret_values=_secret_values_from_environment(secret_names),
    )
    report = verify_apk(config, discover_android_tools(args.sdk_root))
    print(format_report(report))
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
