package com.hikejournal.app.data

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.ListenableWorker.Result
import com.hikejournal.app.MainActivity
import kotlinx.coroutines.delay
import org.json.JSONArray
import java.io.IOException
import java.util.UUID
import java.util.concurrent.TimeUnit

internal data class SpeciesReviewBatchRequest(
    val requestId: String,
    val groups: List<List<String>>,
)

/**
 * Owns the durable client-side half of a species review batch.
 *
 * The companion API does the expensive identification work. WorkManager keeps the
 * start request and status polling alive when the Activity is backgrounded or the
 * app process is recreated, while the request ID makes a lost start response safe
 * to retry.
 */
object SpeciesReviewBatchWork {
    const val WorkName = "hikejournal-species-review-batch"

    internal const val ProgressJobId = "job_id"
    internal const val ProgressState = "state"
    internal const val ProgressTotalPhotos = "total_photos"
    internal const val ProgressProcessedCount = "processed_count"
    internal const val ProgressCurrentPhotoNumber = "current_photo_number"
    internal const val ProgressCurrentPhotoId = "current_photo_id"
    internal const val ProgressTotalGroups = "total_groups"
    internal const val ProgressCurrentGroup = "current_group"
    internal const val ProgressGroupedCount = "grouped_count"
    internal const val ProgressIndividualCount = "individual_count"
    internal const val ProgressWarning = "warning"
    internal const val ProgressError = "error"

    private const val PreferencesName = "species-review-batch"
    private const val RequestIdKey = "request_id"
    private const val GroupsKey = "groups"
    private const val JobIdKey = "job_id"
    private const val NotificationChannelId = "species-review-batch"
    private const val NotificationId = 4102

    fun enqueue(context: Context, groups: List<List<String>>): UUID {
        val requestId = UUID.randomUUID().toString()
        val requestJson = JSONArray().apply {
            groups.forEach { put(JSONArray(it)) }
        }.toString()
        context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
            .edit()
            .clear()
            .putString(RequestIdKey, requestId)
            .putString(GroupsKey, requestJson)
            .commit()

        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val request = OneTimeWorkRequestBuilder<SpeciesReviewBatchWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(
            WorkName,
            ExistingWorkPolicy.REPLACE,
            request,
        )
        return request.id
    }

    internal fun loadRequest(context: Context): SpeciesReviewBatchRequest? {
        val preferences = context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
        val requestId = preferences.getString(RequestIdKey, null)?.takeIf { it.isNotBlank() } ?: return null
        val groupsJson = preferences.getString(GroupsKey, null)?.takeIf { it.isNotBlank() } ?: return null
        val groupsArray = runCatching { JSONArray(groupsJson) }.getOrNull() ?: return null
        val groups = List(groupsArray.length()) { groupIndex ->
            val group = groupsArray.optJSONArray(groupIndex) ?: JSONArray()
            List(group.length()) { photoIndex -> group.optString(photoIndex) }
                .filter(String::isNotBlank)
        }.filter(List<String>::isNotEmpty)
        if (groups.isEmpty()) return null
        return SpeciesReviewBatchRequest(requestId, groups)
    }

    internal fun loadJobId(context: Context): String? = context
        .getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
        .getString(JobIdKey, null)
        ?.takeIf { it.isNotBlank() }

    internal fun saveJobId(context: Context, jobId: String) {
        context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
            .edit()
            .putString(JobIdKey, jobId)
            .commit()
    }

    internal fun emptyStatus(request: SpeciesReviewBatchRequest, state: String = "queued") = ReviewBatchStatus(
        jobId = "",
        state = state,
        totalPhotos = request.groups.sumOf(List<String>::size),
        processedCount = 0,
        processedPhotoIds = emptyList(),
        currentPhotoNumber = 0,
        currentPhotoId = null,
        totalGroups = request.groups.size,
        currentGroup = 0,
        groupedCount = 0,
        individualCount = 0,
        warnings = emptyList(),
        error = null,
        items = emptyList(),
    )

    internal fun statusData(status: ReviewBatchStatus): Data = Data.Builder()
        .putString(ProgressJobId, status.jobId)
        .putString(ProgressState, status.state)
        .putInt(ProgressTotalPhotos, status.totalPhotos)
        .putInt(ProgressProcessedCount, status.processedCount)
        .putInt(ProgressCurrentPhotoNumber, status.currentPhotoNumber)
        .putString(ProgressCurrentPhotoId, status.currentPhotoId.orEmpty())
        .putInt(ProgressTotalGroups, status.totalGroups)
        .putInt(ProgressCurrentGroup, status.currentGroup)
        .putInt(ProgressGroupedCount, status.groupedCount)
        .putInt(ProgressIndividualCount, status.individualCount)
        .putString(ProgressWarning, status.warnings.firstOrNull().orEmpty())
        .putString(ProgressError, status.error.orEmpty())
        .build()

