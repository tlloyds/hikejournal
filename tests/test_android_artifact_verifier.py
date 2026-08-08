import struct
import zipfile
from pathlib import Path

from scripts.verify_android_artifact import (
    AndroidTools,
    CommandResult,
    VerificationConfig,
    build_argument_parser,
    build_config_has_pairing_credential,
    classify_host,
    elf_load_segments_are_16k_aligned,
    format_report,
    normalize_signer_sha256,
    parse_badging,
    resource_file_path,
    verify_apk,
)


SAFE_BADGING = """\
package: name='com.hikejournal.app' versionCode='89' versionName='0.6.28'
targetSdkVersion:'36'
application-label:'HikeJournal'
"""
SAFE_MANIFEST = """\
E: manifest
  A: package="com.hikejournal.app"
  E: application
    A: android:networkSecurityConfig=@0x7f120000
"""
SAFE_NETWORK = """\
E: network-security-config
  E: base-config
    A: cleartextTrafficPermitted=false
"""
RELEASE_SIGNER_SHA256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
RELEASE_SIGNING = """\
Verifies
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Number of signers: 1
Signer #1 certificate DN: CN=HikeJournal Release, O=HikeJournal
Signer #1 certificate SHA-256 digest: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
"""


def _elf64(alignment: int = 0x4000) -> bytes:
    data = bytearray(128)
    data[:4] = b"\x7fELF"
    data[4:6] = b"\x02\x01"
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<HH", data, 54, 56, 1)
    struct.pack_into("<I", data, 64, 1)
    struct.pack_into("<Q", data, 72, 0)
    struct.pack_into("<Q", data, 80, 0)
    struct.pack_into("<Q", data, 112, alignment)
    return bytes(data)


class FixtureRunner:
    def __init__(
        self,
        *,
        badging: str = SAFE_BADGING,
        manifest: str = SAFE_MANIFEST,
        network: str = SAFE_NETWORK,
        resources: str = "",
        signing: str = RELEASE_SIGNING,
        zipalign_code: int = 0,
        dexdump: str = "",
    ) -> None:
        self.badging = badging
        self.manifest = manifest
        self.network = network
        self.resources = resources
        self.signing = signing
        self.zipalign_code = zipalign_code
        self.dexdump = dexdump

    def __call__(self, args: list[str]) -> CommandResult:
        tool = Path(args[0]).name
        if tool == "aapt2" and args[1:3] == ["dump", "badging"]:
            return CommandResult(0, self.badging)
        if tool == "aapt2" and args[1:3] == ["dump", "xmltree"]:
            return CommandResult(0, self.manifest if args[-1] == "AndroidManifest.xml" else self.network)
        if tool == "aapt2" and args[1:3] == ["dump", "resources"]:
            return CommandResult(0, self.resources)
        if tool == "apksigner":
            return CommandResult(0, self.signing)
        if tool == "zipalign":
            return CommandResult(self.zipalign_code)
        if tool == "dexdump":
            return CommandResult(0, self.dexdump)
        raise AssertionError(f"Unexpected fixture command: {args}")


TOOLS = AndroidTools(
    aapt2=Path("/sdk/aapt2"),
    apksigner=Path("/sdk/apksigner"),
    zipalign=Path("/sdk/zipalign"),
    dexdump=Path("/sdk/dexdump"),
)


def _artifact(
    tmp_path: Path,
    *,
    filename: str = "HikeJournal-v0.6.28.apk",
    entries: dict[str, bytes | None] | None = None,
) -> tuple[Path, Path]:
    apk = tmp_path / filename
    version = tmp_path / "VERSION"
    version.write_text("0.6.28\n", encoding="utf-8")
    contents = {
        "AndroidManifest.xml": b"compiled",
        "res/xml/network_security_config.xml": b"compiled",
        "classes.dex": b"dex without application constants",
        "lib/arm64-v8a/libfixture.so": _elf64(),
    }
    for name, data in (entries or {}).items():
        if data is None:
            contents.pop(name, None)
        else:
            contents[name] = data
    with zipfile.ZipFile(apk, "w") as archive:
        for name, data in contents.items():
            archive.writestr(name, data)
    return apk, version


