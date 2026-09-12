package com.hikejournal.app.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HikeJournalApiAuthTest {
    @Test
    fun `a newer shared session is reused after another request refreshes`() {
        assertTrue(shouldReuseCurrentAuthSession("new-access", "expired-access"))
        assertFalse(shouldReuseCurrentAuthSession("expired-access", "expired-access"))
        assertFalse(shouldReuseCurrentAuthSession(null, "expired-access"))
        assertFalse(shouldReuseCurrentAuthSession("new-access", null))
    }
}