    internal fun statusFromData(data: Data): ReviewBatchStatus? {
        val state = data.getString(ProgressState)?.takeIf { it.isNotBlank() } ?: return null
        return ReviewBatchStatus(
            jobId = data.getString(ProgressJobId).orEmpty(),
            state = state,
            totalPhotos = data.getInt(ProgressTotalPhotos, 0),
            processedCount = data.getInt(ProgressProcessedCount, 0),
            processedPhotoIds = emptyList(),
            currentPhotoNumber = data.getInt(ProgressCurrentPhotoNumber, 0),
            currentPhotoId = data.getString(ProgressCurrentPhotoId)?.takeIf { it.isNotBlank() },
            totalGroups = data.getInt(ProgressTotalGroups, 0),
            currentGroup = data.getInt(ProgressCurrentGroup, 0),
            groupedCount = data.getInt(ProgressGroupedCount, 0),
            individualCount = data.getInt(ProgressIndividualCount, 0),
            warnings = data.getString(ProgressWarning)?.takeIf { it.isNotBlank() }?.let(::listOf).orEmpty(),
            error = data.getString(ProgressError)?.takeIf { it.isNotBlank() },
            items = emptyList(),
        )
    }

    internal fun failureData(status: ReviewBatchStatus): Data = Data.Builder()
        .putString(ProgressState, "failed")
        .putString(ProgressJobId, status.jobId)
        .putInt(ProgressTotalPhotos, status.totalPhotos)
        .putInt(ProgressProcessedCount, status.processedCount)
        .putString(ProgressError, status.error.orEmpty())
        .build()

    internal fun notificationId(): Int = NotificationId

    internal fun notificationChannelId(): String = NotificationChannelId
}

class SpeciesReviewBatchWorker(
    context: Context,
    parameters: WorkerParameters,
) : CoroutineWorker(context, parameters) {
    private val appContext = applicationContext

    override suspend fun doWork(): Result {
        val request = SpeciesReviewBatchWork.loadRequest(appContext)
            ?: return Result.failure()
        var status = SpeciesReviewBatchWork.emptyStatus(request)
        publish(status)

        return try {
            val storedJobId = SpeciesReviewBatchWork.loadJobId(appContext)
            status = if (storedJobId == null) {
                repository().startReviewBatch(request.groups, request.requestId).also { started ->
                    SpeciesReviewBatchWork.saveJobId(appContext, started.jobId)
                }
            } else {
                repository().getReviewBatchStatus(storedJobId)
            }
            publish(status)

            var statusCheckFailures = 0
            while (status.state == "queued" || status.state == "running") {
                if (isStopped) return Result.retry()
                delay(1_500)
                status = try {
                    repository().getReviewBatchStatus(status.jobId)
                } catch (error: IOException) {
                    statusCheckFailures += 1
                    if (statusCheckFailures >= 3) throw error
                    continue
                }
                statusCheckFailures = 0
                publish(status)
            }

            if (status.state == "completed") {
                Result.success(SpeciesReviewBatchWork.statusData(status))
            } else {
                Result.failure(SpeciesReviewBatchWork.failureData(status))
            }
        } catch (error: ApiException) {
            val message = error.message ?: "HikeJournal could not complete the species review batch."
            if (error.statusCode == 408 || error.statusCode == 425 || error.statusCode == 429 || error.statusCode >= 500) {
                Result.retry()
            } else {
                val failed = status.copy(state = "failed", error = message)
                publish(failed)
                Result.failure(SpeciesReviewBatchWork.failureData(failed))
            }
        } catch (error: IOException) {
            Result.retry()
        } catch (error: Exception) {
            val failed = status.copy(
                state = "failed",
                error = error.message ?: "HikeJournal could not complete the species review batch.",
            )
            publish(failed)
            Result.failure(SpeciesReviewBatchWork.failureData(failed))
        }
    }

    private fun repository(): HikeJournalRepository = HikeJournalRepository(appContext)

    private suspend fun publish(status: ReviewBatchStatus) {
        setProgress(SpeciesReviewBatchWork.statusData(status))
        setForeground(createForegroundInfo(status))
    }

    private fun createForegroundInfo(status: ReviewBatchStatus): ForegroundInfo {
        val notificationManager = appContext.getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            notificationManager.createNotificationChannel(
                NotificationChannel(
                    SpeciesReviewBatchWork.notificationChannelId(),
                    "Species review",
                    NotificationManager.IMPORTANCE_LOW,
                ).apply {
                    description = "Progress while HikeJournal identifies species-review photos"
                },
            )
        }

        val total = status.totalPhotos.coerceAtLeast(1)
        val current = status.processedCount.coerceIn(0, total)
        val label = when (status.state) {
            "queued" -> "Preparing ID requests…"
            "running" -> "Identifying photo $current of ${status.totalPhotos}…"
            "completed" -> "Species review batch complete"
            "failed" -> "Species review batch stopped"
            else -> "Updating species review batch…"
        }
        val launchIntent = PendingIntent.getActivity(
            appContext,
            4103,
            Intent(appContext, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(appContext, SpeciesReviewBatchWork.notificationChannelId())
            .setSmallIcon(com.hikejournal.app.R.drawable.ic_tracking_notification)
            .setContentTitle("HikeJournal species review")
            .setContentText(label)
            .setContentIntent(launchIntent)
            .setOnlyAlertOnce(true)
            .setOngoing(status.state == "queued" || status.state == "running")
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setProgress(total, current, status.state == "queued")
            .build()
        val serviceType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
        } else {
            0
        }
        return ForegroundInfo(SpeciesReviewBatchWork.notificationId(), notification, serviceType)
    }
}
