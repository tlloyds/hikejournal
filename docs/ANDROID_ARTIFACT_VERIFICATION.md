# Android artifact verification

Use the standalone verifier before treating an APK as a HikeJournal release:

```bash
python3 scripts/verify_android_artifact.py \
  dist/HikeJournal-v<VERSION>.apk \
  --mode release \
  --expected-signer-sha256 "$ANDROID_EXPECTED_SIGNER_SHA256"
```

Release mode exits nonzero when the artifact is unsafe or when the installed
Android SDK tools cannot provide essential package, signing, or ZIP-alignment
evidence. It checks:

- filename and `versionName` against the repository `VERSION`;
- package ID and base application label;
- manifest debuggability and cleartext network policy;
- valid non-debug signing with a modern APK signature scheme;
- signing-certificate identity against the public SHA-256 digest supplied for
  the permanent signer;
- compiled LAN, placeholder, development, and cleartext runtime hosts;
- nonempty `MOBILE_API_TOKEN` BuildConfig values and high-confidence pairing
  credential patterns, without printing the credential;
- configured secret values supplied through `MOBILE_API_TOKEN`,
  `HIKEJOURNAL_PAIRING_KEY`, or additional `--secret-env NAME` variables;
- required 64-bit native ABIs; and
- 16 KB ZIP and 64-bit native ELF LOAD-segment alignment.

The verifier discovers the newest available `aapt2`, `apksigner`, `zipalign`,
and `dexdump` under `ANDROID_HOME`, `ANDROID_SDK_ROOT`, the standard macOS SDK
location, or the standard Linux SDK location. An explicit SDK can be selected
with `--sdk-root PATH`.

MapLibre's native library contains a dormant demo-host string even when the app
provides its required release style. The scanner ignores that exact host only
when every occurrence is confined to `libmaplibre.so`; any occurrence in app
DEX/resources still fails release verification.

To inspect a personal debug build without presenting it as release-safe, use:

```bash
python3 scripts/verify_android_artifact.py dist/HikeJournal-v<VERSION>-debug.apk --mode development
```

Development mode reports release-policy problems as warnings and ends with
`not a release certification`. An unreadable, corrupt, or invalidly signed APK
still fails. The report prints only hostnames and credential classifications;
it never prints discovered secret values or full embedded URLs.

Release mode fails closed when the expected signer pin is absent or modern
v2/v3 signature evidence is unavailable. The personal build also runs strict
JAR verification on the AAB and compares its certificate digest to the same
pin before atomically promoting each staged artifact.

Useful overrides include `--expected-package`, `--expected-label`, repeatable
`--required-abi`, repeatable `--forbidden-host`, repeatable `--secret-env`, and
`--expected-signer-sha256`. Run `--help` for the complete interface.

The verifier is an APK inspection gate, not proof of a complete release. Track A
also requires a protected permanent signing key, an approved debug-to-release
data transition, Play-generated artifact checks where applicable,
install/upgrade and device smoke tests, and archived release evidence. The
personal build command separately verifies the AAB's JAR signature and requires
its certificate digest to match the APK's expected signer before copying either
canonical artifact. A
personal release build also requires an owner-supplied HTTPS
`MOBILE_TRAIL_MAP_STYLE_URL`; the debug MapLibre demo default is not an accepted
production provider. Live satellite views also reference Esri World Imagery,
whose licensing, quota, attribution, privacy, and permitted-use terms require
owner approval even when a trail style is configured. No current personal artifact should be
described as production-signed merely because this command exists.
