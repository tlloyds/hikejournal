package com.hikejournal.app.data

import com.hikejournal.app.BuildConfig
import java.io.IOException
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.Locale
import java.util.concurrent.TimeUnit
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject

private const val OpenMeteoForecastUrl = "https://api.open-meteo.com/v1/forecast"
private const val UsgsApiRoot = "https://api.waterdata.usgs.gov/ogcapi/v0/collections"
private const val GageHeightParameterCode = "00065"
internal const val NearbyWaterGaugeRadiusMiles = 30.0
internal const val AutomaticWaterGaugeLimit = 3

internal class OutdoorConditionsClient {
    private val client = OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    suspend fun loadForecast(latitude: Double, longitude: Double): PlaceForecast = withContext(Dispatchers.IO) {
        val url = OpenMeteoForecastUrl.toHttpUrl().newBuilder()
            .addQueryParameter("latitude", latitude.toString())
            .addQueryParameter("longitude", longitude.toString())
            .addQueryParameter("timezone", "auto")
            .addQueryParameter("forecast_days", "7")
            .addQueryParameter("temperature_unit", "fahrenheit")
            .addQueryParameter("precipitation_unit", "inch")
            .addQueryParameter("wind_speed_unit", "mph")
            .addQueryParameter(
                "current",
                "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation," +
                    "weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m",
            )
            .addQueryParameter(
                "daily",
                "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max," +
                    "apparent_temperature_min,sunrise,sunset,uv_index_max,precipitation_sum," +
                    "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max",
            )
            .build()
        parsePlaceForecast(request(url.toString(), "Open-Meteo"))
    }

    suspend fun resolveGauge(value: String): RiverGauge = withContext(Dispatchers.IO) {
        val siteId = normalizeUsgsSiteId(value)
            ?: throw IllegalArgumentException("Enter a USGS site number or monitoring-location link.")
        val metadataUrl = "$UsgsApiRoot/monitoring-locations/items".toHttpUrl().newBuilder()
            .addQueryParameter("f", "json")
            .addQueryParameter("id", siteId)
            .addQueryParameter("limit", "1")
            .build()
        val gauge = parseRiverGaugeMetadata(request(metadataUrl.toString(), "USGS"), siteId)
        val latestUrl = "$UsgsApiRoot/latest-continuous/items".toHttpUrl().newBuilder()
            .addQueryParameter("f", "json")
            .addQueryParameter("monitoring_location_id", siteId)
            .addQueryParameter("parameter_code", GageHeightParameterCode)
            .addQueryParameter("limit", "10")
            .build()
        val latest = JSONObject(request(latestUrl.toString(), "USGS"))
            .optJSONArray("features")
        if (latest == null || latest.length() == 0) {
            throw IllegalArgumentException("$siteId does not publish a current water height (USGS parameter 00065).")
        }
        gauge
    }

    suspend fun findNearbyRiverGauges(
        latitude: Double,
        longitude: Double,
        radiusMiles: Double = 30.0,
    ): List<NearbyRiverGauge> = withContext(Dispatchers.IO) {
        val latitudeDelta = radiusMiles / 69.0
        val longitudeScale = cos(Math.toRadians(latitude)).coerceAtLeast(0.2)
        val longitudeDelta = radiusMiles / (69.0 * longitudeScale)
        val bbox = listOf(
            longitude - longitudeDelta,
            latitude - latitudeDelta,
            longitude + longitudeDelta,
            latitude + latitudeDelta,
        ).joinToString(",") { String.format(Locale.US, "%.5f", it) }
        val latestUrl = "$UsgsApiRoot/latest-continuous/items".toHttpUrl().newBuilder()
            .addQueryParameter("f", "json")
            .addQueryParameter("bbox", bbox)
            .addQueryParameter("parameter_code", GageHeightParameterCode)
            .addQueryParameter("limit", "1000")
            .build()
        val metadataUrl = "$UsgsApiRoot/monitoring-locations/items".toHttpUrl().newBuilder()
            .addQueryParameter("f", "json")
            .addQueryParameter("bbox", bbox)
            .addQueryParameter("agency_code", "USGS")
            .addQueryParameter("limit", "10000")
            .addQueryParameter("properties", "id,monitoring_location_name")
            .build()
        parseNearbyRiverGauges(
            latestJson = request(latestUrl.toString(), "USGS"),
            metadataJson = request(metadataUrl.toString(), "USGS"),
            originLatitude = latitude,
            originLongitude = longitude,
            radiusMiles = radiusMiles,
        )
    }

