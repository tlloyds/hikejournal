package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class LocalMediaLibraryTest {
    @Test
    fun groupsPhoneMediaIntoRecentFirstAlbums() {
        val olderCamera = media(
            uri = "content://media/images/1",
            albumId = "camera",
            albumName = "Camera",
            takenAt = 100,
        )
        val newestCamera = media(
            uri = "content://media/images/2",
            albumId = "camera",
            albumName = "Camera",
            takenAt = 300,
        )
        val screenshot = media(
            uri = "content://media/images/3",
            albumId = "screenshots",
            albumName = "Screenshots",
            takenAt = 200,
        )

        val albums = buildLocalMediaAlbums(listOf(olderCamera, newestCamera, screenshot))

        assertEquals(listOf("All phone media", "Camera", "Screenshots"), albums.map(LocalMediaAlbum::name))
        assertEquals(
            listOf(newestCamera.uri, screenshot.uri, olderCamera.uri),
            albums.first().items.map(LocalMediaItem::uri),
        )
        assertEquals(listOf(newestCamera.uri, olderCamera.uri), albums[1].items.map(LocalMediaItem::uri))
    }

    @Test
    fun selectionPreservesOrderDeduplicatesAndHonorsBatchLimit() {
        val selected = addLocalMediaSelection(
            current = listOf("content://media/1", "content://media/2"),
            additions = listOf("content://media/2", "content://media/3", "content://media/4"),
            maxItems = 3,
        )

        assertEquals(
            listOf("content://media/1", "content://media/2", "content://media/3"),
            selected,
        )
    }

    private fun media(
        uri: String,
        albumId: String,
        albumName: String,
        takenAt: Long,
    ): LocalMediaItem = LocalMediaItem(
        uri = uri,
        displayName = uri.substringAfterLast('/'),
        contentType = "image/jpeg",
        albumId = albumId,
        albumName = albumName,
        takenAtMillis = takenAt,
        sizeBytes = 1_024,
    )
}
