import java.io.File
import java.net.URI
import java.security.MessageDigest
import org.gradle.api.GradleException

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}

fun loadRootEnvironment(): Map<String, String> {
    val envFile = rootProject.file("../.env")
    if (!envFile.exists()) return emptyMap()
    return envFile.readLines()
        .mapNotNull { line ->
            val clean = line.trim()
            if (clean.isEmpty() || clean.startsWith("#") || !clean.contains("=")) return@mapNotNull null
            val (key, value) = clean.split("=", limit = 2)
            key.trim() to value.trim().trim('"', '\'')
        }
        .toMap()
}

fun String.sha256(): String = MessageDigest.getInstance("SHA-256")
    .digest(toByteArray())
    .joinToString("") { "%02x".format(it) }

fun quoted(value: String): String = "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""

val rootEnvironment = loadRootEnvironment()
fun configuredValue(name: String): String? = System.getenv(name)
    ?.trim()
    ?.takeIf(String::isNotBlank)
    ?: rootEnvironment[name]?.trim()?.takeIf(String::isNotBlank)

val releaseVersion = rootProject.file("../VERSION").readText().trim()
require(releaseVersion.matches(Regex("\\d+\\.\\d+\\.\\d+"))) {
    "VERSION must contain a semantic version such as 1.2.3"
}
val debugMobileApiToken = configuredValue("MOBILE_API_TOKEN")
    ?: "${configuredValue("SUPABASE_KEY").orEmpty()}:hikejournal-mobile-local-v1".sha256()
val configuredMobileApiUrl = configuredValue("MOBILE_API_URL")
val configuredMobileWebUrl = configuredValue("MOBILE_WEB_URL")
val configuredTrailMapStyleUrl = configuredValue("MOBILE_TRAIL_MAP_STYLE_URL")
val configuredSatelliteOfflineStyleUrl = configuredValue("MOBILE_SATELLITE_OFFLINE_STYLE_URL")
val debugMobileApiUrl = configuredMobileApiUrl ?: "http://192.168.0.157:8506"
val debugMobileWebUrl = configuredMobileWebUrl ?: "http://192.168.0.157:8505"
val debugTrailMapStyleUrl = configuredTrailMapStyleUrl
    ?: "https://demotiles.maplibre.org/style.json"

val signingValues = listOf(
    "ANDROID_KEYSTORE_PATH",
    "ANDROID_KEYSTORE_PASSWORD",
    "ANDROID_KEY_ALIAS",
    "ANDROID_KEY_PASSWORD",
).associateWith(::configuredValue)
val anySigningValueConfigured = signingValues.values.any { !it.isNullOrBlank() }
val allSigningValuesConfigured = signingValues.values.all { !it.isNullOrBlank() }
val configuredKeystore = signingValues.getValue("ANDROID_KEYSTORE_PATH")?.let { path ->
    File(path).let { configured ->
        if (configured.isAbsolute) configured else rootProject.file("..").resolve(configured)
    }
}
val productionSigningAvailable = allSigningValuesConfigured && configuredKeystore?.isFile == true

