package com.hikejournal.app.data

import android.content.Context
import androidx.core.content.edit
import org.json.JSONArray
import org.json.JSONObject

internal val SuggestedRiverGauges = listOf(
    RiverGauge(
        siteId = "USGS-02233484",
        name = "Econlockhatchee River near Oviedo",
        latitude = 28.6555528489969,
        longitude = -81.1697860660693,
        suggested = true,
    ),
    RiverGauge(
        siteId = "USGS-02233500",
        name = "Econlockhatchee River near Chuluota",
        latitude = 28.6777777777778,
        longitude = -81.1141666666667,
        suggested = true,
    ),
    RiverGauge(
        siteId = "USGS-02234000",
        name = "St. Johns River above Lake Harney near Geneva",
        latitude = 28.7141611118814,
        longitude = -81.0353374335776,
        suggested = true,
    ),
)

internal fun normalizeUsgsSiteId(value: String): String? {
    val clean = value.trim()
    val locationToken = Regex(
        pattern = "monitoring-location/(USGS-[A-Za-z0-9-]+)",
        option = RegexOption.IGNORE_CASE,
    ).find(clean)?.groupValues?.getOrNull(1)
    val normalized = (locationToken ?: clean)
        .substringBefore('?')
        .substringBefore('#')
        .uppercase()
        .let { if (it.startsWith("USGS-")) it else "USGS-$it" }
    val number = normalized.removePrefix("USGS-")
    return normalized.takeIf { number.matches(Regex("[A-Z0-9-]{5,20}")) }
}

internal class RiverGaugePreferences(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(
        PreferencesName,
        Context.MODE_PRIVATE,
    )

    fun gauges(): List<RiverGauge> {
        val enabled = preferences.getStringSet(EnabledGaugeIdsKey, emptySet()).orEmpty()
        val custom = runCatching {
            val array = JSONArray(preferences.getString(CustomGaugesKey, "[]"))
            List(array.length()) { index ->
                val item = array.getJSONObject(index)
                RiverGauge(
                    siteId = item.getString("site_id"),
                    name = item.getString("name"),
                    latitude = item.getDouble("latitude"),
                    longitude = item.getDouble("longitude"),
                )
            }
        }.getOrDefault(emptyList())
        return (SuggestedRiverGauges + custom)
            .distinctBy(RiverGauge::siteId)
            .map { it.copy(enabled = it.siteId in enabled) }
    }

    fun setEnabled(siteId: String, enabled: Boolean) {
        val current = preferences.getStringSet(EnabledGaugeIdsKey, emptySet()).orEmpty().toMutableSet()
        if (enabled) current += siteId else current -= siteId
        preferences.edit { putStringSet(EnabledGaugeIdsKey, current) }
    }

    fun addCustom(gauge: RiverGauge) {
        val existing = gauges().filterNot(RiverGauge::suggested)
        val updated = (existing.filterNot { it.siteId == gauge.siteId } + gauge.copy(suggested = false))
            .sortedBy { it.name.lowercase() }
        val payload = JSONArray()
        updated.forEach { item ->
            payload.put(
                JSONObject()
                    .put("site_id", item.siteId)
                    .put("name", item.name)
                    .put("latitude", item.latitude)
                    .put("longitude", item.longitude),
            )
        }
        preferences.edit { putString(CustomGaugesKey, payload.toString()) }
        setEnabled(gauge.siteId, true)
    }

    fun removeCustom(siteId: String) {
        val custom = gauges().filterNot(RiverGauge::suggested).filterNot { it.siteId == siteId }
        val payload = JSONArray()
        custom.forEach { item ->
            payload.put(
                JSONObject()
                    .put("site_id", item.siteId)
                    .put("name", item.name)
                    .put("latitude", item.latitude)
                    .put("longitude", item.longitude),
            )
        }
        preferences.edit { putString(CustomGaugesKey, payload.toString()) }
        setEnabled(siteId, false)
    }

    private companion object {
        const val PreferencesName = "hikejournal_river_gauges"
        const val EnabledGaugeIdsKey = "enabled_gauge_ids"
        const val CustomGaugesKey = "custom_gauges_json"
    }
}
