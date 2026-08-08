package com.hikejournal.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ConnectionUrlValidationTest {
    @Test
    fun `debug connection continues to accept a complete local http address`() {
        assertNull(connectionUrlError("http://192.168.0.157:8506", allowCleartext = true))
    }

    @Test
    fun `personal release rejects cleartext connection`() {
        assertEquals(
            "Personal releases require an https:// companion address.",
            connectionUrlError("http://192.168.0.157:8506", allowCleartext = false),
        )
    }

    @Test
    fun `personal release accepts hosted https address`() {
        assertNull(connectionUrlError("https://journal.example.com", allowCleartext = false))
    }

    @Test
    fun `connection address rejects embedded credentials`() {
        assertEquals(
            "Enter a complete https:// base address without credentials, a query, or a fragment.",
            connectionUrlError("https://secret@journal.example.com", allowCleartext = true),
        )
    }

    @Test
    fun `connection address rejects a query or fragment`() {
        val expected = "Enter a complete https:// base address without credentials, a query, or a fragment."
        assertEquals(expected, connectionUrlError("https://journal.example.com?key=value", true))
        assertEquals(expected, connectionUrlError("https://journal.example.com#fragment", true))
    }
}