    suspend fun loadRiverGauge(
        gauge: RiverGauge,
        periodDays: Int,
        placeLatitude: Double?,
        placeLongitude: Double?,
    ): RiverGaugeSeries = withContext(Dispatchers.IO) {
        val days = if (periodDays >= 30) 30 else 7
        val startedAt = Instant.now().minus(days.toLong(), ChronoUnit.DAYS).toString()
        val url = "$UsgsApiRoot/continuous/items".toHttpUrl().newBuilder()
            .addQueryParameter("f", "json")
            .addQueryParameter("monitoring_location_id", gauge.siteId)
            .addQueryParameter("parameter_code", GageHeightParameterCode)
            .addQueryParameter("datetime", "$startedAt/..")
            .addQueryParameter("limit", "10000")
            .addQueryParameter(
                "properties",
                "time_series_id,monitoring_location_id,time,value,unit_of_measure,approval_status,qualifier",
            )
            .build()
        parseRiverGaugeSeries(
            json = request(url.toString(), "USGS"),
            gauge = gauge,
            periodDays = days,
            placeLatitude = placeLatitude,
            placeLongitude = placeLongitude,
        )
    }

    private fun request(url: String, provider: String): String {
        val call = Request.Builder()
            .url(url)
            .header("Accept", "application/json")
            .header("User-Agent", "HikeJournal/${BuildConfig.VERSION_NAME}")
            .build()
        try {
            client.newCall(call).execute().use { response ->
                if (!response.isSuccessful) {
                    throw IOException("$provider returned ${response.code}.")
                }
                return response.body?.string()?.takeIf(String::isNotBlank)
                    ?: throw IOException("$provider returned an empty response.")
            }
        } catch (error: IOException) {
            throw IOException("$provider conditions are temporarily unavailable.", error)
        }
    }
}

internal fun parsePlaceForecast(json: String): PlaceForecast {
    val root = JSONObject(json)
    val current = root.optJSONObject("current") ?: JSONObject()
    val daily = root.optJSONObject("daily") ?: JSONObject()
    val dates = daily.optJSONArray("time") ?: JSONArray()
    val days = List(dates.length()) { index ->
        ForecastDay(
            date = dates.optString(index),
            conditionLabel = forecastConditionLabel(daily.arrayNumber("weather_code", index)?.toInt()),
            temperatureMaxF = daily.arrayNumber("temperature_2m_max", index),
            temperatureMinF = daily.arrayNumber("temperature_2m_min", index),
            apparentTemperatureMaxF = daily.arrayNumber("apparent_temperature_max", index),
            precipitationProbabilityPercent = daily.arrayNumber("precipitation_probability_max", index),
            precipitationTotalInches = daily.arrayNumber("precipitation_sum", index),
            windSpeedMaxMph = daily.arrayNumber("wind_speed_10m_max", index),
            windGustMaxMph = daily.arrayNumber("wind_gusts_10m_max", index),
            uvIndexMax = daily.arrayNumber("uv_index_max", index),
            sunrise = daily.arrayString("sunrise", index),
            sunset = daily.arrayString("sunset", index),
        )
    }
    val forecast = PlaceForecast(
        observedAt = current.stringOrNull("time"),
        timezone = root.optString("timezone"),
        temperatureF = current.numberOrNull("temperature_2m"),
        apparentTemperatureF = current.numberOrNull("apparent_temperature"),
        relativeHumidityPercent = current.numberOrNull("relative_humidity_2m"),
        precipitationInches = current.numberOrNull("precipitation"),
        cloudCoverPercent = current.numberOrNull("cloud_cover"),
        windSpeedMph = current.numberOrNull("wind_speed_10m"),
        windGustMph = current.numberOrNull("wind_gusts_10m"),
        conditionLabel = forecastConditionLabel(current.numberOrNull("weather_code")?.toInt()),
        days = days,
        planningNotes = emptyList(),
    )
    return forecast.copy(planningNotes = buildWeatherPlanningNotes(forecast))
}

