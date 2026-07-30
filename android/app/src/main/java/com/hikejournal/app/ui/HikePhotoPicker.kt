package com.hikejournal.app.ui

import android.content.Context
import android.content.Intent
import android.provider.MediaStore
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts.PickMultipleVisualMedia
import androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia

private const val REQUEST_LOCATION_METADATA_ACCESS =
    "android.provider.extra.REQUEST_LOCATION_METADATA_ACCESS"

internal class OriginalMetadataMultipleMediaPicker(
    maxItems: Int = Int.MAX_VALUE,
) : PickMultipleVisualMedia(maxItems) {
    override fun createIntent(context: Context, input: PickVisualMediaRequest): Intent =
        super.createIntent(context, input).apply {
            putExtra(MediaStore.EXTRA_ACCEPT_ORIGINAL_MEDIA_FORMAT, true)
            if (action == MediaStore.ACTION_PICK_IMAGES) {
                putExtra(REQUEST_LOCATION_METADATA_ACCESS, true)
            }
        }
}

internal fun hikeMediaPickerRequest(
    defaultTab: PickVisualMedia.DefaultTab,
): PickVisualMediaRequest = PickVisualMediaRequest.Builder()
    .setMediaType(PickVisualMedia.ImageAndVideo)
    .setDefaultTab(defaultTab)
    .build()
