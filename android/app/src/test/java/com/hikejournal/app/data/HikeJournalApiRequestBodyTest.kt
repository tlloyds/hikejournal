package com.hikejournal.app.data

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okio.Buffer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Test

class HikeJournalApiRequestBodyTest {
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    @Test
    fun `bodyless post uses an empty json document`() {
        val body = postBodyOrEmpty(null, jsonMediaType)
        val buffer = Buffer()

        body.writeTo(buffer)

        assertEquals("{}", buffer.readUtf8())
        assertEquals(jsonMediaType, body.contentType())
    }

    @Test
    fun `post preserves a supplied request body`() {
        val supplied = "{\"force\":true}".toRequestBody(jsonMediaType)

        assertSame(supplied, postBodyOrEmpty(supplied, jsonMediaType))
    }
}