internal fun parsePlaceConditions(json: String): PlaceConditionsResult {
    val root = JSONObject(json)
    val forecast = root.optJSONObject("forecast")?.let { forecastJson ->
        if (forecastJson.has("current") || forecastJson.has("daily")) {
            parsePlaceForecast(forecastJson.toString())
        } else {
            parseSharedPlaceForecast(forecastJson)
        }
    }
    val riverGauges = root.optJSONArray("river_gauges") ?: JSONArray()
    return PlaceConditionsResult(
        forecast = forecast,
        riverGauges = List(riverGauges.length()) { index ->
            parseServerRiverGaugeSeries(riverGauges.getJSONObject(index))
        },
        liveConditionsNotice = root.stringOrNull("live_conditions_notice"),
    )
}

private fun parseSharedPlaceForecast(json: JSONObject): PlaceForecast {
    val daysJson = json.optJSONArray("days") ?: JSONArray()
    val days = List(daysJson.length()) { index ->
        val day = daysJson.optJSONObject(index) ?: JSONObject()
        ForecastDay(
            date = day.optString("date"),
            conditionLabel = day.optString("condition_label", "Current conditions"),
            temperatureMaxF = day.numberOrNull("temperature_max_f"),
            temperatureMinF = day.numberOrNull("temperature_min_f"),
            apparentTemperatureMaxF = day.numberOrNull("apparent_temperature_max_f"),
            precipitationProbabilityPercent = day.numberOrNull("precipitation_probability_percent"),
            precipitationTotalInches = day.numberOrNull("precipitation_total_inches"),
            windSpeedMaxMph = day.numberOrNull("wind_speed_max_mph"),
            windGustMaxMph = day.numberOrNull("wind_gust_max_mph"),
            uvIndexMax = day.numberOrNull("uv_index_max"),
            sunrise = day.stringOrNull("sunrise"),
            sunset = day.stringOrNull("sunset"),
        )
    }
    val planningNotes = json.optJSONArray("planning_notes")?.let { notes ->
        List(notes.length()) { index -> notes.optString(index).trim() }
            .filter(String::isNotBlank)
    }.orEmpty()
    return PlaceForecast(
        observedAt = json.stringOrNull("observed_at"),
        timezone = json.optString("timezone"),
        temperatureF = json.numberOrNull("temperature_f"),
        apparentTemperatureF = json.numberOrNull("apparent_temperature_f"),
        relativeHumidityPercent = json.numberOrNull("relative_humidity_percent"),
        precipitationInches = json.numberOrNull("precipitation_inches"),
        cloudCoverPercent = json.numberOrNull("cloud_cover_percent"),
        windSpeedMph = json.numberOrNull("wind_speed_mph"),
        windGustMph = json.numberOrNull("wind_gust_mph"),
        conditionLabel = json.optString("condition_label", "Current conditions"),
        days = days,
        planningNotes = planningNotes,
    )
}

