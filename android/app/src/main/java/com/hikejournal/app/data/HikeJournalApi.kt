package com.hikejournal.app.data

import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import com.hikejournal.app.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.net.URI
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.concurrent.TimeUnit

internal fun postBodyOrEmpty(body: RequestBody?, jsonMediaType: MediaType): RequestBody =
    body ?: "{}".toRequestBody(jsonMediaType)

class HikeJournalApi(private val context: Context) {
    private val connectionPreferences = ConnectionPreferences(context)
    private val authPreferences = AuthPreferences(context)
    private val client = OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(90, TimeUnit.SECONDS)
        .build()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    var serverUrl: String
        get() = connectionPreferences.serverUrl(BuildConfig.DEFAULT_API_URL)
        set(value) {
            connectionPreferences.setServerUrl(normalizeServerUrl(value))
        }

    var pairingKey: String
        get() = connectionPreferences.pairingKey(BuildConfig.MOBILE_API_TOKEN)
        set(value) {
            connectionPreferences.setPairingKey(value.trim())
        }

    val authAccount: AuthAccount? get() = authPreferences.session()?.account
    val hasStoredSession: Boolean get() = authPreferences.session() != null

    suspend fun authenticateGoogle(credential: String, nonce: String): AuthAccount = withContext(Dispatchers.IO) {
        val response = executeRaw(
            Request.Builder()
                .url("${serverUrl}/v1/auth/google")
                .header("Accept", "application/json")
                .post(
                    JSONObject()
                        .put("credential", credential)
                        .put("nonce", nonce)
                        .put("device_id", authPreferences.deviceId())
                        .toString()
                        .toRequestBody(jsonMediaType),
                )
                .build(),
        )
        parseMobileSession(response).also(authPreferences::save).account
    }

    suspend fun refreshAuthSession(): AuthAccount = withContext(Dispatchers.IO) {
        refreshSession()?.account ?: throw ApiException("Sign in with Google to continue.", 401)
    }

    suspend fun signOut() = withContext(Dispatchers.IO) {
        val session = authPreferences.session()
        if (session != null) {
            runCatching {
                executeRaw(
                    authenticated(
                        Request.Builder()
                            .url("${serverUrl}/v1/auth/logout")
                            .post(
                                JSONObject()
                                    .put("refresh_token", session.refreshToken)
                                    .toString()
                                    .toRequestBody(jsonMediaType),
                            )
                            .build(),
                        session.accessToken,
                    ),
                )
            }
        }
        authPreferences.clear()
    }

    suspend fun deleteAccount() = withContext(Dispatchers.IO) {
        request(path = "/v1/account", method = "DELETE")
        authPreferences.clear()
    }

    suspend fun getHikesJson(): String = request("/v1/hikes")

    suspend fun getCompanionConfig(): CompanionConfig = parseCompanionConfig(
        json = request("/v1/config"),
        fallbackWebUrl = BuildConfig.DEFAULT_WEB_URL,
    )

    suspend fun getHikeJson(hikeId: String): String =
        request("/v1/hikes/$hikeId?include_photos=false&include_route=false")

    suspend fun getHikePhotosJson(hikeId: String, offset: Int): String =
        request("/v1/hikes/$hikeId/photos?offset=$offset&limit=100")

    suspend fun getHikeRouteJson(hikeId: String): String = request("/v1/hikes/$hikeId/route")

    suspend fun getHikeLocationsJson(stateCode: String): String = request(
        "/v1/hike-locations?state=${normalizeUsStateCode(stateCode).orEmpty().urlEncoded()}",
    )

    suspend fun createHikeLocationJson(name: String, latitude: Double?, longitude: Double?): String = request(
        path = "/v1/hike-locations",
        method = "POST",
        body = JSONObject()
            .put("name", name)
            .put("lat", latitude ?: JSONObject.NULL)
            .put("lng", longitude ?: JSONObject.NULL)
            .toString()
            .toRequestBody(jsonMediaType),
    )

