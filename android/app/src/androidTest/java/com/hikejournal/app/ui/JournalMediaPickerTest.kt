package com.hikejournal.app.ui

import android.Manifest
import android.content.ContentValues
import android.net.Uri
import android.provider.MediaStore
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.filters.SdkSuppress
import androidx.test.platform.app.InstrumentationRegistry
import com.hikejournal.app.data.FieldOperationQueue
import com.hikejournal.app.data.OperationKind
import com.hikejournal.app.data.local.OfflineDatabase
import com.hikejournal.app.data.localMediaAccess
import com.hikejournal.app.ui.theme.HikeJournalTheme
import java.io.DataOutputStream
import java.io.File
import java.util.UUID
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@SdkSuppress(minSdkVersion = 33)
class JournalMediaPickerTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun selectsPhotoAndLargeVideoTogetherAndQueuesBoth() = runBlocking {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        listOf(
            Manifest.permission.READ_MEDIA_IMAGES,
            Manifest.permission.READ_MEDIA_VIDEO,
            Manifest.permission.ACCESS_MEDIA_LOCATION,
        ).forEach { instrumentation.uiAutomation.grantRuntimePermission(context.packageName, it) }
        val resolver = context.contentResolver
        val hikeId = UUID.randomUUID().toString()
        val photoName = "$hikeId.jpg"
        val videoName = "$hikeId.mp4"
        val photo = resolver.insert(
            MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
            ContentValues().apply {
                put(MediaStore.MediaColumns.DISPLAY_NAME, photoName)
                put(MediaStore.MediaColumns.MIME_TYPE, "image/jpeg")
                put(MediaStore.MediaColumns.IS_PENDING, 1)
            },
        )!!
        var video: Uri? = null
        val dao = OfflineDatabase.get(context).operations()
        try {
            resolver.openOutputStream(photo)!!.use { output ->
                instrumentation.context.assets.open("design/hike.jpg").use { it.copyTo(output) }
            }
            video = resolver.insert(
                MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
                ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, videoName)
                    put(MediaStore.MediaColumns.MIME_TYPE, "video/mp4")
                    put(MediaStore.MediaColumns.IS_PENDING, 1)
                },
            )!!
            val padding = ByteArray(1024 * 1024)
            DataOutputStream(resolver.openOutputStream(video)!!).use { output ->
                instrumentation.context.assets.open("design/journal-video.mp4").use { it.copyTo(output) }
                output.writeInt(8 + 35 * padding.size)
                output.writeBytes("free")
                repeat(35) { output.write(padding) }
            }
            val published = ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }
            assertEquals(1, resolver.update(photo, published, null, null))
            assertEquals(1, resolver.update(video, published, null, null))
            val access = localMediaAccess(context)
            assertTrue(access.hasFullLibraryAccess)

            var selected = emptyList<Uri>()
            rule.setContent {
                HikeJournalTheme {
                    LocalMediaPickerDialog(access, {}, {}) { selected = it }
                }
            }
            rule.waitUntil(5_000) { rule.onAllNodesWithText("All phone media").fetchSemanticsNodes().isNotEmpty() }
            rule.onNodeWithText("All phone media").performClick()
            rule.onNodeWithContentDescription(photoName, substring = true).performClick()
            rule.onNodeWithContentDescription(videoName, substring = true).performClick()
            rule.onNodeWithText("Add 2 files").performClick()
            rule.runOnIdle { assertEquals(2, selected.size) }

            val queue = FieldOperationQueue(context)
            assertEquals(1, queue.inspectMediaLocations(selected).videoCount)
            val queued = selected.map { queue.queuePhoto(hikeId, it, "", false, scheduleSync = false) }
            assertEquals(listOf("image/jpeg", "video/mp4"), queued.map { it.contentType })
            val operation = dao.find(OperationKind.UploadPhoto, queued.last().id)!!
            assertTrue(File(operation.localFilePath!!).length() > 30L * padding.size)
            assertEquals(64, queued.last().width)
        } finally {
            dao.listForHike(hikeId).forEach { item ->
                item.localFilePath?.let { File(it).delete() }
                dao.delete(item.id)
            }
            video?.let { resolver.delete(it, null, null) }
            resolver.delete(photo, null, null)
        }
    }
}
