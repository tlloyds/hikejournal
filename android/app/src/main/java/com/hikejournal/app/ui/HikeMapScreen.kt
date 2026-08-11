@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.hikejournal.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Layers
import androidx.compose.material.icons.rounded.PhotoLibrary
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.Sighting
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.TrailText

@Composable
fun HikeMapScreen(
    hike: Hike?,
    focusedPhoto: Photo?,
    onBack: () -> Unit,
    onOpenPhoto: (Photo) -> Unit,
) {
    val sightings = remember(hike, focusedPhoto) { hikeMapSightings(hike, focusedPhoto) }
    val photosById = remember(hike, focusedPhoto) {
        buildList {
            addAll(hike?.photos.orEmpty())
            if (focusedPhoto != null && none { it.id == focusedPhoto.id }) add(focusedPhoto)
        }.associateBy { it.id }
    }
    var selected by remember(focusedPhoto?.id, sightings) {
        mutableStateOf(sightings.firstOrNull { it.id == focusedPhoto?.id })
    }
    var layerMode by remember { mutableStateOf(MapLayerMode.Satellite) }
    val routeSegments = hike?.routeSegments.orEmpty()

    Box(Modifier.fillMaxSize().background(Moss)) {
        HikeJournalMap(
            sightings = sightings,
            selectedSighting = selected,
            layerMode = layerMode,
            onSelect = { selected = it },
            onViewportChanged = {},
            routeSegments = routeSegments,
            focusedSightingId = focusedPhoto?.id,
            modifier = Modifier.fillMaxSize(),
        )

        Row(
            Modifier
                .fillMaxWidth()
                .background(Color(0xF2183A2D))
                .statusBarsPadding()
                .padding(start = 8.dp, end = 8.dp, top = 8.dp, bottom = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back", tint = Paper)
            }
            Column(Modifier.weight(1f).padding(horizontal = 4.dp)) {
                Text(
                    "HikeJournal",
                    style = MaterialTheme.typography.titleMedium,
                    color = Color(0xFFB7C8B5),
                )
                Text(
                    hike?.title?.takeIf { it.isNotBlank() } ?: "Photo location",
                    style = MaterialTheme.typography.headlineSmall,
                    color = Paper,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    hikeMapSummary(
                        routeSegments.size,
                        sightings.count { it.url.isNotBlank() },
                        sightings.count { it.url.isBlank() },
                    ),
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFFB7C8B5),
                )
                MapRouteLegend(modifier = Modifier.padding(top = 4.dp), compact = true)
            }
            TextButton(
                onClick = {
                    layerMode = if (layerMode == MapLayerMode.Trail) {
                        MapLayerMode.Satellite
                    } else {
                        MapLayerMode.Trail
                    }
                },
            ) {
                Icon(Icons.Rounded.Layers, null, tint = Paper, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(5.dp))
                Text(
                    if (layerMode == MapLayerMode.Trail) "Satellite" else "Trail",
                    color = Paper,
                )
            }
        }

        if (routeSegments.isEmpty() && sightings.isEmpty()) {
            Column(
                Modifier
                    .align(Alignment.Center)
                    .background(Paper, RoundedCornerShape(6.dp))
                    .padding(horizontal = 24.dp, vertical = 20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Icon(Icons.Rounded.PhotoLibrary, null, tint = TrailText)
                Text(
                    "Nothing to plot yet",
                    style = MaterialTheme.typography.titleMedium,
                    color = Ink,
                    modifier = Modifier.padding(top = 8.dp),
                )
                Text(
                    "This outing has no saved route or geotagged photos.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 3.dp),
                )
            }
        }

        AnimatedVisibility(
            visible = selected != null,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(horizontal = 12.dp, vertical = 18.dp),
            enter = slideInVertically { it } + fadeIn(),
            exit = slideOutVertically { it } + fadeOut(),
        ) {
            selected?.let { sighting ->
                HikePhotoMapInspector(
                    sighting = sighting,
                    onDismiss = { selected = null },
                    onOpenPhoto = {
                        photosById[sighting.id]?.let(onOpenPhoto)
                    },
                )
            }
        }
    }
}

