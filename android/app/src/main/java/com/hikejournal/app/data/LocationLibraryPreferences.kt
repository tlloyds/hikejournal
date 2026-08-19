package com.hikejournal.app.data

import android.content.Context
import java.util.Locale

data class UsState(val code: String, val name: String)

val UnitedStates: List<UsState> = listOf(
    UsState("AL", "Alabama"),
    UsState("AK", "Alaska"),
    UsState("AZ", "Arizona"),
    UsState("AR", "Arkansas"),
    UsState("CA", "California"),
    UsState("CO", "Colorado"),
    UsState("CT", "Connecticut"),
    UsState("DE", "Delaware"),
    UsState("FL", "Florida"),
    UsState("GA", "Georgia"),
    UsState("HI", "Hawaii"),
    UsState("ID", "Idaho"),
    UsState("IL", "Illinois"),
    UsState("IN", "Indiana"),
    UsState("IA", "Iowa"),
    UsState("KS", "Kansas"),
    UsState("KY", "Kentucky"),
    UsState("LA", "Louisiana"),
    UsState("ME", "Maine"),
    UsState("MD", "Maryland"),
    UsState("MA", "Massachusetts"),
    UsState("MI", "Michigan"),
    UsState("MN", "Minnesota"),
    UsState("MS", "Mississippi"),
    UsState("MO", "Missouri"),
    UsState("MT", "Montana"),
    UsState("NE", "Nebraska"),
    UsState("NV", "Nevada"),
    UsState("NH", "New Hampshire"),
    UsState("NJ", "New Jersey"),
    UsState("NM", "New Mexico"),
    UsState("NY", "New York"),
    UsState("NC", "North Carolina"),
    UsState("ND", "North Dakota"),
    UsState("OH", "Ohio"),
    UsState("OK", "Oklahoma"),
    UsState("OR", "Oregon"),
    UsState("PA", "Pennsylvania"),
    UsState("RI", "Rhode Island"),
    UsState("SC", "South Carolina"),
    UsState("SD", "South Dakota"),
    UsState("TN", "Tennessee"),
    UsState("TX", "Texas"),
    UsState("UT", "Utah"),
    UsState("VT", "Vermont"),
    UsState("VA", "Virginia"),
    UsState("WA", "Washington"),
    UsState("WV", "West Virginia"),
    UsState("WI", "Wisconsin"),
    UsState("WY", "Wyoming"),
)

fun normalizeUsStateCode(value: String?): String? {
    val normalized = value.orEmpty().trim().uppercase(Locale.US)
    return normalized.takeIf { code -> UnitedStates.any { it.code == code } }
}

fun usStateCodeForName(value: String?): String? {
    val normalized = value.orEmpty().trim()
    return UnitedStates.firstOrNull {
        it.code.equals(normalized, ignoreCase = true) || it.name.equals(normalized, ignoreCase = true)
    }?.code
}

internal class LocationLibraryPreferences(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(
        PreferencesName,
        Context.MODE_PRIVATE,
    )

    fun selectedStateCode(): String? = normalizeUsStateCode(preferences.getString(StateCode, null))

    fun setSelectedStateCode(value: String) {
        val stateCode = requireNotNull(normalizeUsStateCode(value)) { "Use a valid U.S. state code." }
        preferences.edit().putString(StateCode, stateCode).apply()
    }

    private companion object {
        const val PreferencesName = "hikejournal_location_library"
        const val StateCode = "selected_state_code"
    }
}