android {
    namespace = "com.hikejournal.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.hikejournal.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 114
        versionName = releaseVersion

        // Safe defaults ensure a newly added non-debug build type cannot inherit a LAN
        // endpoint or the development pairing credential by accident.
        buildConfigField("String", "DEFAULT_API_URL", quoted(""))
        buildConfigField("String", "MOBILE_API_TOKEN", quoted(""))
        buildConfigField("String", "DEFAULT_WEB_URL", quoted(""))
        buildConfigField("String", "TRAIL_MAP_STYLE_URL", quoted(""))
        buildConfigField("String", "SATELLITE_OFFLINE_STYLE_URL", quoted(""))
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        if (productionSigningAvailable) {
            create("production") {
                storeFile = configuredKeystore
                storePassword = signingValues.getValue("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = signingValues.getValue("ANDROID_KEY_ALIAS")
                keyPassword = signingValues.getValue("ANDROID_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            buildConfigField("String", "DEFAULT_API_URL", quoted(debugMobileApiUrl))
            buildConfigField("String", "MOBILE_API_TOKEN", quoted(debugMobileApiToken))
            buildConfigField("String", "DEFAULT_WEB_URL", quoted(debugMobileWebUrl))
            buildConfigField("String", "TRAIL_MAP_STYLE_URL", quoted(debugTrailMapStyleUrl))
            buildConfigField(
                "String",
                "SATELLITE_OFFLINE_STYLE_URL",
                quoted(configuredSatelliteOfflineStyleUrl.orEmpty()),
            )
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            buildConfigField("String", "DEFAULT_API_URL", quoted(configuredMobileApiUrl.orEmpty()))
            buildConfigField("String", "MOBILE_API_TOKEN", quoted(""))
            buildConfigField("String", "DEFAULT_WEB_URL", quoted(configuredMobileWebUrl.orEmpty()))
            buildConfigField(
                "String",
                "TRAIL_MAP_STYLE_URL",
                quoted(configuredTrailMapStyleUrl.orEmpty()),
            )
            buildConfigField(
                "String",
                "SATELLITE_OFFLINE_STYLE_URL",
                quoted(configuredSatelliteOfflineStyleUrl.orEmpty()),
            )
            signingConfigs.findByName("production")?.let { signingConfig = it }
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging.resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    sourceSets.getByName("androidTest").assets.srcDir("$projectDir/schemas")
}

fun requireReleaseHttpsUrl(name: String, value: String?, required: Boolean) {
    if (value.isNullOrBlank()) {
        if (required) throw GradleException("$name is required for a personal release build.")
        return
    }
    val uri = runCatching { URI(value) }.getOrNull()
    if (
        uri?.scheme?.lowercase() != "https" ||
        uri.host.isNullOrBlank() ||
        uri.userInfo != null ||
        uri.rawQuery != null ||
        uri.rawFragment != null
    ) {
        throw GradleException(
            "$name must be an absolute HTTPS base URL without credentials, a query, or a fragment.",
        )
    }
}

val validatePersonalReleaseConfiguration = tasks.register("validatePersonalReleaseConfiguration") {
    group = "verification"
    description = "Rejects unsafe or incomplete configuration before building a personal release."
    doLast {
        requireReleaseHttpsUrl("MOBILE_API_URL", configuredMobileApiUrl, required = true)
        requireReleaseHttpsUrl("MOBILE_WEB_URL", configuredMobileWebUrl, required = false)
        requireReleaseHttpsUrl(
            "MOBILE_TRAIL_MAP_STYLE_URL",
            configuredTrailMapStyleUrl,
            required = true,
        )
        requireReleaseHttpsUrl(
            "MOBILE_SATELLITE_OFFLINE_STYLE_URL",
            configuredSatelliteOfflineStyleUrl,
            required = false,
        )
        if (anySigningValueConfigured && !allSigningValuesConfigured) {
            throw GradleException(
                "Set all four Android signing values, or leave all four unset to build unsigned artifacts.",
            )
        }
        if (allSigningValuesConfigured && configuredKeystore?.isFile != true) {
            throw GradleException("ANDROID_KEYSTORE_PATH must point to an existing keystore file.")
        }
    }
}

tasks.matching { it.name == "preReleaseBuild" }.configureEach {
    dependsOn(validatePersonalReleaseConfiguration)
}

ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("io.coil-kt:coil-compose:2.7.0")
    implementation("io.coil-kt:coil-video:2.7.0")
    implementation("androidx.media3:media3-exoplayer:1.5.1")
    implementation("androidx.media3:media3-ui:1.5.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.maplibre.gl:android-sdk:13.0.2")
    implementation("androidx.room:room-runtime:2.7.2")
    implementation("androidx.room:room-ktx:2.7.2")
    ksp("androidx.room:room-compiler:2.7.2")
    implementation("androidx.work:work-runtime-ktx:2.10.1")
    implementation("androidx.exifinterface:exifinterface:1.4.1")
    implementation("com.google.android.gms:play-services-location:21.3.0")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
    androidTestImplementation("androidx.room:room-testing:2.7.2")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