    suspend fun getPlaceProfileJson(locationId: String): String =
        request("/v1/places/${locationId.urlEncoded()}/profile")

    suspend fun getPlaceConditionsJson(
        locationId: String,
        riverPeriodDays: Int,
        followedGaugeIDs: List<String>,
    ): String {
        val params = buildString {
            append("/v1/places/${locationId.urlEncoded()}/conditions?river_days=")
            append(if (riverPeriodDays >= 30) "30" else "7")
            followedGaugeIDs
                .map(String::trim)
                .filter(String::isNotEmpty)
                .distinct()
                .take(20)
                .forEach { append("&followed_gauge_id="); append(it.urlEncoded()) }
        }
        return request(params)
    }

    suspend fun getFieldBriefingJson(
        locationId: String,
        targetDate: String,
        iconicTaxa: List<String> = emptyList(),
    ): String {
        val filter = iconicTaxa.distinct().joinToString(",")
        val query = buildString {
            append("/v1/field-briefing?location_id=${locationId.urlEncoded()}&date=${targetDate.urlEncoded()}")
            if (filter.isNotBlank()) append("&iconic_taxon=${filter.urlEncoded()}")
        }
        return request(query)
    }

    suspend fun getHikeComparisonJson(hikeId: String, otherHikeId: String): String = request(
        "/v1/hikes/${hikeId.urlEncoded()}/comparison?other_hike_id=${otherHikeId.urlEncoded()}",
    )

    suspend fun enrichHikeWeatherJson(hikeId: String, force: Boolean = false): String = request(
        path = "/v1/hikes/${hikeId.urlEncoded()}/weather?force=$force",
        method = "POST",
    )

    suspend fun getSpeciesJson(): String = request("/v1/species")

    suspend fun getSpeciesDetailJson(key: String): String = request(
        "/v1/species/detail?key=${URLEncoder.encode(key, StandardCharsets.UTF_8.toString())}",
    )

    suspend fun getDiscoveryAreasJson(query: String = ""): String = request(
        "/v1/discovery/areas?q=${query.urlEncoded()}",
    )

    suspend fun getNearbySpeciesJson(
        areaId: String?,
        targetDate: String,
        radiusKm: Int,
        iconicTaxa: List<String>,
        latitude: Double? = null,
        longitude: Double? = null,
        limit: Int = 50,
    ): String {
        val params = mutableListOf(
            "date=${targetDate.urlEncoded()}",
            "radius_km=$radiusKm",
            "limit=$limit",
        )
        if (!areaId.isNullOrBlank()) params += "area_id=${areaId.urlEncoded()}"
        if (iconicTaxa.isNotEmpty()) {
            params += "iconic_taxon=${iconicTaxa.joinToString(",").urlEncoded()}"
        }
        if (latitude != null && longitude != null) {
            params += "lat=${roundedDiscoveryCoordinate(latitude)}"
            params += "lng=${roundedDiscoveryCoordinate(longitude)}"
            params += "area_name=${"Current area".urlEncoded()}"
        }
        return request("/v1/discovery/nearby?${params.joinToString("&")}")
    }

    suspend fun getSpeciesQuestsJson(): String = request("/v1/discovery/quests")

    suspend fun getSpeciesQuestJson(questId: String): String =
        request("/v1/discovery/quests/${questId.urlEncoded()}")

    suspend fun getNearbySightingsJson(nearby: NearbySpecies, taxonId: Long): String {
        val params = mutableListOf(
            "taxon_id=$taxonId",
            "date=${nearby.targetDate.urlEncoded()}",
            "radius_km=${nearby.radiusKm}",
        )
        if (nearby.areaId.isNotBlank()) {
            params += "area_id=${nearby.areaId.urlEncoded()}"
        } else if (nearby.latitude != null && nearby.longitude != null) {
            params += "lat=${roundedDiscoveryCoordinate(nearby.latitude)}"
            params += "lng=${roundedDiscoveryCoordinate(nearby.longitude)}"
            params += "area_name=${nearby.areaName.urlEncoded()}"
        }
        return request("/v1/discovery/nearby/sightings?${params.joinToString("&")}")
    }

