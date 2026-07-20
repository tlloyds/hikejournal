package com.hikejournal.app.data

import android.content.Context
import org.json.JSONObject
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.offline.OfflineManager
import org.maplibre.android.offline.OfflineRegion
import org.maplibre.android.offline.OfflineRegionError
import org.maplibre.android.offline.OfflineRegionStatus
import org.maplibre.android.offline.OfflineTilePyramidRegionDefinition

data class OfflineMapPack(
    val id: Long,
    val name: String,
    val layer: String,
    val completedResources: Long,
    val requiredResources: Long,
    val bytes: Long,
    val complete: Boolean,
) {
    val progress: Float
        get() = if (requiredResources <= 0) 0f else (completedResources.toFloat() / requiredResources).coerceIn(0f, 1f)
}

class OfflineMapPacks(context: Context) {
    private val manager = OfflineManager.getInstance(context.applicationContext)

    fun list(onResult: (List<OfflineMapPack>) -> Unit, onError: (String) -> Unit) {
        manager.listOfflineRegions(object : OfflineManager.ListOfflineRegionsCallback {
            override fun onList(offlineRegions: Array<OfflineRegion>?) {
                val regions = offlineRegions.orEmpty()
                if (regions.isEmpty()) {
                    onResult(emptyList())
                    return
                }
                val results = mutableListOf<OfflineMapPack>()
                regions.forEach { region ->
                    region.getStatus(object : OfflineRegion.OfflineRegionStatusCallback {
                        override fun onStatus(status: OfflineRegionStatus?) {
                            if (status != null) results += region.toPack(status)
                            if (results.size == regions.size) onResult(results.sortedByDescending { it.id })
                        }

                        override fun onError(error: String?) {
                            onError(error ?: "Could not read an offline map pack.")
                        }
                    })
                }
            }

            override fun onError(error: String) = onError(error)
        })
    }

    fun download(
        name: String,
        layer: String,
        styleUrl: String,
        bounds: LatLngBounds,
        minZoom: Double,
        maxZoom: Double,
        pixelRatio: Float,
        onProgress: (OfflineMapPack) -> Unit,
        onComplete: (OfflineMapPack) -> Unit,
        onError: (String) -> Unit,
    ) {
        if (styleUrl.isBlank()) {
            onError("This map layer does not have an offline-enabled provider configured.")
            return
        }
        val definition = OfflineTilePyramidRegionDefinition(
            styleUrl,
            bounds,
            minZoom.coerceAtLeast(0.0),
            maxZoom.coerceAtLeast(minZoom),
            pixelRatio.coerceAtLeast(1f),
        )
        val metadata = JSONObject()
            .put("name", name)
            .put("layer", layer)
            .put("created_at", System.currentTimeMillis())
            .toString()
            .toByteArray()
        manager.createOfflineRegion(definition, metadata, object : OfflineManager.CreateOfflineRegionCallback {
            override fun onCreate(offlineRegion: OfflineRegion) {
                offlineRegion.setObserver(object : OfflineRegion.OfflineRegionObserver {
                    override fun onStatusChanged(status: OfflineRegionStatus) {
                        val pack = offlineRegion.toPack(status)
                        onProgress(pack)
                        if (status.isComplete) {
                            offlineRegion.setDownloadState(OfflineRegion.STATE_INACTIVE)
                            onComplete(pack)
                        }
                    }

                    override fun onError(error: OfflineRegionError) {
                        onError(error.message ?: "Map download failed.")
                    }

                    override fun mapboxTileCountLimitExceeded(limit: Long) {
                        onError("This map pack exceeded the provider's $limit-tile limit.")
                    }
                })
                offlineRegion.setDownloadState(OfflineRegion.STATE_ACTIVE)
            }

            override fun onError(error: String) = onError(error)
        })
    }

    fun delete(packId: Long, onComplete: () -> Unit, onError: (String) -> Unit) {
        manager.listOfflineRegions(object : OfflineManager.ListOfflineRegionsCallback {
            override fun onList(offlineRegions: Array<OfflineRegion>?) {
                val region = offlineRegions.orEmpty().firstOrNull { it.id == packId }
                if (region == null) {
                    onComplete()
                    return
                }
                region.delete(object : OfflineRegion.OfflineRegionDeleteCallback {
                    override fun onDelete() = onComplete()
                    override fun onError(error: String) = onError(error)
                })
            }

            override fun onError(error: String) = onError(error)
        })
    }
}

private fun OfflineRegion.toPack(status: OfflineRegionStatus): OfflineMapPack {
    val metadataJson = runCatching { JSONObject(String(metadata)) }.getOrElse { JSONObject() }
    return OfflineMapPack(
        id = id,
        name = metadataJson.optString("name", "Field map"),
        layer = metadataJson.optString("layer", "trail"),
        completedResources = status.completedResourceCount,
        requiredResources = status.requiredResourceCount,
        bytes = status.completedResourceSize,
        complete = status.isComplete,
    )
}
