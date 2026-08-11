package com.hikejournal.app.data

import android.content.Context

internal const val DEFAULT_SHOW_FLORIDA_TRAIL = true

internal class MapDisplayPreferences(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(
        PreferencesName,
        Context.MODE_PRIVATE,
    )

    fun showFloridaTrail(): Boolean = preferences.getBoolean(
        ShowFloridaTrailKey,
        DEFAULT_SHOW_FLORIDA_TRAIL,
    )

    fun setShowFloridaTrail(show: Boolean) {
        preferences.edit().putBoolean(ShowFloridaTrailKey, show).apply()
    }

    private companion object {
        const val PreferencesName = "hikejournal_map_display"
        const val ShowFloridaTrailKey = "show_florida_trail"
    }
}
