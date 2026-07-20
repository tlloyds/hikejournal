import java.security.MessageDigest

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
val mobileApiToken = rootEnvironment["MOBILE_API_TOKEN"]?.takeIf { it.isNotBlank() }
    ?: "${rootEnvironment["SUPABASE_KEY"].orEmpty()}:hikejournal-mobile-local-v1".sha256()
val mobileApiUrl = rootEnvironment["MOBILE_API_URL"]?.takeIf { it.isNotBlank() }
    ?: "http://192.168.0.157:8506"
val mobileWebUrl = rootEnvironment["MOBILE_WEB_URL"]?.takeIf { it.isNotBlank() }
    ?: "http://192.168.0.157:8505"
val satelliteOfflineStyleUrl = rootEnvironment["MOBILE_SATELLITE_OFFLINE_STYLE_URL"].orEmpty()

android {
    namespace = "com.hikejournal.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.hikejournal.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 7
        versionName = "0.5.2"

        buildConfigField("String", "DEFAULT_API_URL", quoted(mobileApiUrl))
        buildConfigField("String", "MOBILE_API_TOKEN", quoted(mobileApiToken))
        buildConfigField("String", "DEFAULT_WEB_URL", quoted(mobileWebUrl))
        buildConfigField("String", "SATELLITE_OFFLINE_STYLE_URL", quoted(satelliteOfflineStyleUrl))
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        val keystorePath = rootEnvironment["ANDROID_KEYSTORE_PATH"]
        if (!keystorePath.isNullOrBlank() && file(keystorePath).exists()) {
            create("production") {
                storeFile = file(keystorePath)
                storePassword = rootEnvironment["ANDROID_KEYSTORE_PASSWORD"]
                keyAlias = rootEnvironment["ANDROID_KEY_ALIAS"]
                keyPassword = rootEnvironment["ANDROID_KEY_PASSWORD"]
            }
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            buildConfigField("String", "MOBILE_API_TOKEN", quoted(""))
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
    implementation("io.coil-kt:coil-compose:2.7.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.maplibre.gl:android-sdk:13.0.2")
    implementation("androidx.room:room-runtime:2.7.2")
    implementation("androidx.room:room-ktx:2.7.2")
    ksp("androidx.room:room-compiler:2.7.2")
    implementation("androidx.work:work-runtime-ktx:2.10.1")
    implementation("androidx.exifinterface:exifinterface:1.4.1")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
