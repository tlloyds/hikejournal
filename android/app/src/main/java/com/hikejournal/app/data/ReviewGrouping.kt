package com.hikejournal.app.data

import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.Duration
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

const val GROUPED_ID_MAX_PHOTOS = 8
const val REVIEW_BATCH_MAX_GROUPS_PER_JOB = 50
const val SMART_ID_MAX_DISTANCE_METERS = 12.0
const val SMART_ID_MAX_MINUTES = 2.0

data class ReviewPhotoGroup(
    val items: List<ReviewItem>,
    val timeSpanMinutes: Double,
    val maxDistanceMeters: Double,
) {
    val photoIds: List<String> get() = items.map { it.id }
}

/** Keep each companion job inside the API contract while preserving the review-plan order. */
fun chunkReviewBatchGroups(
    groups: List<List<String>>,
    maxGroupsPerJob: Int = REVIEW_BATCH_MAX_GROUPS_PER_JOB,
): List<List<List<String>>> {
    require(maxGroupsPerJob > 0) { "A review batch job must allow at least one group." }
    return groups.chunked(maxGroupsPerJob)
}

/** Mirrors the web review planner: same outing, same short time window, and close GPS points. */
fun buildReviewPhotoGroups(
    items: List<ReviewItem>,
    maxDistanceMeters: Double = SMART_ID_MAX_DISTANCE_METERS,
    maxMinutes: Double = SMART_ID_MAX_MINUTES,
    maxPhotos: Int = GROUPED_ID_MAX_PHOTOS,
): List<ReviewPhotoGroup> {
    val partitions = items.groupBy { it.hikeId ?: "standalone" }
    val groups = mutableListOf<ReviewPhotoGroup>()
    partitions.values.forEach { partition ->
        val compatibleGroups = mutableListOf<MutableList<ReviewItem>>()
        partition.sortedWith(compareBy<ReviewItem>({ reviewInstant(it) == null }, { reviewInstant(it) }, { it.id }))
            .forEach { item ->
                val instant = reviewInstant(item)
                val coordinates = item.photo.coordinates()
                if (instant == null || coordinates == null) {
                    compatibleGroups += mutableListOf(item)
                    return@forEach
                }
                val matchingGroup = compatibleGroups.firstOrNull { group ->
                    group.size < maxPhotos && fitsReviewGroup(
                        item,
                        group,
                        maxDistanceMeters = maxDistanceMeters,
                        maxMinutes = maxMinutes,
                    )
                }
                if (matchingGroup == null) compatibleGroups += mutableListOf(item)
                else matchingGroup += item
            }
        groups += compatibleGroups.map { summarizeReviewGroup(it) }
    }
    return groups.sortedWith(compareBy<ReviewPhotoGroup>({ reviewInstant(it.items.first()) == null }, { reviewInstant(it.items.first()) }, { it.items.first().id }))
}

fun splitReviewPhotoGroups(
    groups: List<ReviewPhotoGroup>,
    separatePhotoIds: Set<String>,
): List<ReviewPhotoGroup> {
    val splitGroups = mutableListOf<ReviewPhotoGroup>()
    groups.forEach { group ->
        val groupedItems = group.items.filterNot { it.id in separatePhotoIds }
        val separateItems = group.items.filter { it.id in separatePhotoIds }
        if (groupedItems.isNotEmpty()) splitGroups += summarizeReviewGroup(groupedItems)
        separateItems.forEach { item -> splitGroups += summarizeReviewGroup(listOf(item)) }
    }
    return splitGroups.sortedWith(compareBy<ReviewPhotoGroup>({ reviewInstant(it.items.first()) == null }, { reviewInstant(it.items.first()) }, { it.items.first().id }))
}

private fun fitsReviewGroup(
    item: ReviewItem,
    group: List<ReviewItem>,
    maxDistanceMeters: Double,
    maxMinutes: Double,
): Boolean {
    val candidateTime = reviewInstant(item) ?: return false
    val groupTimes = group.mapNotNull(::reviewInstant)
    if (groupTimes.isEmpty()) return false
    val minTime = minOf(candidateTime, groupTimes.minOrNull() ?: candidateTime)
    val maxTime = maxOf(candidateTime, groupTimes.maxOrNull() ?: candidateTime)
    val timeSpanMinutes = Duration.between(minTime, maxTime).toMillis() / 60_000.0
    if (timeSpanMinutes > maxMinutes) return false
    val candidateCoordinates = item.photo.coordinates() ?: return false
    return group.all { existing ->
        existing.photo.coordinates()?.let { distanceMeters(candidateCoordinates, it) <= maxDistanceMeters } == true
    }
}

private fun summarizeReviewGroup(items: List<ReviewItem>): ReviewPhotoGroup {
    val ordered = items.sortedWith(compareBy<ReviewItem>({ reviewInstant(it) == null }, { reviewInstant(it) }, { it.id }))
    val times = ordered.mapNotNull(::reviewInstant)
    val timeSpanMinutes = if (times.size > 1) {
        val minTime = times.minOrNull() ?: times.first()
        val maxTime = times.maxOrNull() ?: times.last()
        Duration.between(minTime, maxTime).toMillis() / 60_000.0
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
    return ReviewPhotoGroup(ordered, timeSpanMinutes, maxDistance)
}

private fun reviewInstant(item: ReviewItem): Instant? = item.photo.takenAt?.let { raw ->
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
