package com.hikejournal.app.data

import android.content.Context
import android.content.SharedPreferences

/** Versioned independently of app releases so material notice changes require a new acknowledgment. */
internal class IdentificationSafetyPreferences(
    private val preferences: SharedPreferences,
    private val requiredNoticeVersion: Int = NoticeVersion,
) {
    constructor(context: Context) : this(
        context.applicationContext.getSharedPreferences("hikejournal_identification_safety", Context.MODE_PRIVATE),
    )

    val hasAcknowledged: Boolean get() = preferences.getInt("acknowledged_notice_version", 0) >= requiredNoticeVersion

    fun acknowledge() {
        preferences.edit().putInt("acknowledged_notice_version", requiredNoticeVersion).apply()
    }

    companion object {
        const val NoticeVersion = 1
    }
}