    suspend fun getQuestSightingsJson(questId: String, taxonId: Long): String =
        request(
            "/v1/discovery/quests/${questId.urlEncoded()}/sightings?taxon_id=$taxonId",
        )

    suspend fun createSpeciesQuest(
        areaId: String,
        targetDate: String,
        radiusKm: Int,
        iconicTaxon: String?,
        title: String,
        linkedHikeId: String?,
        resultLimit: Int,
    ): String = request(
        path = "/v1/discovery/quests",
        method = "POST",
        body = JSONObject()
            .put("area_id", areaId)
            .put("target_date", targetDate)
            .put("radius_km", radiusKm)
            .put("iconic_taxon", iconicTaxon ?: JSONObject.NULL)
            .put("title", title)
            .put("linked_hike_id", linkedHikeId ?: JSONObject.NULL)
            .put("result_limit", resultLimit)
            .toString()
            .toRequestBody(jsonMediaType),
    )

    suspend fun updateSpeciesQuest(
        questId: String,
        title: String? = null,
        status: String? = null,
        linkedHikeId: String? = null,
        setLinkedHike: Boolean = false,
        focusTaxonIds: List<Long>? = null,
    ): String {
        val payload = JSONObject()
            .put("set_linked_hike", setLinkedHike)
        if (title != null) payload.put("title", title)
        if (status != null) payload.put("status", status)
        if (setLinkedHike) payload.put("linked_hike_id", linkedHikeId ?: JSONObject.NULL)
        if (focusTaxonIds != null) payload.put("focus_taxon_ids", org.json.JSONArray(focusTaxonIds))
        return request(
            path = "/v1/discovery/quests/${questId.urlEncoded()}",
            method = "PATCH",
            body = payload.toString().toRequestBody(jsonMediaType),
        )
    }

    suspend fun deleteSpeciesQuest(questId: String) {
        request(
            path = "/v1/discovery/quests/${questId.urlEncoded()}",
            method = "DELETE",
        )
    }

    suspend fun getSightingsJson(): String = request("/v1/sightings")

    suspend fun getMapRoutesJson(): String = request("/v1/routes")

    suspend fun getReviewQueueJson(): String = request("/v1/species/review")

    suspend fun requestReviewBatch(groups: List<List<String>>): String {
        val groupsJson = org.json.JSONArray()
        groups.forEach { photoIds ->
            groupsJson.put(
                JSONObject().put("photo_ids", org.json.JSONArray(photoIds)),
            )
        }
        return request(
            path = "/v1/species/review/batch-recommendation",
            method = "POST",
            body = JSONObject()
                .put("groups", groupsJson)
                .toString()
                .toRequestBody(jsonMediaType),
        )
    }

    suspend fun startReviewBatch(groups: List<List<String>>, clientRequestId: String? = null): String {
        val groupsJson = org.json.JSONArray()
        groups.forEach { photoIds ->
            groupsJson.put(JSONObject().put("photo_ids", org.json.JSONArray(photoIds)))
        }
        return request(
            path = "/v1/species/review/batch-recommendation/start",
            method = "POST",
            body = JSONObject()
                .put("groups", groupsJson)
                .put("client_request_id", clientRequestId ?: JSONObject.NULL)
                .toString()
                .toRequestBody(jsonMediaType),
        )
    }

    suspend fun getReviewBatchStatus(jobId: String): String =
        request("/v1/species/review/batch-recommendation/$jobId")

    suspend fun getInatAuthorizationUrl(): String = JSONObject(request("/v1/inat/oauth/start"))
        .getString("authorize_url")

