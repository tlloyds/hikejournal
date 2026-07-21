package com.hikejournal.app.data

import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import com.hikejournal.app.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.concurrent.TimeUnit

class HikeJournalApi(private val context: Context) {
    private val preferences = context.getSharedPreferences("hikejournal", Context.MODE_PRIVATE)
    private val client = OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(90, TimeUnit.SECONDS)
        .build()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    var serverUrl: String
        get() = preferences.getString("server_url", BuildConfig.DEFAULT_API_URL)
            ?.trim()?.trimEnd('/') ?: BuildConfig.DEFAULT_API_URL
        set(value) {
            preferences.edit().putString("server_url", normalizeServerUrl(value)).apply()
        }

    var pairingKey: String
        get() = preferences.getString("pairing_key", BuildConfig.MOBILE_API_TOKEN)
            ?.trim() ?: BuildConfig.MOBILE_API_TOKEN
        set(value) {
            preferences.edit().putString("pairing_key", value.trim()).apply()
        }

    suspend fun getHikesJson(): String = request("/v1/hikes")

    suspend fun getHikeJson(hikeId: String): String = request("/v1/hikes/$hikeId")

    suspend fun getSpeciesJson(): String = request("/v1/species")

    suspend fun getSpeciesDetailJson(key: String): String = request(
        "/v1/species/detail?key=${URLEncoder.encode(key, StandardCharsets.UTF_8.toString())}",
    )

    suspend fun getSightingsJson(): String = request("/v1/sightings")

    suspend fun getReviewQueueJson(): String = request("/v1/species/review")

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
                "This phone's companion service needs the latest HikeJournal update. Restart or redeploy it, then try again.",
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
                    .put("confidence", candidate.confidence ?: JSONObject.NULL),
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

    suspend fun updateCaption(photoId: String, caption: String): String = request(
        path = "/v1/photos/$photoId/caption",
        method = "PUT",
        body = JSONObject().put("caption", caption).toString().toRequestBody(jsonMediaType),
    )

    suspend fun deletePhoto(photoId: String): String = request(
        path = "/v1/photos/$photoId",
        method = "DELETE",
    )

    suspend fun queueSpeciesReview(photoId: String): String = request(
        path = "/v1/photos/$photoId/review",
        method = "POST",
        body = JSONObject().toString().toRequestBody(jsonMediaType),
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
    ): String = withContext(Dispatchers.IO) {
        if (!file.exists()) throw IOException("The queued field photo is missing from this phone.")
        val multipart = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("caption", caption)
            .addFormDataPart("queue_for_review", queueForReview.toString())
            .addFormDataPart("photo_id", photoId)
            .addFormDataPart("file", fileName, file.asRequestBody(contentType.toMediaTypeOrNull()))
            .build()
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
        body: okhttp3.RequestBody? = null,
    ): String = withContext(Dispatchers.IO) {
        val builder = Request.Builder()
            .url("${serverUrl}$path")
            .header("X-HikeJournal-Key", pairingKey)
            .header("Accept", "application/json")
        when (method) {
            "POST" -> builder.post(requireNotNull(body))
            "PUT" -> builder.put(requireNotNull(body))
            "DELETE" -> builder.delete(body)
        }
        execute(builder.build())
    }

    private fun execute(request: Request): String = client.newCall(request).execute().use { response ->
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

    private fun normalizeServerUrl(value: String): String {
        val clean = value.trim().trimEnd('/')
        if (clean.startsWith("http://") || clean.startsWith("https://")) return clean
        return "http://$clean"
    }
}

class ApiException(message: String, val statusCode: Int) : IOException(message)

private fun HikeDraft.toJson(): JSONObject = JSONObject()
    .put("title", title)
    .put("hike_date", hikeDate)
    .put("distance_miles", distanceMiles ?: JSONObject.NULL)
    .put("location_name", locationName)
    .put("notes", notes)

private fun ContentResolver.displayName(uri: Uri): String? {
    return query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        if (!cursor.moveToFirst()) return@use null
        cursor.getString(0)
    }
}
