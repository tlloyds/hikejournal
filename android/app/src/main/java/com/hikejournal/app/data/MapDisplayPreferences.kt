package com.hikejournal.app.data

import android.content.Context
import androidx.core.content.edit

internal const val FLORIDA_TRAIL_ID = "florida"

internal data class TrailOverlayDefinition(
    val id: String,
    val name: String,
    val shortName: String,
    val states: String,
    val layerUrls: List<String>,
    val featured: Boolean = false,
    val objectIdField: String = "OBJECTID",
)

internal val NationalScenicTrailOverlays = listOf(
    TrailOverlayDefinition(
        id = "appalachian",
        name = "Appalachian Trail",
        shortName = "AT",
        states = "Georgia to Maine",
        featured = true,
        layerUrls = listOf("https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Centerline/FeatureServer/0"),
    ),
    TrailOverlayDefinition(
        id = "pacific-crest",
        name = "Pacific Crest Trail",
        shortName = "PCT",
        states = "California · Oregon · Washington",
        featured = true,
        layerUrls = listOf("https://services5.arcgis.com/ZldHa25efPFpMmfB/arcgis/rest/services/PCTA_Centerline/FeatureServer/0"),
    ),
    TrailOverlayDefinition(
        id = "continental-divide",
        name = "Continental Divide Trail",
        shortName = "CDT",
        states = "New Mexico to Montana",
        featured = true,
        layerUrls = listOf("https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/Continental_Divide_NST_view/FeatureServer/0"),
    ),
    TrailOverlayDefinition(
        id = FLORIDA_TRAIL_ID,
        name = "Florida Trail",
        shortName = "FT",
        states = "Florida",
        objectIdField = "FID",
        layerUrls = listOf("https://services9.arcgis.com/soy9dtLUh5hYXg8U/arcgis/rest/services/FNST%20Master/FeatureServer/0"),
    ),
    TrailOverlayDefinition(
        id = "arizona",
        name = "Arizona Trail",
        shortName = "AZT",
        states = "Arizona",
        layerUrls = listOf("https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/Arizona_National_Scenic_Trail_Feature_Layers_view/FeatureServer/3"),
    ),
    TrailOverlayDefinition(
        id = "ice-age",
        name = "Ice Age Trail",
        shortName = "IAT",
        states = "Wisconsin",
        layerUrls = listOf("https://services.arcgis.com/EeCmkqXss9GYEKIZ/arcgis/rest/services/IAT_Segments_CR/FeatureServer/0"),
    ),
    TrailOverlayDefinition(
        id = "natchez-trace",
        name = "Natchez Trace Trail",
        shortName = "NATT",
        states = "Alabama · Mississippi · Tennessee",
        layerUrls = listOf("https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NATT_TRANS_NSTTrail/FeatureServer/0"),
    ),
    TrailOverlayDefinition(
        id = "new-england",
        name = "New England Trail",
        shortName = "NET",
        states = "Connecticut · Massachusetts",
        objectIdField = "FID",
        layerUrls = listOf("https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/NEEN_BND_NationalScenicTrailCenterline_ln/FeatureServer/0"),
    ),
    TrailOverlayDefinition(
        id = "north-country",
        name = "North Country Trail",
        shortName = "NCT",
        states = "North Dakota to Vermont",
        layerUrls = listOf(
            "https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/nct_public/FeatureServer/2",
            "https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/agol_sht_public/FeatureServer/1",
        ),
    ),
    TrailOverlayDefinition(
        id = "pacific-northwest",
        name = "Pacific Northwest Trail",
        shortName = "PNT",
        states = "Montana · Idaho · Washington",
        objectIdField = "FID",
        layerUrls = listOf("https://services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/Pacific_Northwest_National_Scenic_Trail/FeatureServer/0"),
    ),
    TrailOverlayDefinition(
        id = "potomac-heritage",
        name = "Potomac Heritage Trail",
        shortName = "PHT",
        states = "Virginia · DC · Maryland · Pennsylvania",
        layerUrls = listOf("https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/POHE_Trail_Centerline_FTDS_view/FeatureServer/0"),
    ),
)

internal class MapDisplayPreferences(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(
        PreferencesName,
        Context.MODE_PRIVATE,
    )

    fun selectedTrailIds(): Set<String> {
        if (preferences.contains(SelectedTrailIdsKey)) {
            return preferences.getStringSet(SelectedTrailIdsKey, emptySet()).orEmpty()
                .intersect(NationalScenicTrailOverlays.map(TrailOverlayDefinition::id).toSet())
        }
        val legacyFloridaEnabled = preferences.getBoolean(ShowFloridaTrailKey, true)
        return if (legacyFloridaEnabled) setOf(FLORIDA_TRAIL_ID) else emptySet()
    }

    fun setTrailSelected(trailId: String, selected: Boolean) {
        if (NationalScenicTrailOverlays.none { it.id == trailId }) return
        val updated = selectedTrailIds().toMutableSet()
        if (selected) updated += trailId else updated -= trailId
        preferences.edit {
            putStringSet(SelectedTrailIdsKey, updated)
            putBoolean(ShowFloridaTrailKey, FLORIDA_TRAIL_ID in updated)
        }
    }

    private companion object {
        const val PreferencesName = "hikejournal_map_display"
        const val SelectedTrailIdsKey = "selected_national_scenic_trails"
        const val ShowFloridaTrailKey = "show_florida_trail"
    }
}
