package com.hikejournal.app.data

import com.hikejournal.app.data.local.PendingOperationEntity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
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
    ) = PendingOperationEntity(
        id = id,
        kind = kind,
        entityId = entityId,
        parentId = parentId,
        payloadJson = payloadJson,
        localFilePath = null,
        contentType = null,
        fileName = null,
        state = state,
        attemptCount = 0,
        createdAt = 1L,
        updatedAt = 1L,
        lastError = null,
    )
}
