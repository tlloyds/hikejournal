package com.hikejournal.app.data

import android.Manifest
import android.content.ContentUris
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.provider.MediaStore
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

const val MAX_LOCAL_MEDIA_SELECTION = 500
private const val MAX_LOCAL_MEDIA_BYTES = 30L * 1024L * 1024L
private const val ALL_LOCAL_MEDIA_ALBUM_ID = "__all_local_media__"

data class LocalMediaAccess(
    val canReadImages: Boolean,
    val canReadVideos: Boolean,
    val canReadLocations: Boolean,
    val hasFullLibraryAccess: Boolean,
) {
    val canReadMedia: Boolean get() = canReadImages || canReadVideos
    val readyForOriginals: Boolean get() = canReadMedia && canReadLocations
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

fun requiredLocalMediaPermissions(): Array<String> = buildList {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        add(Manifest.permission.READ_MEDIA_IMAGES)
        add(Manifest.permission.READ_MEDIA_VIDEO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            add(Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED)
        }
    } else {
        add(Manifest.permission.READ_EXTERNAL_STORAGE)
    }
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        add(Manifest.permission.ACCESS_MEDIA_LOCATION)
    }
}.toTypedArray()

fun localMediaAccess(context: Context): LocalMediaAccess {
    fun granted(permission: String): Boolean =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    val legacyRead = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU &&
        granted(Manifest.permission.READ_EXTERNAL_STORAGE)
    val fullImages = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
        granted(Manifest.permission.READ_MEDIA_IMAGES)
    val fullVideos = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
        granted(Manifest.permission.READ_MEDIA_VIDEO)
    val partial = Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE &&
        granted(Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED)
    val location = Build.VERSION.SDK_INT < Build.VERSION_CODES.Q ||
        granted(Manifest.permission.ACCESS_MEDIA_LOCATION)

    return LocalMediaAccess(
        canReadImages = legacyRead || fullImages || partial,
        canReadVideos = legacyRead || fullVideos || partial,
        canReadLocations = location,
        hasFullLibraryAccess = legacyRead || (fullImages && fullVideos),
    )
}

suspend fun loadLocalMediaLibrary(
    context: Context,
    access: LocalMediaAccess = localMediaAccess(context),
): List<LocalMediaAlbum> {
    if (!access.canReadMedia) return emptyList()
    val items = withContext(Dispatchers.IO) {
        buildList {
            if (access.canReadImages) addAll(queryLocalMedia(context, isVideo = false))
            if (access.canReadVideos) addAll(queryLocalMedia(context, isVideo = true))
        }
    }
    return withContext(Dispatchers.Default) { buildLocalMediaAlbums(items) }
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

private fun queryLocalMedia(context: Context, isVideo: Boolean): List<LocalMediaItem> {
    val collection = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && isVideo ->
            MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL)
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q ->
            MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL)
        isVideo -> MediaStore.Video.Media.EXTERNAL_CONTENT_URI
        else -> MediaStore.Images.Media.EXTERNAL_CONTENT_URI
    }
    val projection = arrayOf(
        MediaStore.MediaColumns._ID,
        MediaStore.MediaColumns.DISPLAY_NAME,
        MediaStore.MediaColumns.MIME_TYPE,
        MediaStore.MediaColumns.SIZE,
        MediaStore.Images.ImageColumns.DATE_TAKEN,
        MediaStore.MediaColumns.DATE_ADDED,
        MediaStore.Images.ImageColumns.BUCKET_ID,
        MediaStore.Images.ImageColumns.BUCKET_DISPLAY_NAME,
    )
    val selection = "${MediaStore.MediaColumns.SIZE} > 0 AND ${MediaStore.MediaColumns.SIZE} <= ?"
    val selectionArgs = arrayOf(MAX_LOCAL_MEDIA_BYTES.toString())

    return runCatching {
        context.contentResolver.query(
            collection,
            projection,
            selection,
            selectionArgs,
            "${MediaStore.Images.ImageColumns.DATE_TAKEN} DESC, ${MediaStore.MediaColumns.DATE_ADDED} DESC",
        )?.use { cursor ->
            val idColumn = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns._ID)
            val nameColumn = cursor.getColumnIndex(MediaStore.MediaColumns.DISPLAY_NAME)
            val typeColumn = cursor.getColumnIndex(MediaStore.MediaColumns.MIME_TYPE)
            val sizeColumn = cursor.getColumnIndex(MediaStore.MediaColumns.SIZE)
            val takenColumn = cursor.getColumnIndex(MediaStore.Images.ImageColumns.DATE_TAKEN)
            val addedColumn = cursor.getColumnIndex(MediaStore.MediaColumns.DATE_ADDED)
            val bucketIdColumn = cursor.getColumnIndex(MediaStore.Images.ImageColumns.BUCKET_ID)
            val bucketNameColumn = cursor.getColumnIndex(MediaStore.Images.ImageColumns.BUCKET_DISPLAY_NAME)
            buildList {
                while (cursor.moveToNext()) {
                    val id = cursor.getLong(idColumn)
                    val contentUri = ContentUris.withAppendedId(collection, id)
                    val dateTaken = cursor.longOrNull(takenColumn)
                        ?: cursor.longOrNull(addedColumn)?.times(1_000L)
                        ?: 0L
                    val bucketId = cursor.stringOrNull(bucketIdColumn)
                        ?: "other-${if (isVideo) "video" else "image"}"
                    add(
                        LocalMediaItem(
                            uri = contentUri.toString(),
                            displayName = cursor.stringOrNull(nameColumn)
                                ?: "${if (isVideo) "video" else "photo"}-$id",
                            contentType = cursor.stringOrNull(typeColumn)
                                ?: if (isVideo) "video/mp4" else "image/jpeg",
                            albumId = bucketId,
                            albumName = cursor.stringOrNull(bucketNameColumn) ?: "Other",
                            takenAtMillis = dateTaken,
                            sizeBytes = cursor.longOrNull(sizeColumn) ?: 0L,
                        )
                    )
                }
            }
        }.orEmpty()
    }.getOrDefault(emptyList())
}

private fun android.database.Cursor.stringOrNull(column: Int): String? =
    if (column < 0 || isNull(column)) null else getString(column)

private fun android.database.Cursor.longOrNull(column: Int): Long? =
    if (column < 0 || isNull(column)) null else getLong(column)
