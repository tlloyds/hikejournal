package com.hikejournal.app.data

import org.junit.Assert.assertEquals
import org.junit.Test

class QueuedPhotoPreparationTest {
    @Test
    fun `large landscape photos match the server upload dimensions`() {
        assertEquals(1600 to 1200, constrainedPhotoDimensions(4032, 3024))
    }

    @Test
    fun `large portrait photos preserve their aspect ratio`() {
        assertEquals(1200 to 1600, constrainedPhotoDimensions(3024, 4032))
    }

    @Test
    fun `smaller photos are not enlarged`() {
        assertEquals(1280 to 720, constrainedPhotoDimensions(1280, 720))
    }
}