    suspend fun requestReviewRecommendation(photoId: String): String = try {
        request(
            path = "/v1/species/review/$photoId/recommendation",
            method = "POST",
            body = JSONObject().toString().toRequestBody(jsonMediaType),
        )
    } catch (error: ApiException) {
        if (error.statusCode == 404) {
            throw ApiException(
                "This action isn’t available with the current connection yet.",
                error.statusCode,
            )
        }
        throw error
    }

    suspend fun getPublishQueueJson(): String = request("/v1/species/publish")

    suspend fun publishObservation(observationId: String, options: PublishOptions): String = request(
        path = "/v1/species/publish/$observationId",
        method = "POST",
        body = JSONObject()
            .put("acknowledged_public", true)
            .put("observation_ids", org.json.JSONArray(options.observationIds))
            .put("description", options.description)
            .put("tags", org.json.JSONArray(options.tags))
            .put("geoprivacy", options.geoprivacy)
            .put("captive", options.captive)
            .toString()
            .toRequestBody(jsonMediaType),
    )

    suspend fun startPublishBatch(
        groups: List<List<String>>,
        options: PublishOptions,
        clientRequestId: String? = null,
    ): String {
        val groupPayload = org.json.JSONArray()
        groups.forEach { observationIds ->
            groupPayload.put(org.json.JSONObject().put("observation_ids", org.json.JSONArray(observationIds)))
        }
        return request(
            path = "/v1/species/publish/batch/start",
            method = "POST",
            body = JSONObject()
                .put("acknowledged_public", true)
                .put("groups", groupPayload)
                .put("client_request_id", clientRequestId ?: JSONObject.NULL)
                .put("description", options.description)
                .put("tags", org.json.JSONArray(options.tags))
                .put("geoprivacy", options.geoprivacy)
                .put("captive", options.captive)
                .toString()
                .toRequestBody(jsonMediaType),
        )
    }

    suspend fun getPublishBatchStatus(jobId: String): String =
        request("/v1/species/publish/batch/$jobId")

    suspend fun decideReview(
        photoId: String,
        observationId: String?,
        action: String,
        candidate: ReviewCandidate?,
    ): String {
        val payload = JSONObject()
            .put("action", action)
            .put("observation_id", observationId ?: JSONObject.NULL)
        if (candidate != null) {
            payload.put(
                "candidate",
                JSONObject()
                    .put("taxon_id", candidate.taxonId ?: JSONObject.NULL)
                    .put("common_name", candidate.commonName)
                    .put("scientific_name", candidate.scientificName)
                    .put("confidence", normalizedReviewConfidence(candidate.confidence) ?: JSONObject.NULL),
            )
        }
        return request(
            path = "/v1/species/review/$photoId/decision",
            method = "POST",
            body = payload.toString().toRequestBody(jsonMediaType),
        )
    }

    suspend fun createHike(draft: HikeDraft, hikeId: String? = null): String = request(
        path = "/v1/hikes",
        method = "POST",
        body = draft.toJson().apply { put("id", hikeId ?: JSONObject.NULL) }.toString().toRequestBody(jsonMediaType),
    )

    suspend fun updateHike(hikeId: String, draft: HikeDraft): String = request(
        path = "/v1/hikes/$hikeId",
        method = "PUT",
        body = draft.toJson().toString().toRequestBody(jsonMediaType),
    )

    suspend fun setArchived(hikeId: String, archived: Boolean): String = request(
        path = "/v1/hikes/$hikeId/archive",
        method = "PUT",
        body = JSONObject().put("is_archived", archived).toString().toRequestBody(jsonMediaType),
    )

    suspend fun deleteHike(hikeId: String): String = request(
        path = "/v1/hikes/$hikeId",
        method = "DELETE",
    )

    suspend fun setHikeCover(hikeId: String, photoId: String?): String = request(
        path = "/v1/hikes/$hikeId/cover",
        method = "PUT",
        body = JSONObject().put("photo_id", photoId ?: JSONObject.NULL).toString().toRequestBody(jsonMediaType),
    )

