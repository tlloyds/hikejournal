package com.hikejournal.app.data

import com.hikejournal.app.data.local.PendingOperationEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FieldSyncOrderingTest {
    @Test
    fun `hike children wait for create even when timestamps match`() {
        val route = operation(
            id = "route",
            kind = OperationKind.UploadRoute,
            entityId = "recorded-route:hike-1",
            parentId = "hike-1",
        )
        val create = operation(
            id = "create",
            kind = OperationKind.CreateHike,
            entityId = "hike-1",
        )

        assertEquals(create, selectNextSyncOperation(listOf(route, create)))
    }

    @Test
    fun `tracked hike metadata update waits behind its original create`() {
        val update = operation(
            id = "update",
            kind = OperationKind.UpdateHike,
            entityId = "hike-1",
            payloadJson = """{"title":"Named hike"}""",
        )
        val create = operation(
            id = "create",
            kind = OperationKind.CreateHike,
            entityId = "hike-1",
            payloadJson = """{"title":"Untitled hike"}""",
        )

        assertEquals(create, selectNextSyncOperation(listOf(update, create)))
        assertEquals(update, selectNextSyncOperation(listOf(update)))
    }

    @Test
    fun `field mark waits for its offline hike to exist`() {
        val mark = operation(
            id = "mark",
            kind = OperationKind.CreateFieldMark,
            entityId = "mark-1",
            parentId = "hike-1",
            payloadJson = "{\"wait_for_hike_create\":true}",
        )
        val create = operation("create", OperationKind.CreateHike, "hike-1")

        assertEquals(create, selectNextSyncOperation(listOf(mark, create)))
        assertNull(selectNextSyncOperation(listOf(mark)))
    }

    @Test
    fun `failed create blocks route photos and edits`() {
        val create = operation(
            id = "create",
            kind = OperationKind.CreateHike,
            entityId = "hike-1",
            state = "needs_attention",
        )
        val children = listOf(
            operation("route", OperationKind.UploadRoute, "route-1", "hike-1"),
            operation("photo", OperationKind.UploadPhoto, "photo-1", "hike-1"),
            operation("edit", OperationKind.UpdateHike, "hike-1"),
        )

        assertNull(selectNextSyncOperation(children + create, prioritizedPhotoId = "photo-1"))
    }

    @Test
    fun `prioritized photo runs after create is gone`() {
        val route = operation("route", OperationKind.UploadRoute, "route-1", "hike-1")
        val photo = operation("photo", OperationKind.UploadPhoto, "photo-1", "hike-1")

        assertEquals(photo, selectNextSyncOperation(listOf(route, photo), prioritizedPhotoId = "photo-1"))
    }

    @Test
    fun `selected cover waits for its pending photo upload even when ordering ties`() {
        val cover = operation(
            id = "cover",
            kind = OperationKind.SetHikeCover,
            entityId = "hike-1",
            payloadJson = """{"photo_id":"photo-1"}""",
        )
        val photo = operation(
            id = "photo",
            kind = OperationKind.UploadPhoto,
            entityId = "photo-1",
            parentId = "hike-1",
        )

        assertEquals(photo, selectNextSyncOperation(listOf(cover, photo)))
    }

    @Test
    fun `cover photo jumps a large upload queue and cover update follows it`() {
        val uploads = (1..184).map { index ->
            operation(
                id = "upload-$index",
                kind = OperationKind.UploadPhoto,
                entityId = "photo-$index",
                parentId = "hike-1",
            )
        }
        val cover = operation(
            id = "cover",
            kind = OperationKind.SetHikeCover,
            entityId = "hike-1",
            payloadJson = """{"photo_id":"photo-184"}""",
        )

        assertEquals(uploads.last(), selectNextSyncOperation(uploads + cover))
        assertEquals(cover, selectNextSyncOperation(uploads.dropLast(1) + cover))
    }

    @Test
    fun `clearing a cover jumps pending photo uploads`() {
        val photo = operation("photo", OperationKind.UploadPhoto, "photo-1", "hike-1")
        val clearCover = operation(
            id = "cover",
            kind = OperationKind.SetHikeCover,
            entityId = "hike-1",
            payloadJson = """{"photo_id":null}""",
        )

        assertEquals(clearCover, selectNextSyncOperation(listOf(photo, clearCover)))
    }

    @Test
    fun `ordinary photo uploads run in bounded parallel batches`() {
        val uploads = (1..184).map { index ->
            operation(
                id = "upload-$index",
                kind = OperationKind.UploadPhoto,
                entityId = "photo-$index",
                parentId = "hike-1",
            )
        }

        assertEquals(uploads.take(2), selectNextSyncBatch(uploads))
        assertEquals(uploads.take(3), selectNextSyncBatch(uploads, maxParallelPhotoUploads = 3))
    }

    @Test
    fun `selected cover upload runs alone so its cover update can follow immediately`() {
        val ordinary = operation("ordinary", OperationKind.UploadPhoto, "photo-1", "hike-1")
        val selected = operation("selected", OperationKind.UploadPhoto, "photo-2", "hike-1")
        val cover = operation(
            id = "cover",
            kind = OperationKind.SetHikeCover,
            entityId = "hike-1",
            payloadJson = """{"photo_id":"photo-2"}""",
        )

        assertEquals(listOf(selected), selectNextSyncBatch(listOf(ordinary, selected, cover)))
    }

    @Test
    fun `metadata changes never share a batch with uploads`() {
        val update = operation("update", OperationKind.UpdateHike, "hike-1")
        val photo = operation("photo", OperationKind.UploadPhoto, "photo-1", "hike-1")

        assertEquals(listOf(update), selectNextSyncBatch(listOf(update, photo)))
    }

    @Test
    fun `every locally selected review photo remains visible while uploads drain`() {
        val operations = (1..35).map { index ->
            operation(
                id = "upload-$index",
                kind = OperationKind.UploadPhoto,
                entityId = "photo-$index",
                parentId = "hike-1",
                payloadJson = """{"queue_for_review":true}""",
            )
        } + operation(
            id = "video",
            kind = OperationKind.UploadPhoto,
            entityId = "video-1",
            parentId = "hike-1",
            payloadJson = """{"queue_for_review":true}""",
            contentType = "video/mp4",
        )

        val reviewUploads = pendingReviewUploadOperations(operations)

        assertEquals(35, reviewUploads.size)
        assertTrue(reviewUploads.all { it.entityId.startsWith("photo-") })
    }

    @Test
    fun `offline pending create is cancelled locally without an API requirement`() {
        val create = operation("create", OperationKind.CreateHike, "hike-1")

        assertEquals(
            HikeDeletionMode.QUEUE_LOCAL_DRAFT_DELETION,
            selectHikeDeletionMode(listOf(create), "hike-1", remoteDeletionAllowed = false),
        )
    }

    @Test
    fun `offline synced hike still requires a connection`() {
        assertEquals(
            HikeDeletionMode.REQUIRE_CONNECTION,
            selectHikeDeletionMode(emptyList(), "hike-1", remoteDeletionAllowed = false),
        )
    }

    @Test
    fun `pending create is cancelled locally even when the network is available`() {
        val create = operation("create", OperationKind.CreateHike, "hike-1")

        assertEquals(
            HikeDeletionMode.QUEUE_LOCAL_DRAFT_DELETION,
            selectHikeDeletionMode(listOf(create), "hike-1", remoteDeletionAllowed = true),
        )
    }

    @Test
    fun `online synced hike attempts the idempotent API`() {
        assertEquals(
            HikeDeletionMode.DELETE_REMOTE_NOW,
            selectHikeDeletionMode(emptyList(), "hike-1", remoteDeletionAllowed = true),
        )
    }

    @Test
    fun `existing deletion intent can finish local cleanup while offline`() {
        val deletion = operation("delete", OperationKind.DeleteHike, "hike-1")

        assertEquals(
            HikeDeletionMode.QUEUE_LOCAL_DRAFT_DELETION,
            selectHikeDeletionMode(listOf(deletion), "hike-1", remoteDeletionAllowed = false),
        )
    }

    private fun operation(
        id: String,
        kind: String,
        entityId: String,
        parentId: String? = null,
        state: String = "queued",
        payloadJson: String = "{}",
        contentType: String? = null,
    ) = PendingOperationEntity(
        id = id,
        kind = kind,
        entityId = entityId,
        parentId = parentId,
        payloadJson = payloadJson,
        localFilePath = null,
        contentType = contentType,
        fileName = null,
        state = state,
        attemptCount = 0,
        createdAt = 1L,
        updatedAt = 1L,
        lastError = null,
    )
}