@Composable
private fun HikePhotoMapInspector(
    sighting: Sighting,
    onDismiss: () -> Unit,
    onOpenPhoto: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .background(Paper, RoundedCornerShape(8.dp))
            .padding(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (sighting.url.isNotBlank()) {
            AsyncImage(
                model = sighting.url,
                contentDescription = sighting.caption.ifBlank { "Geotagged hike photo" },
                contentScale = ContentScale.Crop,
                modifier = Modifier.size(88.dp).background(Moss),
            )
        } else {
            Box(Modifier.size(64.dp).background(Moss), contentAlignment = Alignment.Center) {
                Text("MARK", style = MaterialTheme.typography.labelSmall, color = Paper)
            }
        }
        Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
            Text(
                sighting.speciesName.ifBlank {
                    sighting.caption.ifBlank { "Geotagged field photo" }
                },
                style = MaterialTheme.typography.titleMedium,
                color = Ink,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (sighting.locationName.isNotBlank()) {
                Text(
                    sighting.locationName,
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            if (sighting.url.isNotBlank()) {
                Button(
                    onClick = onOpenPhoto,
                    modifier = Modifier.padding(top = 7.dp).height(38.dp),
                ) {
                    Icon(Icons.Rounded.PhotoLibrary, null, Modifier.size(17.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("View photo")
                }
            } else if (sighting.caption.isNotBlank()) {
                Text(sighting.caption, style = MaterialTheme.typography.bodyMedium, color = InkMuted)
            }
        }
        TextButton(onClick = onDismiss) {
            Text("Close")
        }
    }
}

internal fun hikeMapSightings(hike: Hike?, focusedPhoto: Photo?): List<Sighting> {
    val photos = buildList {
        addAll(hike?.photos.orEmpty())
        if (focusedPhoto != null && none { it.id == focusedPhoto.id }) add(focusedPhoto)
    }
    val photoSightings = photos
        .asSequence()
        .filter { it.latitude != null && it.longitude != null }
        .distinctBy { it.id }
        .map { photo ->
            val primary = photo.species.firstOrNull { it.isPrimary } ?: photo.species.firstOrNull()
            Sighting(
                id = photo.id,
                hikeId = photo.hikeId ?: hike?.id,
                hikeTitle = hike?.title ?: "Photo location",
                hikeDate = hike?.hikeDate.orEmpty(),
                locationName = hike?.locationName.orEmpty(),
                url = photo.url,
                caption = photo.caption,
                takenAt = photo.takenAt,
                latitude = requireNotNull(photo.latitude),
                longitude = requireNotNull(photo.longitude),
                speciesName = primary?.commonName.orEmpty(),
                scientificName = primary?.scientificName.orEmpty(),
                confirmed = photo.species.any { it.status == "confirmed" },
            )
        }
        .toList()
    val markSightings = hike?.fieldMarks.orEmpty().map { mark ->
        Sighting(
            id = mark.id,
            hikeId = mark.hikeId,
            hikeTitle = hike?.title ?: "Field Mark",
            hikeDate = hike?.hikeDate.orEmpty(),
            locationName = hike?.locationName.orEmpty(),
            url = "",
            caption = mark.note,
            takenAt = mark.markedAt,
            latitude = mark.latitude,
            longitude = mark.longitude,
            speciesName = when (mark.markType) {
                "wildlife" -> "Wildlife"
                "plant" -> "Plant"
                "trail_condition" -> "Trail condition"
                "water" -> "Water"
                "campsite" -> "Campsite"
                "hazard" -> "Hazard"
                else -> "Field note"
            },
            scientificName = "Field Mark",
            confirmed = true,
        )
    }
    return (photoSightings + markSightings).distinctBy(Sighting::id)
}

internal fun hikeMapSummary(routeCount: Int, photoCount: Int, markCount: Int = 0): String {
    val routes = "$routeCount ROUTE${if (routeCount == 1) "" else "S"}"
    val photos = "$photoCount GEOTAGGED PHOTO${if (photoCount == 1) "" else "S"}"
    val marks = if (markCount > 0) " · $markCount FIELD MARK${if (markCount == 1) "" else "S"}" else ""
    return "$routes · $photos$marks"
}
