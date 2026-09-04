package com.hikejournal.app.data

import android.content.Context
import android.content.Intent
import android.net.Uri

const val MAX_LOCAL_MEDIA_SELECTION = 500
private const val ALL_LOCAL_MEDIA_ALBUM_ID = "__all_local_media__"

/**
 * Keep picker grants alive while the upload sheet is open. Some picker providers do not
 * offer persistable grants, so failure is intentionally harmless; queuePhoto copies the
 * selected bytes into app-private storage before the temporary grant expires.
 */
fun persistSelectedMediaAccess(context: Context, uris: List<Uri>) {
    uris.forEach { uri ->
        runCatching {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION,
            )
        }
    }
}

data class LocalMediaItem(
    val uri: String,
    val displayName: String,
    val contentType: String,
    val albumId: String,
    val albumName: String,
    val takenAtMillis: Long,
    val sizeBytes: Long,
)

data class LocalMediaAlbum(
    val id: String,
    val name: String,
    val items: List<LocalMediaItem>,
) {
    val coverUri: String get() = items.firstOrNull()?.uri.orEmpty()
}

internal fun buildLocalMediaAlbums(items: List<LocalMediaItem>): List<LocalMediaAlbum> {
    if (items.isEmpty()) return emptyList()
    val sortedItems = items.sortedByDescending(LocalMediaItem::takenAtMillis)
    val physicalAlbums = sortedItems
        .groupBy(LocalMediaItem::albumId)
        .map { (albumId, albumItems) ->
            LocalMediaAlbum(
                id = albumId,
                name = albumItems.firstNotNullOfOrNull { it.albumName.takeIf(String::isNotBlank) }
                    ?: "Other",
                items = albumItems,
            )
        }
        .sortedWith(
            compareByDescending<LocalMediaAlbum> { it.items.maxOfOrNull(LocalMediaItem::takenAtMillis) ?: 0L }
                .thenBy(LocalMediaAlbum::name),
        )
    return listOf(
        LocalMediaAlbum(
            id = ALL_LOCAL_MEDIA_ALBUM_ID,
            name = "All phone media",
            items = sortedItems,
        ),
    ) + physicalAlbums
}

internal fun addLocalMediaSelection(
    current: List<String>,
    additions: List<String>,
    maxItems: Int = MAX_LOCAL_MEDIA_SELECTION,
): List<String> {
    if (maxItems <= 0) return emptyList()
    val selected = LinkedHashSet<String>()
    current.forEach { if (it.isNotBlank() && selected.size < maxItems) selected += it }
    additions.forEach { if (it.isNotBlank() && selected.size < maxItems) selected += it }
    return selected.toList()
}