    suspend fun createFieldMark(mark: FieldMark): String = request(
        path = "/v1/hikes/${mark.hikeId.urlEncoded()}/field-marks",
        method = "POST",
        body = JSONObject()
            .put("id", mark.id)
            .put("recording_session_id", mark.recordingSessionId ?: JSONObject.NULL)
            .put("marked_at", mark.markedAt)
            .put("lat", mark.latitude)
            .put("lng", mark.longitude)
            .put("accuracy_meters", mark.accuracyMeters ?: JSONObject.NULL)
            .put("mark_type", mark.markType)
            .put("note", mark.note)
            .toString()
            .toRequestBody(jsonMediaType),
    )

    suspend fun updateObservationNaturalHistory(
        observationId: String,
        confidence: String,
        provenance: String,
        phenophases: List<String>,
    ): String = request(
        path = "/v1/observations/${observationId.urlEncoded()}/natural-history",
        method = "PUT",
        body = JSONObject()
            .put("confidence", confidence)
            .put("provenance", provenance)
            .put(
                "phenophases",
                org.json.JSONArray().apply {
                    phenophases.forEach { code -> put(JSONObject().put("code", code)) }
                },
            )
            .toString()
            .toRequestBody(jsonMediaType),
    )

    suspend fun uploadRouteFile(
        hikeId: String,
        file: java.io.File,
        fileName: String,
        sourceType: String? = null,
    ): String = withContext(Dispatchers.IO) {
        if (!file.exists()) throw IOException("The selected TCX file is no longer available on this phone.")
        val multipartBuilder = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", fileName, file.asRequestBody("application/vnd.garmin.tcx+xml".toMediaType()))
        sourceType?.takeIf { it.isNotBlank() }?.let {
            multipartBuilder.addFormDataPart("source_type", it)
        }
        val multipart = multipartBuilder.build()
        execute(
            Request.Builder()
                .url("${serverUrl}/v1/hikes/$hikeId/route")
                .header("X-HikeJournal-Key", pairingKey)
                .post(multipart)
                .build(),
        )
    }

    suspend fun updateCaption(photoId: String, caption: String): String = request(
        path = "/v1/photos/$photoId/caption",
        method = "PUT",
        body = JSONObject().put("caption", caption).toString().toRequestBody(jsonMediaType),
    )

    suspend fun deletePhoto(photoId: String): String = request(
        path = "/v1/photos/$photoId",
        method = "DELETE",
    )

    suspend fun setSpeciesReview(photoId: String, queued: Boolean): String = request(
        path = "/v1/photos/$photoId/review",
        method = "PUT",
        body = JSONObject().put("queued", queued).toString().toRequestBody(jsonMediaType),
    )

    suspend fun assignKnownSpecies(
        photoId: String,
        taxonId: Long?,
        commonName: String,
        scientificName: String,
    ): String = request(
        path = "/v1/photos/$photoId/species",
        method = "PUT",
        body = JSONObject()
            .put("taxon_id", taxonId ?: JSONObject.NULL)
            .put("common_name", commonName)
            .put("scientific_name", scientificName)
            .toString()
            .toRequestBody(jsonMediaType),
    )

    suspend fun uploadPhoto(
        hikeId: String,
        uri: Uri,
        caption: String,
        queueForReview: Boolean,
    ): String = withContext(Dispatchers.IO) {
        val resolver = context.contentResolver
        val bytes = resolver.openInputStream(uri)?.use { it.readBytes() }
            ?: throw IOException("The selected photo could not be opened.")
        val contentType = resolver.getType(uri) ?: "image/jpeg"
        val filename = resolver.displayName(uri) ?: "hike-photo.jpg"
        val multipart = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("caption", caption)
            .addFormDataPart("queue_for_review", queueForReview.toString())
            .addFormDataPart(
                "file",
                filename,
                bytes.toRequestBody(contentType.toMediaTypeOrNull()),
            )
            .build()
        execute(
            Request.Builder()
                .url("${serverUrl}/v1/hikes/$hikeId/photos")
                .header("X-HikeJournal-Key", pairingKey)
                .post(multipart)
                .build(),
        )
    }

