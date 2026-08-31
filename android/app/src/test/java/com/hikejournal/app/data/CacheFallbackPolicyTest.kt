package com.hikejournal.app.data

import java.io.IOException
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CacheFallbackPolicyTest {
    @Test
    fun `authentication failures do not masquerade as offline cached data`() {
        assertFalse(canUseCachedLoad(ApiException("Sign in with Google to continue.", 401)))
        assertFalse(canUseCachedLoad(ApiException("Forbidden", 403)))
    }

    @Test
    fun `temporary server failures can use the last known queue`() {
        assertTrue(canUseCachedLoad(ApiException("Request timed out", 408)))
        assertTrue(canUseCachedLoad(ApiException("Try again later", 425)))
        assertTrue(canUseCachedLoad(ApiException("Too many requests", 429)))
        assertTrue(canUseCachedLoad(ApiException("Server unavailable", 503)))
        assertTrue(canUseCachedLoad(IOException("No network")))
        assertFalse(canUseCachedLoad(IllegalStateException("Malformed response")))
    }
}
