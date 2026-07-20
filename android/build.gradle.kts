plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
    id("com.google.devtools.ksp") version "2.0.21-1.0.28" apply false
}

// The repository lives in iCloud Drive. Keep large, disposable Android build
// outputs in a local cache so iCloud cannot create "file 2.dex" conflict copies.
val hikeJournalBuildRoot = providers.environmentVariable("HIKEJOURNAL_ANDROID_BUILD_DIR")
    .orElse("${System.getProperty("user.home")}/.cache/hikejournal-android-build")

subprojects {
    layout.buildDirectory.set(file("${hikeJournalBuildRoot.get()}/${project.name}"))
}
