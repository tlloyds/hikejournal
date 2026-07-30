package com.hikejournal.app.data

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.util.UUID
import java.util.zip.ZipInputStream
import kotlin.coroutines.coroutineContext

private const val MAX_ZIP_MEDIA_ITEMS = 500
private const val MAX_ZIP_ENTRY_BYTES = 30L * 1024L * 1024L
private const val MAX_ZIP_TOTAL_BYTES = 2L * 1024L * 1024L * 1024L
private const val MIN_REMAINING_STORAGE_BYTES = 128L * 1024L * 1024L

data class GooglePhotosZipImport(
    val sessionId: String,
    val mediaUris: List<Uri>,
    val ignoredEntryCount: Int,
)

internal data class ZipExtractionResult(
    val mediaFiles: List<File>,
    val ignoredEntryCount: Int,
)

class GooglePhotosZipImporter(context: Context) {
    private val appContext = context.applicationContext
    private val importRoot = File(appContext.cacheDir, "google-photos-zips").apply { mkdirs() }

    suspend fun extract(uri: Uri): GooglePhotosZipImport = withContext(Dispatchers.IO) {
        discardExpiredImports()
        val sessionId = UUID.randomUUID().toString()
        val destination = sessionDirectory(sessionId).apply { mkdirs() }
        try {
            val input = appContext.contentResolver.openInputStream(uri)
                ?: throw IOException("The selected ZIP file could not be opened.")
            val result = input.use { extractSupportedMediaZip(it, destination) }
            GooglePhotosZipImport(
                sessionId = sessionId,
                mediaUris = result.mediaFiles.map(Uri::fromFile),
                ignoredEntryCount = result.ignoredEntryCount,
            )
        } catch (error: Exception) {
            destination.deleteRecursively()
            throw error
        }
    }

    suspend fun discard(sessionId: String) = withContext(Dispatchers.IO) {
        sessionDirectory(sessionId).deleteRecursively()
    }

    private fun sessionDirectory(sessionId: String): File {
        require(sessionId.matches(Regex("[a-f0-9-]{36}"))) { "Invalid ZIP import session." }
        return File(importRoot, sessionId)
    }

    private fun discardExpiredImports() {
        val cutoff = System.currentTimeMillis() - 24L * 60L * 60L * 1000L
        importRoot.listFiles()
            .orEmpty()
            .filter { it.isDirectory && it.lastModified() < cutoff }
            .forEach(File::deleteRecursively)
    }
}

internal suspend fun extractSupportedMediaZip(
    input: InputStream,
    destination: File,
    maxMediaItems: Int = MAX_ZIP_MEDIA_ITEMS,
    maxEntryBytes: Long = MAX_ZIP_ENTRY_BYTES,
    maxTotalBytes: Long = MAX_ZIP_TOTAL_BYTES,
): ZipExtractionResult {
    require(maxMediaItems > 0)
    require(maxEntryBytes > 0)
    require(maxTotalBytes >= maxEntryBytes)
    destination.mkdirs()

    val mediaFiles = mutableListOf<File>()
    var ignoredEntryCount = 0
    var totalBytes = 0L
    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)

    ZipInputStream(input.buffered()).use { zip ->
        while (true) {
            coroutineContext.ensureActive()
            val entry = zip.nextEntry ?: break
            if (entry.isDirectory) {
                zip.closeEntry()
                continue
            }

            val extension = supportedMediaExtension(entry.name)
            if (extension == null) {
                ignoredEntryCount += 1
                zip.closeEntry()
                continue
            }
            if (mediaFiles.size >= maxMediaItems) {
                throw IOException("This ZIP contains more than $maxMediaItems supported photos or videos.")
            }
            if (entry.size > maxEntryBytes) {
                throw IOException("Every photo or video in the ZIP must be 30 MB or smaller.")
            }

            val outputFile = File(destination, "${UUID.randomUUID()}.$extension")
            var entryBytes = 0L
            try {
                outputFile.outputStream().buffered().use { output ->
                    while (true) {
                        coroutineContext.ensureActive()
                        val count = zip.read(buffer)
                        if (count < 0) break
                        entryBytes += count
                        totalBytes += count
                        if (entryBytes > maxEntryBytes) {
                            throw IOException("Every photo or video in the ZIP must be 30 MB or smaller.")
                        }
                        if (totalBytes > maxTotalBytes) {
                            throw IOException("This ZIP expands beyond the 2 GB import safety limit.")
                        }
                        if (destination.usableSpace < MIN_REMAINING_STORAGE_BYTES) {
                            throw IOException("This phone needs more free storage to unpack the album safely.")
                        }
                        output.write(buffer, 0, count)
                    }
                }
                mediaFiles += outputFile
            } catch (error: Exception) {
                outputFile.delete()
                throw error
            } finally {
                zip.closeEntry()
            }
        }
    }

    if (mediaFiles.isEmpty()) {
        throw IOException("This ZIP does not contain supported photos or videos.")
    }
    return ZipExtractionResult(mediaFiles, ignoredEntryCount)
}

internal fun supportedMediaExtension(fileName: String): String? =
    fileName.substringAfterLast('/').substringAfterLast('.', "").lowercase().let { extension ->
        when (extension) {
            "jpg", "jpeg", "png", "heic", "heif", "webp", "gif",
            "mp4", "mov", "m4v", "3gp", "webm",
            -> extension
            else -> null
        }
    }

internal fun mediaContentType(fileName: String): String? =
    when (supportedMediaExtension(fileName)) {
        "jpg", "jpeg" -> "image/jpeg"
        "png" -> "image/png"
        "heic" -> "image/heic"
        "heif" -> "image/heif"
        "webp" -> "image/webp"
        "gif" -> "image/gif"
        "mp4" -> "video/mp4"
        "mov" -> "video/quicktime"
        "m4v" -> "video/x-m4v"
        "3gp" -> "video/3gpp"
        "webm" -> "video/webm"
        else -> null
    }