    suspend fun uploadPhotoFile(
        hikeId: String,
        photoId: String,
        file: java.io.File,
        contentType: String,
        fileName: String,
        caption: String,
        queueForReview: Boolean,
        takenAt: String?,
        latitude: Double?,
        longitude: Double?,
    ): String = withContext(Dispatchers.IO) {
        if (!file.exists()) throw IOException("The queued field photo is missing from this phone.")
        val multipartBuilder = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("caption", caption)
            .addFormDataPart("queue_for_review", queueForReview.toString())
            .addFormDataPart("photo_id", photoId)
            .addFormDataPart("file", fileName, file.asRequestBody(contentType.toMediaTypeOrNull()))
        takenAt?.takeIf { it.isNotBlank() }?.let {
            multipartBuilder.addFormDataPart("taken_at", it)
        }
        latitude?.let {
            multipartBuilder.addFormDataPart("lat", it.toString())
        }
        longitude?.let {
            multipartBuilder.addFormDataPart("lng", it.toString())
        }
        val multipart = multipartBuilder.build()
        execute(
            Request.Builder()
                .url("${serverUrl}/v1/hikes/$hikeId/photos")
                .header("X-HikeJournal-Key", pairingKey)
                .post(multipart)
                .build(),
        )
    }

    private suspend fun request(
        path: String,
        method: String = "GET",
        body: RequestBody? = null,
    ): String = withContext(Dispatchers.IO) {
        val builder = Request.Builder()
            .url("${serverUrl}$path")
            .header("X-HikeJournal-Key", pairingKey)
            .header("Accept", "application/json")
        when (method) {
            "POST" -> builder.post(postBodyOrEmpty(body, jsonMediaType))
            "PUT" -> builder.put(requireNotNull(body))
            "PATCH" -> builder.patch(requireNotNull(body))
            "DELETE" -> builder.delete(body)
        }
        execute(builder.build())
    }

    private fun execute(request: Request): String {
        val first = authenticated(request)
        return try {
            executeRaw(first)
        } catch (error: ApiException) {
            if (error.statusCode != 401 || !BuildConfig.GOOGLE_AUTH_ENABLED) throw error
            val refreshed = refreshSession() ?: throw error
            executeRaw(authenticated(request, refreshed.accessToken))
        }
    }

    @Synchronized
    private fun refreshSession(): MobileSession? {
        val existing = authPreferences.session() ?: return null
        return try {
            val response = executeRaw(
                Request.Builder()
                    .url("${serverUrl}/v1/auth/refresh")
                    .header("Accept", "application/json")
                    .post(
                        JSONObject()
                            .put("refresh_token", existing.refreshToken)
                            .put("device_id", authPreferences.deviceId())
                            .toString()
                            .toRequestBody(jsonMediaType),
                    )
                    .build(),
            )
            parseMobileSession(response).also(authPreferences::save)
        } catch (_: Exception) {
            authPreferences.clear()
            null
        }
    }

    private fun authenticated(request: Request, accessToken: String? = authPreferences.session()?.accessToken): Request {
        val builder = request.newBuilder()
            .removeHeader("Authorization")
            .removeHeader("X-HikeJournal-Key")
        if (BuildConfig.GOOGLE_AUTH_ENABLED) {
            accessToken?.takeIf(String::isNotBlank)?.let { builder.header("Authorization", "Bearer $it") }
        } else {
            builder.header("X-HikeJournal-Key", pairingKey)
        }
        return builder.build()
    }