private fun parseServerRiverGaugeSeries(item: JSONObject): RiverGaugeSeries {
    val gaugeJSON = item.optJSONObject("gauge") ?: JSONObject()
    val gauge = RiverGauge(
        siteId = gaugeJSON.optString("site_id"),
        name = gaugeJSON.optString("name", "USGS water gauge"),
        latitude = gaugeJSON.numberOrNull("lat") ?: 0.0,
        longitude = gaugeJSON.numberOrNull("lng") ?: 0.0,
        enabled = gaugeJSON.optBoolean("enabled"),
        suggested = gaugeJSON.optBoolean("suggested"),
    )
    val readingsJSON = item.optJSONArray("readings") ?: JSONArray()
    return RiverGaugeSeries(
        gauge = gauge,
        periodDays = item.optInt("period_days", 7),
        readings = List(readingsJSON.length()) { index ->
            val reading = readingsJSON.getJSONObject(index)
            RiverGaugeReading(
                observedAt = reading.optString("observed_at"),
                heightFeet = reading.numberOrNull("height_feet") ?: 0.0,
                provisional = reading.optBoolean("provisional"),
            )
        },
        distanceMiles = item.numberOrNull("distance_miles"),
        errorMessage = item.stringOrNull("error_message"),
    )
}

internal fun buildWeatherPlanningNotes(forecast: PlaceForecast): List<String> {
    val today = forecast.days.firstOrNull()
    val notes = mutableListOf<String>()
    val feelsLike = today?.apparentTemperatureMaxF ?: forecast.apparentTemperatureF
    when {
        feelsLike != null && feelsLike >= 100 -> notes +=
            "Plan a cooler, earlier outing: the peak feels-like temperature is near ${feelsLike.roundToInt()}°F."
        feelsLike != null && feelsLike >= 90 -> notes +=
            "Hot trail conditions are likely; the peak feels-like temperature is near ${feelsLike.roundToInt()}°F."
    }
    val rainChance = today?.precipitationProbabilityPercent
    val rainTotal = today?.precipitationTotalInches
    if ((rainChance ?: 0.0) >= 50 || (rainTotal ?: 0.0) >= 0.25) {
        notes += "Rain may materially change footing and water crossings (${rainChance?.roundToInt() ?: 0}% chance, ${formatForecastDecimal(rainTotal)} in forecast)."
    }
    val gust = today?.windGustMaxMph
    if ((gust ?: 0.0) >= 25) {
        notes += "Gusts near ${gust?.roundToInt()} mph could affect exposed sections and tree cover."
    }
    val uv = today?.uvIndexMax
    if ((uv ?: 0.0) >= 8) {
        notes += "Peak UV is very high near ${formatForecastDecimal(uv)}; plan sun protection and limit exposed midday time."
    }
    if (notes.isEmpty()) {
        notes += "No major heat, rain, wind, or UV signal stands out in today’s forecast."
    }
    return notes.take(3)
}

internal fun parseRiverGaugeMetadata(json: String, expectedSiteId: String): RiverGauge {
    val feature = JSONObject(json).optJSONArray("features")?.optJSONObject(0)
        ?: throw IllegalArgumentException("USGS site $expectedSiteId was not found.")
    val properties = feature.optJSONObject("properties") ?: JSONObject()
    val siteId = properties.optString("id", feature.optString("id")).uppercase()
    if (siteId != expectedSiteId) throw IllegalArgumentException("USGS site $expectedSiteId was not found.")
    val coordinates = feature.optJSONObject("geometry")?.optJSONArray("coordinates")
    val longitude = coordinates?.optDouble(0)?.takeIf(Double::isFinite)
    val latitude = coordinates?.optDouble(1)?.takeIf(Double::isFinite)
    if (latitude == null || longitude == null) {
        throw IllegalArgumentException("USGS site $expectedSiteId has no usable map coordinates.")
    }
    return RiverGauge(
        siteId = siteId,
        name = friendlyUsgsGaugeName(properties.optString("monitoring_location_name", siteId)),
        latitude = latitude,
        longitude = longitude,
    )
}