def _codes(report) -> set[str]:
    return {finding.code for finding in report.findings}


def test_parses_badging_without_depending_on_a_real_apk() -> None:
    assert parse_badging(SAFE_BADGING) == {
        "name": "com.hikejournal.app",
        "versionCode": "89",
        "versionName": "0.6.28",
        "applicationLabel": "HikeJournal",
        "targetSdkVersion": "36",
    }


def test_resolves_shrunk_network_security_resource_path() -> None:
    dump = """resource 0x7f120000 xml/network_security_config
      () (file) res/8G.xml type=XML
    """
    assert resource_file_path(dump, "xml/network_security_config") == "res/8G.xml"


def test_normalizes_common_signer_fingerprint_formats() -> None:
    colon_delimited = ":".join(
        RELEASE_SIGNER_SHA256[index : index + 2]
        for index in range(0, len(RELEASE_SIGNER_SHA256), 2)
    ).upper()
    assert normalize_signer_sha256(colon_delimited) == RELEASE_SIGNER_SHA256
    assert (
        normalize_signer_sha256(f"SHA-256 fingerprint: {colon_delimited}")
        == RELEASE_SIGNER_SHA256
    )
    assert normalize_signer_sha256("not-a-fingerprint") is None


def test_signer_fingerprint_cli_uses_environment_and_allows_override(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ANDROID_EXPECTED_SIGNER_SHA256", RELEASE_SIGNER_SHA256.upper())
    from_environment = build_argument_parser().parse_args(["artifact.apk"])
    explicit = build_argument_parser().parse_args(
        ["artifact.apk", "--expected-signer-sha256", "f" * 64]
    )
    assert from_environment.expected_signer_sha256 == RELEASE_SIGNER_SHA256.upper()
    assert explicit.expected_signer_sha256 == "f" * 64


def test_detects_only_nonempty_build_config_pairing_token() -> None:
    prefix = "Class descriptor  : 'Lcom/hikejournal/app/BuildConfig;'\nStatic fields -\n"
    assert not build_config_has_pairing_credential(
        prefix + "name : 'MOBILE_API_TOKEN'\nvalue : \"\"\n", "com.hikejournal.app"
    )
    assert build_config_has_pairing_credential(
        prefix + "name : 'MOBILE_API_TOKEN'\nvalue : \"do-not-print-this-secret\"\n",
        "com.hikejournal.app",
    )


def test_classifies_private_and_placeholder_hosts() -> None:
    forbidden = frozenset({"demotiles.maplibre.org"})
    assert classify_host("192.168.1.22", forbidden) == "local-network-url"
    assert classify_host("service.local", forbidden) == "local-network-url"
    assert classify_host("demotiles.maplibre.org", forbidden) == "development-host"
    assert classify_host("api.example.com", forbidden) == "development-host"
    assert classify_host("api.hikejournal.example", forbidden) == "development-host"
    assert classify_host("api.hikejournal.com", forbidden) is None


def test_checks_elf_load_segment_alignment_with_stdlib_fixture() -> None:
    assert elf_load_segments_are_16k_aligned(_elf64(0x4000)) is True
    assert elf_load_segments_are_16k_aligned(_elf64(0x1000)) is False
    assert elf_load_segments_are_16k_aligned(b"not an elf") is None


def test_safe_release_fixture_passes(tmp_path: Path) -> None:
    apk, version = _artifact(tmp_path)
    report = verify_apk(
        VerificationConfig(
            apk_path=apk,
            version_file=version,
            expected_signer_sha256=RELEASE_SIGNER_SHA256,
        ),
        TOOLS,
        FixtureRunner(),
    )
    assert not report.failed
    assert not report.findings
    assert report.facts["package"] == "com.hikejournal.app"
    assert report.facts["native ABIs"] == "arm64-v8a"
    assert format_report(report).endswith("Result: PASS")


def test_release_accepts_configured_signer_fingerprint_in_common_format(
    tmp_path: Path,
) -> None:
    apk, version = _artifact(tmp_path)
    formatted = "SHA-256: " + ":".join(
        RELEASE_SIGNER_SHA256[index : index + 2]
        for index in range(0, len(RELEASE_SIGNER_SHA256), 2)
    ).upper()
    report = verify_apk(
        VerificationConfig(
            apk_path=apk,
            version_file=version,
            expected_signer_sha256=formatted,
        ),
        TOOLS,
        FixtureRunner(),
    )

    assert not report.failed
    assert "signer-fingerprint-mismatch" not in _codes(report)
    assert "signer-fingerprint-unavailable" not in _codes(report)


def test_release_rejects_mismatched_configured_signer_fingerprint(
    tmp_path: Path,
) -> None:
    apk, version = _artifact(tmp_path)
    report = verify_apk(
        VerificationConfig(
            apk_path=apk,
            version_file=version,
            expected_signer_sha256="f" * 64,
        ),
        TOOLS,
        FixtureRunner(),
    )

    assert report.failed
    assert "signer-fingerprint-mismatch" in _codes(report)


def test_release_rejects_unavailable_configured_signer_fingerprint(
    tmp_path: Path,
) -> None:
    apk, version = _artifact(tmp_path)
    report = verify_apk(
        VerificationConfig(
            apk_path=apk,
            version_file=version,
            expected_signer_sha256=RELEASE_SIGNER_SHA256,
        ),
        TOOLS,
        FixtureRunner(signing=RELEASE_SIGNING.replace(
            f"Signer #1 certificate SHA-256 digest: {RELEASE_SIGNER_SHA256}\n", ""
        )),
    )

    assert report.failed
    assert "signer-fingerprint-unavailable" in _codes(report)


def test_release_inspects_a_shrunk_network_security_resource(tmp_path: Path) -> None:
    apk, version = _artifact(
        tmp_path,
        entries={
            "res/xml/network_security_config.xml": None,
            "res/8G.xml": b"compiled",
        },
    )
    report = verify_apk(
        VerificationConfig(
            apk_path=apk,
            version_file=version,
            expected_signer_sha256=RELEASE_SIGNER_SHA256,
        ),
        TOOLS,
        FixtureRunner(
            resources="""resource 0x7f120000 xml/network_security_config
              () (file) res/8G.xml type=XML
            """,
        ),
    )

    assert "cleartext-policy-uninspected" not in _codes(report)
    assert not report.failed


def test_release_ignores_only_maplibre_native_demo_constant(tmp_path: Path) -> None:
    apk, version = _artifact(
        tmp_path,
        entries={
            "lib/arm64-v8a/libfixture.so": None,
            "lib/arm64-v8a/libmaplibre.so": (
                _elf64() + b"https://demotiles.maplibre.org/style.json"
            ),
        },
    )
    report = verify_apk(
        VerificationConfig(
            apk_path=apk,
            version_file=version,
            expected_signer_sha256=RELEASE_SIGNER_SHA256,
        ),
        TOOLS,
        FixtureRunner(),
    )

    assert not report.failed
    assert "development-host" not in _codes(report)


def test_release_requires_a_pinned_signer_identity(tmp_path: Path) -> None:
    apk, version = _artifact(tmp_path)

    report = verify_apk(
        VerificationConfig(apk_path=apk, version_file=version),
        TOOLS,
        FixtureRunner(),
    )

    assert report.failed
    assert "signer-fingerprint-required" in _codes(report)


def test_release_requires_affirmative_modern_signature_evidence(tmp_path: Path) -> None:
    apk, version = _artifact(tmp_path)
    report = verify_apk(
        VerificationConfig(
            apk_path=apk,
            version_file=version,
            expected_signer_sha256=RELEASE_SIGNER_SHA256,
        ),
        TOOLS,
        FixtureRunner(
            signing="\n".join(
                line
                for line in RELEASE_SIGNING.splitlines()
                if not line.startswith("Verified using v")
            )
        ),
    )

    assert report.failed
    assert "legacy-signature-only" in _codes(report)


def test_release_rejects_all_primary_artifact_hazards_without_leaking_secret(
    tmp_path: Path,
) -> None:
    secret = b"a9E4_secret_value_that_must_never_appear_in_output_0123456789"
    apk, version = _artifact(
        tmp_path,
        filename="wrong.apk",
        entries={
            "classes.dex": (
                b"BuildConfig MOBILE_API_TOKEN X-HikeJournal-Key "
                + secret
                + b" http://192.168.4.9:8506 https://demotiles.maplibre.org/style.json"
            ),
            "lib/arm64-v8a/libfixture.so": _elf64(0x1000),
        },
    )
    unsafe_badging = SAFE_BADGING.replace("com.hikejournal.app", "org.wrong.app").replace(
        "0.6.28", "9.9.9"
    ).replace("HikeJournal", "Wrong App")
    unsafe_manifest = SAFE_MANIFEST + "\nA: android:debuggable=true\n"
    unsafe_network = "A: cleartextTrafficPermitted=true\n"
    debug_signing = RELEASE_SIGNING.replace(
        "CN=HikeJournal Release, O=HikeJournal", "C=US, O=Android, CN=Android Debug"
    )
    dexdump = """\
Class descriptor  : 'Lcom/hikejournal/app/BuildConfig;'
Static fields -
  name : 'MOBILE_API_TOKEN'
  value : "a9E4_secret_value_that_must_never_appear_in_output_0123456789"
"""
    report = verify_apk(
        VerificationConfig(
            apk_path=apk,
            version_file=version,
            secret_values=(secret,),
        ),
        TOOLS,
        FixtureRunner(
            badging=unsafe_badging,
            manifest=unsafe_manifest,
            network=unsafe_network,
            signing=debug_signing,
            zipalign_code=1,
            dexdump=dexdump,
        ),
    )

    assert report.failed
    assert {
        "artifact-name-mismatch",
        "package-mismatch",
        "version-mismatch",
        "application-label-mismatch",
        "debuggable",
        "debug-signing",
        "cleartext-policy",
        "compiled-cleartext-url",
        "local-network-url",
        "development-host",
        "embedded-pairing-credential",
        "elf-page-alignment",
        "zip-page-alignment",
    } <= _codes(report)
    rendered = format_report(report)
    assert secret.decode() not in rendered
    assert "value_that_must_never" not in rendered


def test_development_mode_characterizes_release_hazards_without_certifying(
    tmp_path: Path,
) -> None:
    apk, version = _artifact(
        tmp_path,
        entries={"classes.dex": b"http://10.0.2.2:8506"},
    )
    report = verify_apk(
        VerificationConfig(apk_path=apk, version_file=version, mode="development"),
        TOOLS,
        FixtureRunner(
            manifest=SAFE_MANIFEST + "\nA: android:debuggable=true\n",
            signing=RELEASE_SIGNING.replace("HikeJournal Release", "Android Debug"),
        ),
    )
    assert not report.failed
    assert {finding.severity for finding in report.findings} == {"WARN"}
    assert "not a release certification" in format_report(report)


def test_release_requires_64_bit_counterpart_for_native_code(tmp_path: Path) -> None:
    apk, version = _artifact(
        tmp_path,
        entries={
            "lib/arm64-v8a/libfixture.so": None,
            "lib/armeabi-v7a/libfixture.so": _elf64(),
        },
    )
    report = verify_apk(
        VerificationConfig(apk_path=apk, version_file=version),
        TOOLS,
        FixtureRunner(),
    )
    assert report.failed
    assert "missing-64-bit-abi" in _codes(report)


def test_release_requires_sdk_evidence_while_development_reports_missing_tools(
    tmp_path: Path,
) -> None:
    apk, version = _artifact(tmp_path)
    release = verify_apk(
        VerificationConfig(apk_path=apk, version_file=version),
        AndroidTools(),
    )
    development = verify_apk(
        VerificationConfig(apk_path=apk, version_file=version, mode="development"),
        AndroidTools(),
    )
    assert release.failed
    assert {"aapt2-unavailable", "apksigner-unavailable", "zipalign-unavailable"} <= _codes(release)
    assert not development.failed
    assert all(finding.severity == "WARN" for finding in development.findings)
