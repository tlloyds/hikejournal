package com.hikejournal.app.ui

import androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia
import org.junit.Assert.assertSame
import org.junit.Test

class HikePhotoPickerTest {
    @Test
    fun albumRequestOpensTheSystemPickerOnAlbums() {
        val request = hikeMediaPickerRequest(PickVisualMedia.DefaultTab.AlbumsTab)

        assertSame(PickVisualMedia.DefaultTab.AlbumsTab, request.defaultTab)
        assertSame(PickVisualMedia.ImageAndVideo, request.mediaType)
    }
}