internal fun parseNearbyRiverGauges(
    latestJson: String,
    metadataJson: String,
    originLatitude: Double,
    originLongitude: Double,
    radiusMiles: Double = 30.0,
    now: Instant = Instant.now(),
): List<NearbyRiverGauge> {
    val names = mutableMapOf<String, String>()
    val metadata = JSONObject(metadataJson).optJSONArray("features") ?: JSONArray()
    for (index in 0 until metadata.length()) {
        val properties = metadata.optJSONObject(index)?.optJSONObject("properties") ?: continue
        val siteId = properties.optString("id").uppercase().takeIf(String::isNotBlank) ?: continue
        names[siteId] = friendlyUsgsGaugeName(properties.optString("monitoring_location_name", siteId))
    }
    val latestBySite = linkedMapOf<String, NearbyRiverGauge>()
    val latest = JSONObject(latestJson).optJSONArray("features") ?: JSONArray()
    for (index in 0 until latest.length()) {
        val feature = latest.optJSONObject(index) ?: continue
        val properties = feature.optJSONObject("properties") ?: continue
        val siteId = properties.optString("monitoring_location_id").uppercase()
            .takeIf { it.startsWith("USGS-") } ?: continue
        val observedAt = properties.stringOrNull("time") ?: continue
        val observedInstant = runCatching { Instant.parse(observedAt) }.getOrNull() ?: continue
        if (observedInstant.isBefore(now.minus(7, ChronoUnit.DAYS)) || observedInstant.isAfter(now.plus(1, ChronoUnit.DAYS))) {
            continue
        }
        val height = properties.numberOrNull("value") ?: continue
        if (!properties.optString("unit_of_measure").equals("ft", ignoreCase = true)) continue
        val coordinates = feature.optJSONObject("geometry")?.optJSONArray("coordinates") ?: continue
        val longitude = coordinates.optDouble(0).takeIf(Double::isFinite) ?: continue
        val latitude = coordinates.optDouble(1).takeIf(Double::isFinite) ?: continue
        val distance = distanceMiles(originLatitude, originLongitude, latitude, longitude)
        if (distance > radiusMiles) continue
        val candidate = NearbyRiverGauge(
            gauge = RiverGauge(
                siteId = siteId,
                name = names[siteId] ?: siteId,
                latitude = latitude,
                longitude = longitude,
            ),
            distanceMiles = distance,
            currentHeightFeet = height,
            observedAt = observedAt,
            provisional = !properties.optString("approval_status").equals("Approved", ignoreCase = true),
        )
        val existing = latestBySite[siteId]
        if (existing == null || candidate.observedAt > existing.observedAt) latestBySite[siteId] = candidate
    }
    return latestBySite.values
        .sortedWith(compareBy<NearbyRiverGauge> { it.distanceMiles }.thenBy { it.gauge.name })
        .take(30)
}

internal fun selectRelevantWaterGauges(
    nearby: List<NearbyRiverGauge>,
    followed: List<RiverGauge>,
    originLatitude: Double?,
    originLongitude: Double?,
    radiusMiles: Double = NearbyWaterGaugeRadiusMiles,
    automaticLimit: Int = AutomaticWaterGaugeLimit,
): List<RiverGauge> {
    val automatic = nearby
        .sortedWith(compareBy<NearbyRiverGauge> { it.distanceMiles }.thenBy { it.gauge.name })
        .take(automaticLimit)
        .map { it.gauge.copy(enabled = true) }
    val relevantFollowed = if (originLatitude != null && originLongitude != null) {
        followed
            .filter(RiverGauge::enabled)
            .filter { gauge ->
                distanceMiles(originLatitude, originLongitude, gauge.latitude, gauge.longitude) <= radiusMiles
            }
            .sortedWith(
                compareBy<RiverGauge> {
                    distanceMiles(originLatitude, originLongitude, it.latitude, it.longitude)
                }.thenBy { it.name },
            )
    } else {
        emptyList()
    }
    return (automatic + relevantFollowed).distinctBy(RiverGauge::siteId)
}

