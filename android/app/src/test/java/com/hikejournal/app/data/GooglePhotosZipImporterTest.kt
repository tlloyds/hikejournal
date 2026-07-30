package com.hikejournal.app.data

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class GooglePhotosZipImporterTest {
    @Test
    fun extractsNestedMediaAndIgnoresSidecarsWithoutTrustingEntryPaths() = runBlocking {
        val destination = Files.createTempDirectory("hikejournal-zip-test").toFile()
        try {
            val result = extractSupportedMediaZip(
                input = zipBytes(
                    "Album/first.JPG" to "first".toByteArray(),
                    "Album/first.JPG.json" to "{}".toByteArray(),
                    "../../outside.png" to "second".toByteArray(),
                ).inputStream(),
                destination = destination,
            )

            assertEquals(2, result.mediaFiles.size)
            assertEquals(1, result.ignoredEntryCount)
            assertTrue(result.mediaFiles.all { it.parentFile?.canonicalFile == destination.canonicalFile })
            assertTrue(result.mediaFiles.any { it.extension == "jpg" })
            assertTrue(result.mediaFiles.any { it.extension == "png" })
            assertTrue(result.mediaFiles.all(File::isFile))
        } finally {
            destination.deleteRecursively()
        }
    }

    @Test
    fun rejectsArchivesOverTheMediaItemLimit() = runBlocking {
        val destination = Files.createTempDirectory("hikejournal-zip-limit").toFile()
        try {
            expectZipFailure {
                extractSupportedMediaZip(
                    input = zipBytes(
                        "one.jpg" to byteArrayOf(1),
                        "two.jpg" to byteArrayOf(2),
                    ).inputStream(),
                    destination = destination,
                    maxMediaItems = 1,
                )
            }
        } finally {
            destination.deleteRecursively()
        }
    }

    @Test
    fun rejectsAnEntryThatExpandsPastThePerFileLimit() = runBlocking {
        val destination = Files.createTempDirectory("hikejournal-zip-size").toFile()
        try {
            expectZipFailure {
                extractSupportedMediaZip(
                    input = zipBytes("large.jpg" to ByteArray(32) { 1 }).inputStream(),
                    destination = destination,
                    maxEntryBytes = 16,
                    maxTotalBytes = 64,
                )
            }
        } finally {
            destination.deleteRecursively()
        }
    }

    @Test
    fun recognizesGooglePhotosMediaExtensions() {
        assertEquals("jpg", supportedMediaExtension("Takeout/Album/IMG_1.JPG"))
        assertEquals("video/quicktime", mediaContentType("Takeout/Album/clip.MOV"))
        assertEquals("image/heic", mediaContentType("photo.heic"))
        assertEquals(null, supportedMediaExtension("photo.jpg.json"))
    }

    private suspend fun expectZipFailure(block: suspend () -> Unit) {
        try {
            block()
            fail("Expected ZIP extraction to fail.")
        } catch (_: IOException) {
            // Expected.
        }
    }

    private fun zipBytes(vararg entries: Pair<String, ByteArray>): ByteArray {
        val output = ByteArrayOutputStream()
        ZipOutputStream(output).use { zip ->
            entries.forEach { (name, bytes) ->
                zip.putNextEntry(ZipEntry(name))
                ByteArrayInputStream(bytes).copyTo(zip)
                zip.closeEntry()
            }
        }
        return output.toByteArray()
    }
}