    private fun executeRaw(request: Request): String = client.newCall(request).execute().use { response ->
        val responseBody = response.body?.string().orEmpty()
        if (!response.isSuccessful) {
            val detail = runCatching { JSONObject(responseBody).optString("detail") }.getOrNull()
            throw ApiException(
                detail?.takeIf { it.isNotBlank() } ?: "HikeJournal returned ${response.code}.",
                response.code,
            )
        }
        responseBody
    }

    private fun parseMobileSession(json: String): MobileSession {
        val root = JSONObject(json)
        val account = root.getJSONObject("account")
        return MobileSession(
            accessToken = root.getString("access_token"),
            refreshToken = root.getString("refresh_token"),
            account = AuthAccount(
                subject = account.getString("subject"),
                email = account.getString("email"),
                displayName = account.optString("display_name", account.getString("email")),
                pictureUrl = account.optString("picture_url"),
            ),
        )
    }

    private fun normalizeServerUrl(value: String): String {
        val clean = value.trim().trimEnd('/')
        if (
            clean.startsWith("http://", ignoreCase = true) ||
            clean.startsWith("https://", ignoreCase = true)
        ) {
            val schemeLength = clean.indexOf(":")
            return clean.replaceRange(0, schemeLength, clean.substring(0, schemeLength).lowercase())
        }
        return "http://$clean"
    }
}

class ApiException(message: String, val statusCode: Int) : IOException(message)

data class CompanionConfig(
    val webUrl: String,
    val apiVersion: String? = null,
    val capabilities: Set<String> = emptySet(),
    val contractVersion: String? = null,
    val minimumAndroidVersion: String? = null,
    val recommendedAndroidVersion: String? = null,
)

internal fun parseCompanionConfig(json: String, fallbackWebUrl: String): CompanionConfig {
    val payload = JSONObject(json)
    val compatibility = payload.optJSONObject("compatibility")
    val capabilitiesJson = payload.optJSONArray("capabilities")
    val capabilities = buildSet {
        for (index in 0 until (capabilitiesJson?.length() ?: 0)) {
            capabilitiesJson?.optString(index)
                ?.trim()
                ?.takeIf(String::isNotBlank)
                ?.let(::add)
        }
    }
    val webUrl = validHttpUrl(payload.optString("web_url"))
        ?: validHttpUrl(fallbackWebUrl)
        .orEmpty()
    return CompanionConfig(
        webUrl = webUrl,
        apiVersion = payload.optionalString("api_version"),
        capabilities = capabilities,
        contractVersion = payload.optionalString("contract_version"),
        minimumAndroidVersion = compatibility?.optionalString("minimum_android_version"),
        recommendedAndroidVersion = compatibility?.optionalString("recommended_android_version"),
    )
}

private fun JSONObject.optionalString(key: String): String? = takeUnless { isNull(key) }
    ?.optString(key)
    ?.trim()
    ?.takeIf(String::isNotBlank)

internal fun validHttpUrl(value: String): String? {
    val clean = value.trim().trimEnd('/')
    val uri = runCatching { URI(clean) }.getOrNull() ?: return null
    return clean.takeIf {
        uri.scheme?.lowercase() in setOf("http", "https") &&
            !uri.host.isNullOrBlank() &&
            uri.userInfo == null &&
            uri.rawQuery == null &&
            uri.rawFragment == null
    }
}

private fun HikeDraft.toJson(): JSONObject = JSONObject()
    .put("title", title)
    .put("hike_date", hikeDate)
    .put("distance_miles", distanceMiles ?: JSONObject.NULL)
    .put("location_name", locationName)
    .put("notes", notes)
    .put("location_id", locationId ?: JSONObject.NULL)

private fun ContentResolver.displayName(uri: Uri): String? {
    return query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        if (!cursor.moveToFirst()) return@use null
        cursor.getString(0)
    }
}

private fun String.urlEncoded(): String =
    URLEncoder.encode(this, StandardCharsets.UTF_8.toString())