internal fun parseRiverGaugeSeries(
    json: String,
    gauge: RiverGauge,
    periodDays: Int,
    placeLatitude: Double? = null,
    placeLongitude: Double? = null,
): RiverGaugeSeries {
    val features = JSONObject(json).optJSONArray("features") ?: JSONArray()
    val bySeries = linkedMapOf<String, MutableList<RiverGaugeReading>>()
    for (index in 0 until features.length()) {
        val properties = features.optJSONObject(index)?.optJSONObject("properties") ?: continue
        val observedAt = properties.stringOrNull("time") ?: continue
        val height = properties.numberOrNull("value") ?: continue
        val seriesId = properties.optString("time_series_id", "default")
        bySeries.getOrPut(seriesId) { mutableListOf() } += RiverGaugeReading(
            observedAt = observedAt,
            heightFeet = height,
            provisional = !properties.optString("approval_status").equals("Approved", ignoreCase = true),
        )
    }
    val readings = bySeries.values.maxByOrNull(List<RiverGaugeReading>::size)
        .orEmpty()
        .distinctBy(RiverGaugeReading::observedAt)
        .sortedBy(RiverGaugeReading::observedAt)
    if (readings.isEmpty()) {
        throw IOException("No water-height readings were reported for ${gauge.name} in the last $periodDays days.")
    }
    val distance = if (placeLatitude != null && placeLongitude != null) {
        distanceMiles(placeLatitude, placeLongitude, gauge.latitude, gauge.longitude)
    } else {
        null
    }
    return RiverGaugeSeries(
        gauge = gauge,
        periodDays = periodDays,
        readings = readings,
        distanceMiles = distance,
    )
}

internal fun forecastConditionLabel(code: Int?): String = when (code) {
    0 -> "Clear"
    1, 2 -> "Partly cloudy"
    3 -> "Overcast"
    45, 48 -> "Foggy"
    51, 53, 55, 56, 57 -> "Drizzle"
    61, 63, 65, 66, 67, 80, 81, 82 -> "Rain"
    71, 73, 75, 77, 85, 86 -> "Snow"
    95, 96, 99 -> "Thunderstorms"
    else -> "Current conditions"
}

private fun friendlyUsgsGaugeName(value: String): String {
    val words = value.substringBeforeLast(", ", value).lowercase(Locale.US).split(Regex("\\s+"))
    val smallWords = setOf("at", "above", "below", "near", "of", "the")
    return words.mapIndexed { index, word ->
        if (index > 0 && word in smallWords) word else word.replaceFirstChar { it.titlecase(Locale.US) }
    }.joinToString(" ")
}

private fun formatForecastDecimal(value: Double?): String =
    if (value == null) "0" else String.format(Locale.US, if (value < 1) "%.2f" else "%.1f", value)

private fun JSONObject.numberOrNull(name: String): Double? =
    if (!has(name) || isNull(name)) null else optDouble(name).takeIf(Double::isFinite)

private fun JSONObject.stringOrNull(name: String): String? =
    optString(name).trim().takeIf(String::isNotBlank)

private fun JSONObject.arrayNumber(name: String, index: Int): Double? =
    optJSONArray(name)?.let { array ->
        if (index >= array.length() || array.isNull(index)) null else array.optDouble(index).takeIf(Double::isFinite)
    }

private fun JSONObject.arrayString(name: String, index: Int): String? =
    optJSONArray(name)?.optString(index)?.trim()?.takeIf(String::isNotBlank)

private fun distanceMiles(latA: Double, lngA: Double, latB: Double, lngB: Double): Double {
    val earthRadiusMiles = 3958.8
    val latDistance = Math.toRadians(latB - latA)
    val lngDistance = Math.toRadians(lngB - lngA)
    val haversine = sin(latDistance / 2) * sin(latDistance / 2) +
        cos(Math.toRadians(latA)) * cos(Math.toRadians(latB)) *
        sin(lngDistance / 2) * sin(lngDistance / 2)
    return earthRadiusMiles * 2 * asin(sqrt(haversine.coerceIn(0.0, 1.0)))
}
