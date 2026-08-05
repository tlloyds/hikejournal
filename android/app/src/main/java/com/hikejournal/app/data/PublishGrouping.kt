package com.hikejournal.app.data

import java.time.Duration
import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

const val GROUPED_PUBLISH_MAX_PHOTOS = 8
const val PUBLISH_MAX_DISTANCE_METERS = 50.0
const val PUBLISH_MAX_MINUTES = 15.0

data class PublishObservationGroup(
    val items: List<PublishItem>,
    val timeSpanMinutes: Double,
    val maxDistanceMeters: Double,
) {
    val photoIds: List<String> get() = items.map { it.photo.id }
    val observationIds: List<String> get() = items.map { it.id }
    val oversized: Boolean get() = items.size > GROUPED_PUBLISH_MAX_PHOTOS
}

/** Mirrors the web publishing planner: same species, outing, time window, and GPS area. */
fun buildPublishObservationGroups(
    items: List<PublishItem>,
    maxDistanceMeters: Double = PUBLISH_MAX_DISTANCE_METERS,
    maxMinutes: Double = PUBLISH_MAX_MINUTES,
): List<PublishObservationGroup> {
    val partitions = items.groupBy { item ->
        val scope = item.hikeId ?: "standalone"
        "$scope|${publishSpeciesKey(item)}"
    }
    val groups = mutableListOf<PublishObservationGroup>()
    partitions.values.forEach { partition ->
        val compatibleGroups = mutableListOf<MutableList<PublishItem>>()
        partition.sortedWith(compareBy<PublishItem>({ publishInstant(it) == null }, { publishInstant(it) }, { it.id }))
            .forEach { item ->
                val instant = publishInstant(item)
                if (instant == null || item.photo.coordinates() == null) {
                    compatibleGroups += mutableListOf(item)
                    return@forEach
                }
                val matchingGroup = compatibleGroups.firstOrNull { group ->
                    fitsPublishGroup(
                        item,
                        group,
                        maxDistanceMeters = maxDistanceMeters,
                        maxMinutes = maxMinutes,
                    )
                }
                if (matchingGroup == null) compatibleGroups += mutableListOf(item)
                else matchingGroup += item
            }
        groups += compatibleGroups.map(::summarizePublishGroup)
    }
    return groups.sortedWith(
        compareBy<PublishObservationGroup>({ publishInstant(it.items.first()) == null }, { publishInstant(it.items.first()) }, { it.items.first().id }),
    )
}

fun splitPublishObservationGroups(
    groups: List<PublishObservationGroup>,
    separatePhotoIds: Set<String>,
): List<PublishObservationGroup> {
    val splitGroups = mutableListOf<PublishObservationGroup>()
    groups.forEach { group ->
        val groupedItems = group.items.filterNot { it.photo.id in separatePhotoIds }
        val separateItems = group.items.filter { it.photo.id in separatePhotoIds }
        if (groupedItems.isNotEmpty()) splitGroups += summarizePublishGroup(groupedItems)
        separateItems.forEach { item -> splitGroups += summarizePublishGroup(listOf(item)) }
    }
    return splitGroups.sortedWith(
        compareBy<PublishObservationGroup>({ publishInstant(it.items.first()) == null }, { publishInstant(it.items.first()) }, { it.items.first().id }),
    )
}

private fun publishSpeciesKey(item: PublishItem): String = when {
    item.taxonId != null -> "taxon:${item.taxonId}"
    item.scientificName.isNotBlank() -> "scientific:${item.scientificName.trim().lowercase()}"
    item.commonName.isNotBlank() -> "common:${item.commonName.trim().lowercase()}"
    else -> "id:${item.id}"
}

private fun fitsPublishGroup(
    item: PublishItem,
    group: List<PublishItem>,
    maxDistanceMeters: Double,
    maxMinutes: Double,
): Boolean {
    val candidateTime = publishInstant(item) ?: return false
    val groupTimes = group.mapNotNull(::publishInstant)
    if (groupTimes.isEmpty()) return false
    val minTime = minOf(candidateTime, groupTimes.minOrNull() ?: candidateTime)
    val maxTime = maxOf(candidateTime, groupTimes.maxOrNull() ?: candidateTime)
    if (Duration.between(minTime, maxTime).toMillis() / 60_000.0 > maxMinutes) return false
    val candidateCoordinates = item.photo.coordinates() ?: return false
    return group.all { existing ->
        existing.photo.coordinates()?.let { distanceMeters(candidateCoordinates, it) <= maxDistanceMeters } == true
    }
}

private fun summarizePublishGroup(items: List<PublishItem>): PublishObservationGroup {
    val ordered = items.sortedWith(compareBy<PublishItem>({ publishInstant(it) == null }, { publishInstant(it) }, { it.id }))
    val times = ordered.mapNotNull(::publishInstant)
    val timeSpanMinutes = if (times.size > 1) {
        Duration.between(times.minOrNull() ?: times.first(), times.maxOrNull() ?: times.last()).toMillis() / 60_000.0
    } else {
        0.0
    }
    val maxDistance = ordered.indices.maxOfOrNull { leftIndex ->
        (leftIndex + 1 until ordered.size).maxOfOrNull { rightIndex ->
            val left = ordered[leftIndex].photo.coordinates()
            val right = ordered[rightIndex].photo.coordinates()
            if (left == null || right == null) 0.0 else distanceMeters(left, right)
        } ?: 0.0
    } ?: 0.0
    return PublishObservationGroup(ordered, timeSpanMinutes, maxDistance)
}

private fun publishInstant(item: PublishItem): Instant? = item.photo.takenAt?.let { raw ->
    runCatching { Instant.parse(raw) }.getOrNull()
        ?: runCatching { OffsetDateTime.parse(raw).toInstant() }.getOrNull()
        ?: runCatching { LocalDateTime.parse(raw).toInstant(ZoneOffset.UTC) }.getOrNull()
}

private fun Photo.coordinates(): Pair<Double, Double>? {
    val lat = latitude ?: return null
    val lng = longitude ?: return null
    if (lat !in -90.0..90.0 || lng !in -180.0..180.0) return null
    return lat to lng
}

private fun distanceMeters(left: Pair<Double, Double>, right: Pair<Double, Double>): Double {
    val earthRadiusMeters = 6_371_000.0
    val lat1 = Math.toRadians(left.first)
    val lng1 = Math.toRadians(left.second)
    val lat2 = Math.toRadians(right.first)
    val lng2 = Math.toRadians(right.second)
    val deltaLat = lat2 - lat1
    val deltaLng = lng2 - lng1
    val haversine = sin(deltaLat / 2).pow(2) + cos(lat1) * cos(lat2) * sin(deltaLng / 2).pow(2)
    return earthRadiusMeters * 2 * asin(sqrt(haversine.coerceIn(0.0, 1.0)))
}
