package com.hikejournal.app.data

import android.content.Context

internal class GettingStartedPreferences(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(
        PreferencesName,
        Context.MODE_PRIVATE,
    )

    fun hasSeen(accountKey: String): Boolean = preferences.getBoolean(keyFor(accountKey), false)

    fun markSeen(accountKey: String) {
        preferences.edit().putBoolean(keyFor(accountKey), true).apply()
    }

    private fun keyFor(accountKey: String): String = "$SeenPrefix$accountKey"

    private companion object {
        const val PreferencesName = "hikejournal_getting_started"
        const val SeenPrefix = "seen_v1_"
    }
}
