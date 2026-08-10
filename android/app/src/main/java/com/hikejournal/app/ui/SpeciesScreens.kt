@file:OptIn(
    androidx.compose.foundation.ExperimentalFoundationApi::class,
    androidx.compose.material3.ExperimentalMaterial3Api::class,
)

package com.hikejournal.app.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.CloudOff
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Edit
import androidx.compose.material.icons.rounded.KeyboardArrowDown
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.ColorMatrix
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.core.content.ContextCompat
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.hikejournal.app.data.Encounter
import com.hikejournal.app.data.DiscoveryArea
import com.hikejournal.app.data.DiscoveryTaxon
import com.hikejournal.app.data.FieldQuest
import com.hikejournal.app.data.Hike
import com.hikejournal.app.data.NearbySpecies
import com.hikejournal.app.data.ObservationTypeFilter
import com.hikejournal.app.data.Photo
import com.hikejournal.app.data.QuestSightingsMap
import com.hikejournal.app.data.SpeciesRecord
import com.hikejournal.app.data.SpeciesSort
import com.hikejournal.app.data.filterDiscoveryAreas
import com.hikejournal.app.data.filterSpeciesByObservationType
import com.hikejournal.app.data.sortSpeciesRecords
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.TrailText
import com.hikejournal.app.ui.theme.FernText
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

private enum class SpeciesMode(val label: String) {
    Collection("Collection"),
    Nearby("Nearby"),
    Quests("Field Quests"),
}

private const val QuestFocusLimit = 10
private const val StandardNearbyLimit = 50
private const val ExpandedNearbyLimit = 100

data class SpeciesCollectionPreferences(
    val query: String = "",
    val sort: SpeciesSort = SpeciesSort.Alphabetical,
    val selectedHikeId: String? = null,
    val observationType: ObservationTypeFilter = ObservationTypeFilter.All,
)

@Composable
fun SpeciesIndexScreen(
    species: List<SpeciesRecord>,
    hikes: List<Hike>,
    discoveryAreas: List<DiscoveryArea>,
    nearbySpecies: NearbySpecies?,
    quests: List<FieldQuest>,
    questMapQuest: FieldQuest?,
    questMapTaxon: DiscoveryTaxon?,
    questSightingsMap: QuestSightingsMap?,
    initialNearbyAreaName: String?,
    loading: Boolean,
    discoveryLoading: Boolean,
    savingQuest: Boolean,
    offline: Boolean,
    discoveryNotice: String?,
    questMapLoading: Boolean,
    questMapNotice: String?,
    onRefresh: () -> Unit,
    onRefreshDiscovery: () -> Unit,
    onLoadNearby: (String?, String, Int, List<String>, Double?, Double?, Int) -> Unit,
    onSaveQuest: (String, String?, List<Long>, (FieldQuest) -> Unit) -> Unit,
    onSaveQuestFocus: (FieldQuest, List<Long>) -> Unit,
    onRenameQuest: (FieldQuest, String) -> Unit,
    onArchiveQuest: (FieldQuest) -> Unit,
    onDeleteQuest: (FieldQuest) -> Unit,
    onOpenNearbyMap: (NearbySpecies, DiscoveryTaxon) -> Unit,
    onOpenQuestMap: (FieldQuest, DiscoveryTaxon) -> Unit,
    onRefreshQuestMap: () -> Unit,
    onCloseQuestMap: () -> Unit,
    onInitialAreaConsumed: () -> Unit,
    collectionPreferences: SpeciesCollectionPreferences,
    onCollectionPreferencesChange: (SpeciesCollectionPreferences) -> Unit,
    onOpenSpecies: (String, List<SpeciesRecord>, String) -> Unit,
) {
    var mode by remember { mutableStateOf(SpeciesMode.Collection) }
    var query by remember { mutableStateOf(collectionPreferences.query) }
    var speciesSort by remember { mutableStateOf(collectionPreferences.sort) }
    var speciesSortOpen by remember { mutableStateOf(false) }
    var selectedHikeId by remember { mutableStateOf(collectionPreferences.selectedHikeId) }
    var filterOpen by remember { mutableStateOf(false) }
    var observationType by remember { mutableStateOf(collectionPreferences.observationType) }
    var observationTypeFilterOpen by remember { mutableStateOf(false) }
    var areaSearch by remember { mutableStateOf("") }
    var selectedAreaId by remember { mutableStateOf<String?>(null) }
    var targetDate by remember { mutableStateOf(LocalDate.now().toString()) }
    var radiusKm by remember { mutableIntStateOf(10) }
    var iconicTaxa by remember { mutableStateOf(emptyList<String>()) }
    var nearbyLifeFilterOpen by remember { mutableStateOf(false) }
    var focusTaxonIds by remember { mutableStateOf(emptyList<Long>()) }
    var linkedQuestHikeId by remember { mutableStateOf<String?>(null) }
    var selectedQuestId by remember { mutableStateOf<String?>(null) }
    var showArchivedQuests by remember { mutableStateOf(false) }
    var locationNotice by remember { mutableStateOf<String?>(null) }
    var editingQuestId by remember { mutableStateOf<String?>(null) }
    var previewTaxon by remember { mutableStateOf<DiscoveryTaxon?>(null) }
    var pendingDeleteQuest by remember { mutableStateOf<FieldQuest?>(null) }
    var renamingQuest by remember { mutableStateOf<FieldQuest?>(null) }
    var questNameDraft by remember { mutableStateOf("") }
    var nearbyResultLimit by remember { mutableIntStateOf(StandardNearbyLimit) }
    val context = LocalContext.current
    val selectedArea = discoveryAreas.firstOrNull { it.id == selectedAreaId }
    val visibleAreas = filterDiscoveryAreas(discoveryAreas, areaSearch)
    val visibleQuests = quests.filter { (it.status == "archived") == showArchivedQuests }
    val selectedQuest = visibleQuests.firstOrNull { it.id == selectedQuestId }
        ?: visibleQuests.singleOrNull()
    if (questMapQuest != null && questMapTaxon != null) {
        QuestSightingsMapScreen(
            quest = questMapQuest,
            taxon = questMapTaxon,
            mapData = questSightingsMap,
            loading = questMapLoading,
            notice = questMapNotice,
            onBack = onCloseQuestMap,
            onRefresh = onRefreshQuestMap,
        )
        return
    }
    LaunchedEffect(nearbySpecies) {
        val availableIds = nearbySpecies?.taxa?.mapTo(mutableSetOf()) { it.taxonId }.orEmpty()
        focusTaxonIds = focusTaxonIds.filter { it in availableIds }
        nearbyResultLimit = nearbySpecies?.resultLimit ?: StandardNearbyLimit
    }
    LaunchedEffect(initialNearbyAreaName, discoveryAreas) {
        if (initialNearbyAreaName != null && (initialNearbyAreaName.isBlank() || discoveryAreas.isNotEmpty())) {
            mode = SpeciesMode.Nearby
            areaSearch = initialNearbyAreaName
            selectedAreaId = discoveryAreas.firstOrNull {
                it.name.equals(initialNearbyAreaName, ignoreCase = true)
            }?.id
            onInitialAreaConsumed()
        }
    }
    val locationPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { result ->
        if (result.values.any { it }) {
            requestOneShotLocation(
                context = context,
                onLocation = { location ->
                    locationNotice = null
                    onLoadNearby(
                        null,
                        targetDate,
                        radiusKm,
                        iconicTaxa,
                        location.latitude,
                        location.longitude,
                        nearbyResultLimit,
                    )
                },
                onUnavailable = { locationNotice = "A current location was not available. Choose a saved trail instead." },
            )
        } else {
            locationNotice = "Location access was declined. You can still choose any saved trail."
        }
    }
    val scopedSpecies = species.mapNotNull { record ->
        if (selectedHikeId == null) {
            record
        } else {
            record.hikeEncounterCounts[selectedHikeId]?.let { encounterCount ->
                record.copy(
                    encounterCount = encounterCount,
                    hikeCount = 1,
                    coverUrl = record.hikeCoverUrls[selectedHikeId] ?: record.coverUrl,
                    latestSeen = record.hikeLatestSeen[selectedHikeId] ?: record.latestSeen,
                )
            }
        }
    }
    val typeScopedSpecies = filterSpeciesByObservationType(scopedSpecies, observationType)
    val filtered = typeScopedSpecies
        .filter {
            query.isBlank() || it.commonName.contains(query, ignoreCase = true) ||
                it.scientificName.contains(query, ignoreCase = true)
        }
        .let { items -> sortSpeciesRecords(items, speciesSort) }
    val browseContext = buildList {
        hikes.firstOrNull { it.id == selectedHikeId }?.title?.let(::add)
        if (observationType != ObservationTypeFilter.All) add(observationType.label)
        if (query.isNotBlank()) add("\u201c$query\u201d")
        add(speciesSort.label)
    }.joinToString(" \u00b7 ")
    val encounterCount = typeScopedSpecies.sumOf { it.encounterCount }
    val headerCount = when (mode) {
        SpeciesMode.Collection -> "${typeScopedSpecies.size} SPECIES · $encounterCount ENCOUNTERS"
        SpeciesMode.Nearby -> nearbySpecies?.let {
            "${it.progress.collectedCount} OF ${it.progress.totalCount} COLLECTED"
        } ?: "SEASONAL FIELD LIST"
        SpeciesMode.Quests -> "${visibleQuests.size} ${if (showArchivedQuests) "ARCHIVED" else "ACTIVE"} QUESTS"
    }

    Box(Modifier.fillMaxSize().background(Parchment)) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 104.dp),
        ) {
        item {
            Column(
                Modifier.fillMaxWidth().background(Moss).statusBarsPadding().padding(start = 20.dp, end = 8.dp, top = 17.dp, bottom = 22.dp),
            ) {
                Row(verticalAlignment = Alignment.Top) {
                    Column(Modifier.weight(1f)) {
                        Text("HikeJournal", style = MaterialTheme.typography.headlineSmall, color = Color(0xFFB7C8B5))
                        Text(
                            when (mode) {
                                SpeciesMode.Collection -> "Field guide"
                                SpeciesMode.Nearby -> "Nearby field list"
                                SpeciesMode.Quests -> "Field quests"
                            },
                            style = MaterialTheme.typography.displayMedium,
                            color = Paper,
                        )
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(headerCount, style = MaterialTheme.typography.labelSmall, color = Color(0xFFB7C8B5))
                            if (offline) {
                                Spacer(Modifier.width(9.dp))
                                Icon(Icons.Rounded.CloudOff, null, tint = Trail, modifier = Modifier.size(15.dp))
                            }
                        }
                    }
                    IconButton(
                        onClick = {
                            if (mode == SpeciesMode.Collection) onRefresh() else onRefreshDiscovery()
                        },
                        enabled = !loading && !discoveryLoading,
                    ) {
                        if (loading || discoveryLoading) CircularProgressIndicator(Modifier.size(20.dp), color = Paper, strokeWidth = 2.dp)
                        else Icon(Icons.Rounded.Refresh, "Refresh species", tint = Paper)
                    }
                }
            }
        }
        item {
            SpeciesModeTabs(
                mode = mode,
                onMode = {
                    if (it == SpeciesMode.Quests && mode != SpeciesMode.Quests) selectedQuestId = null
                    mode = it
                },
            )
        }
        if (!discoveryNotice.isNullOrBlank() && mode != SpeciesMode.Collection) {
            item {
                Text(
                    discoveryNotice,
                    style = MaterialTheme.typography.bodyMedium,
                    color = TrailText,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 10.dp),
                )
            }
        }
        when (mode) {
        SpeciesMode.Collection -> {
        item {
            HikeFilterControl(
                hikes = hikes,
                selectedHikeId = selectedHikeId,
                onClick = { filterOpen = true },
            )
        }
        item {
            ObservationTypeFilterControl(
                selectedType = observationType,
                matchingCount = typeScopedSpecies.size,
                onClick = { observationTypeFilterOpen = true },
            )
        }
        item {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 15.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Rounded.Search, null, tint = InkMuted, modifier = Modifier.size(21.dp))
                OutlinedTextField(
                    value = query,
                    onValueChange = {
                        query = it
                        onCollectionPreferencesChange(collectionPreferences.copy(query = it))
                    },
                    modifier = Modifier.weight(1f).padding(start = 6.dp),
                    placeholder = { Text("Search common or scientific name") },
                    singleLine = true,
                    shape = RoundedCornerShape(4.dp),
                )
            }
        }
        item {
            Row(
                Modifier.fillMaxWidth().padding(start = 20.dp, end = 12.dp, bottom = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("SPECIES INDEX", style = MaterialTheme.typography.labelSmall, color = TrailText)
                TextButton(onClick = { speciesSortOpen = true }) {
                    Text(speciesSort.label)
                    Spacer(Modifier.width(2.dp))
                    Icon(
                        Icons.Rounded.KeyboardArrowDown,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                }
            }
        }
        if (loading && species.isEmpty()) {
            item {
                Column(Modifier.fillMaxWidth().padding(vertical = 90.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator(color = Moss, strokeWidth = 2.dp)
                    Text("Pressing the field guide…", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 14.dp))
                }
            }
        } else if (filtered.isEmpty()) {
            item {
                Column(Modifier.fillMaxWidth().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        when {
                            query.isNotBlank() -> "No species match"
                            observationType != ObservationTypeFilter.All -> "No ${observationType.label.lowercase()} yet"
                            else -> "No confirmed species"
                        },
                        style = MaterialTheme.typography.headlineMedium,
                        color = Ink,
                    )
                    Text(
                        when {
                            query.isNotBlank() -> "Try a common or scientific name."
                            observationType != ObservationTypeFilter.All -> "Choose another observation type to widen the field guide."
                            selectedHikeId != null -> "This outing has no confirmed encounters yet."
                            else -> "Confirmed observations will appear here after review."
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        color = InkMuted,
                    )
                }
            }
        } else {
            items(filtered, key = { it.key }) { record ->
                SpeciesIndexRow(record) { key -> onOpenSpecies(key, filtered, browseContext) }
            }
        }
        }
        SpeciesMode.Nearby -> {
            item {
                NearbyControls(
                    areas = visibleAreas,
                    areaSearch = areaSearch,
                    selectedArea = selectedArea,
                    targetDate = targetDate,
                    radiusKm = radiusKm,
                    iconicTaxa = iconicTaxa,
                    locationNotice = locationNotice,
                    loading = discoveryLoading,
                    onAreaSearch = {
                        areaSearch = it
                        if (selectedArea?.name != it) selectedAreaId = null
                    },
                    onArea = {
                        selectedAreaId = it.id
                        areaSearch = it.name
                    },
                    onDate = { targetDate = it },
                    onRadius = { radiusKm = when (radiusKm) { 5 -> 10; 10 -> 25; else -> 5 } },
                    onGroup = { nearbyLifeFilterOpen = true },
                    onExplore = {
                        selectedArea?.let {
                            nearbyResultLimit = StandardNearbyLimit
                            onLoadNearby(
                                it.id,
                                targetDate,
                                radiusKm,
                                iconicTaxa,
                                null,
                                null,
                                StandardNearbyLimit,
                            )
                        }
                    },
                    onUseLocation = {
                        val hasPermission = ContextCompat.checkSelfPermission(
                            context,
                            Manifest.permission.ACCESS_COARSE_LOCATION,
                        ) == PackageManager.PERMISSION_GRANTED
                        if (hasPermission) {
                            requestOneShotLocation(
                                context,
                                onLocation = { location ->
                                    locationNotice = null
                                    nearbyResultLimit = StandardNearbyLimit
                                    onLoadNearby(
                                        null,
                                        targetDate,
                                        radiusKm,
                                        iconicTaxa,
                                        location.latitude,
                                        location.longitude,
                                        StandardNearbyLimit,
                                    )
                                },
                                onUnavailable = { locationNotice = "A current location was not available. Choose a saved trail instead." },
                            )
                        } else {
                            locationPermission.launch(
                                arrayOf(
                                    Manifest.permission.ACCESS_COARSE_LOCATION,
                                    Manifest.permission.ACCESS_FINE_LOCATION,
                                ),
                            )
                        }
                    },
                )
            }
            nearbySpecies?.let { nearby ->
                item {
                    DiscoveryProgressHeader(
                        progress = nearby.progress.collectedCount,
                        total = nearby.progress.totalCount,
                        label = "${nearby.areaName} · ${nearby.periodLabel}",
                        detail = nearby.sourceGuidance,
                    )
                }
                if (nearby.dataDensity == "sparse" && nearby.dataDensityMessage.isNotBlank()) {
                    item {
                        Text(
                            nearby.dataDensityMessage,
                            style = MaterialTheme.typography.bodyMedium,
                            color = TrailText,
                            modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
                        )
                    }
                }
                if (
                    nearby.resultLimit == StandardNearbyLimit &&
                    nearby.progress.totalCount == StandardNearbyLimit &&
                    nearby.progress.collectedCount == StandardNearbyLimit
                ) {
                    item {
                        Column(
                            Modifier.fillMaxWidth().background(Color(0xFFE4DDC5))
                                .padding(horizontal = 20.dp, vertical = 14.dp),
                        ) {
                            Text(
                                "FIELD LIST COMPLETE",
                                style = MaterialTheme.typography.labelSmall,
                                color = TrailText,
                            )
                            Text(
                                "You found all 50. Open the next 50 nearby species?",
                                style = MaterialTheme.typography.titleLarge,
                                color = Ink,
                            )
                            TextButton(
                                onClick = {
                                    nearbyResultLimit = ExpandedNearbyLimit
                                    onLoadNearby(
                                        nearby.areaId.takeIf { it.isNotBlank() },
                                        nearby.targetDate,
                                        nearby.radiusKm,
                                        iconicTaxaForFilter(nearby.iconicTaxon),
                                        nearby.latitude,
                                        nearby.longitude,
                                        ExpandedNearbyLimit,
                                    )
                                },
                                enabled = !discoveryLoading,
                            ) {
                                Text("Expand to 100 species")
                            }
                        }
                    }
                }
                item {
                    QuestTargetStrip(
                        selectedCount = focusTaxonIds.size,
                        pending = false,
                    )
                }
                item {
                    val linkedHike = hikes.firstOrNull { it.id == linkedQuestHikeId }
                    Row(
                        Modifier.fillMaxWidth().padding(horizontal = 12.dp),
                        horizontalArrangement = Arrangement.End,
                    ) {
                        TextButton(
                            onClick = {
                                val choices = listOf<String?>(null) + hikes.map { it.id }
                                linkedQuestHikeId = choices[(choices.indexOf(linkedQuestHikeId) + 1).mod(choices.size)]
                            },
                        ) {
                            Text(linkedHike?.let { "Linked to ${it.title}" } ?: "Link an outing")
                        }
                    }
                }
                item {
                    Row(
                        Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            "${focusTaxonIds.size} OF $QuestFocusLimit QUEST TARGETS",
                            style = MaterialTheme.typography.labelSmall,
                            color = if (focusTaxonIds.isNotEmpty()) Trail else TrailText,
                        )
                        Button(
                            onClick = {
                                onSaveQuest(
                                    "${nearby.areaName} · ${nearby.periodLabel}",
                                    linkedQuestHikeId,
                                    focusTaxonIds,
                                    { quest ->
                                        mode = SpeciesMode.Quests
                                        selectedQuestId = quest.id
                                        editingQuestId = null
                                        focusTaxonIds = emptyList()
                                    },
                                )
                            },
                            enabled = !savingQuest && nearby.areaId.isNotBlank() && focusTaxonIds.isNotEmpty(),
                            shape = RoundedCornerShape(4.dp),
                        ) {
                            Text(
                                when {
                                    savingQuest -> "Saving…"
                                    focusTaxonIds.isEmpty() -> questTargetPrompt(focusTaxonIds.size)
                                    else -> "Save quest"
                                },
                            )
                        }
                    }
                }
                items(nearby.taxa, key = { "nearby-${it.taxonId}" }) { taxon ->
                    DiscoverySpeciesRow(
                        taxon = taxon,
                        focusOrder = focusTaxonIds.indexOf(taxon.taxonId)
                            .takeIf { it >= 0 }
                            ?.plus(1),
                        onToggleFocus = {
                            focusTaxonIds = toggleFocus(focusTaxonIds, taxon.taxonId)
                        },
                        onPreview = { previewTaxon = taxon },
                        selectionEnabled = focusTaxonIds.size < QuestFocusLimit || taxon.taxonId in focusTaxonIds,
                    )
                }
            } ?: item {
                DiscoveryEmpty(
                    if (discoveryLoading) "Gathering the local field list…"
                    else "Choose a saved trail or use your current area to begin.",
                )
            }
        }
        SpeciesMode.Quests -> {
            item {
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        if (selectedQuest == null) "CHOOSE A FIELD QUEST" else selectedQuest.title.uppercase(Locale.US),
                        style = MaterialTheme.typography.labelSmall,
                        color = TrailText,
                        modifier = Modifier.weight(1f),
                    )
                    TextButton(
                        onClick = {
                            showArchivedQuests = !showArchivedQuests
                            selectedQuestId = null
                        },
                    ) {
                        Text(if (showArchivedQuests) "Show active" else "Show archive")
                    }
                }
            }
            if (visibleQuests.size > 1 && selectedQuest == null) {
                items(visibleQuests, key = { "quest-tile-${it.id}" }) { quest ->
                    QuestTile(
                        quest = quest,
                        onOpen = {
                            editingQuestId = null
                            selectedQuestId = quest.id
                        },
                    )
                }
            } else if (selectedQuest != null) {
                val quest = selectedQuest
                val focusedTaxa = quest.taxa.filter { it.focusOrder != null }.sortedBy { it.focusOrder }
                val foundTargets = focusedTaxa.count { it.collected }
                val editingTargets = editingQuestId == quest.id
                if (visibleQuests.size > 1) {
                    item {
                        TextButton(
                            onClick = {
                                editingQuestId = null
                                selectedQuestId = null
                            },
                            modifier = Modifier.padding(horizontal = 8.dp),
                        ) {
                            Icon(
                                Icons.AutoMirrored.Rounded.ArrowBack,
                                null,
                                modifier = Modifier.size(17.dp),
                            )
                            Text("All quests", modifier = Modifier.padding(start = 5.dp))
                        }
                    }
                }
                item {
                    DiscoveryProgressHeader(
                        progress = foundTargets,
                        total = focusedTaxa.size,
                        label = "${quest.areaName} · ${quest.periodLabel}",
                        detail = if (quest.pendingFocusSync) {
                            "Target changes are queued for sync."
                        } else {
                            "This quest follows your chosen species."
                        },
                        noun = "found",
                    )
                }
                item {
                    QuestTargetStrip(
                        selectedCount = focusedTaxa.size,
                        pending = quest.pendingFocusSync,
                    )
                }
                item {
                    Column(
                        Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp),
                    ) {
                        Row(
                            Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                if (editingTargets) "CHOOSE 1–10 TARGETS" else "YOUR QUEST TARGETS",
                                style = MaterialTheme.typography.labelSmall,
                                color = TrailText,
                            )
                            TextButton(onClick = {
                                editingQuestId = if (editingTargets) null else quest.id
                            }, enabled = !editingTargets || focusedTaxa.isNotEmpty()) {
                                Text(
                                    when {
                                        !editingTargets -> "Change targets"
                                        focusedTaxa.isNotEmpty() -> "Done"
                                        else -> questTargetPrompt(focusedTaxa.size)
                                    },
                                )
                            }
                        }
                        Row(
                            Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.End,
                        ) {
                            TextButton(onClick = {
                                renamingQuest = quest
                                questNameDraft = quest.title
                            }) {
                                Icon(Icons.Rounded.Edit, null, modifier = Modifier.size(16.dp))
                                Text("Rename", modifier = Modifier.padding(start = 4.dp))
                            }
                            TextButton(onClick = { onArchiveQuest(quest) }) {
                                Text(if (quest.status == "archived") "Restore" else "Archive")
                            }
                            TextButton(onClick = { pendingDeleteQuest = quest }) {
                                Text("Delete", color = Color(0xFF8F3D32))
                            }
                        }
                    }
                }
                val displayedTaxa = if (editingTargets) quest.taxa else focusedTaxa
                items(displayedTaxa, key = { "quest-${quest.id}-${it.taxonId}" }) { taxon ->
                    val focusOrder = focusedTaxa.indexOfFirst { it.taxonId == taxon.taxonId }
                        .takeIf { it >= 0 }
                        ?.plus(1)
                    DiscoverySpeciesRow(
                        taxon = taxon,
                        focusOrder = focusOrder,
                        onToggleFocus = if (editingTargets) {
                            {
                                val updated = toggleFocus(
                                    focusedTaxa.map { it.taxonId },
                                    taxon.taxonId,
                                )
                                if (updated.isNotEmpty()) onSaveQuestFocus(quest, updated)
                            }
                        } else {
                            null
                        },
                        onPreview = { previewTaxon = taxon },
                        selectionEnabled = when {
                            focusOrder != null && focusedTaxa.size == 1 -> false
                            focusOrder != null -> true
                            else -> focusedTaxa.size < QuestFocusLimit
                        },
                    )
                }
                if (focusedTaxa.isEmpty() && !editingTargets) {
                    item {
                        DiscoveryEmpty("Choose at least one target to make this Field Quest actionable.")
                    }
                }
            } else {
                item {
                DiscoveryEmpty(
                    if (discoveryLoading) "Opening saved field quests…"
                    else if (showArchivedQuests) "No archived quests." else "Save a nearby field list to make your first quest.",
                )
                }
            }
        }
        }
        }
    }

    if (filterOpen) {
        HikeFilterSheet(
            hikes = hikes,
            selectedHikeId = selectedHikeId,
            onSelect = {
                selectedHikeId = it
                onCollectionPreferencesChange(collectionPreferences.copy(selectedHikeId = it))
                filterOpen = false
            },
            onDismiss = { filterOpen = false },
        )
    }
    if (observationTypeFilterOpen) {
        ObservationTypeFilterSheet(
            selectedType = observationType,
            onSelect = {
                observationType = it
                onCollectionPreferencesChange(collectionPreferences.copy(observationType = it))
                observationTypeFilterOpen = false
            },
            onDismiss = { observationTypeFilterOpen = false },
        )
    }
    if (speciesSortOpen) {
        SpeciesSortSheet(
            selectedSort = speciesSort,
            onSelect = {
                speciesSort = it
                onCollectionPreferencesChange(collectionPreferences.copy(sort = it))
                speciesSortOpen = false
            },
            onDismiss = { speciesSortOpen = false },
        )
    }
    if (nearbyLifeFilterOpen) {
        NearbyLifeFilterSheet(
            selectedGroups = iconicTaxa,
            onApply = {
                iconicTaxa = it
                nearbyLifeFilterOpen = false
            },
            onDismiss = { nearbyLifeFilterOpen = false },
        )
    }
    previewTaxon?.let { taxon ->
        val mapQuest = selectedQuest?.takeIf { quest ->
            mode == SpeciesMode.Quests && quest.taxa.any { it.taxonId == taxon.taxonId }
        }
        val mapNearby = nearbySpecies?.takeIf { nearby ->
            mode == SpeciesMode.Nearby && nearby.taxa.any { it.taxonId == taxon.taxonId }
        }
        DiscoveryTaxonPreviewDialog(
            taxon = taxon,
            onMap = when {
                mapQuest != null -> ({ onOpenQuestMap(mapQuest, taxon) })
                mapNearby != null -> ({ onOpenNearbyMap(mapNearby, taxon) })
                else -> null
            },
            onDismiss = { previewTaxon = null },
        )
    }
    pendingDeleteQuest?.let { quest ->
        AlertDialog(
            onDismissRequest = { pendingDeleteQuest = null },
            title = { Text("Delete Field Quest?", color = Ink) },
            text = {
                Text(
                    "“${quest.title}” and its saved target list will be removed permanently. Your species observations will not be affected.",
                    color = InkMuted,
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        onDeleteQuest(quest)
                        pendingDeleteQuest = null
                    },
                ) {
                    Text("Delete permanently", color = Color(0xFF8F3D32))
                }
            },
            dismissButton = {
                TextButton(onClick = { pendingDeleteQuest = null }) { Text("Cancel") }
            },
            containerColor = Paper,
        )
    }
    renamingQuest?.let { quest ->
        AlertDialog(
            onDismissRequest = { renamingQuest = null },
            title = { Text("Name this Field Quest", color = Ink) },
            text = {
                OutlinedTextField(
                    value = questNameDraft,
                    onValueChange = { questNameDraft = it },
                    singleLine = true,
                    label = { Text("Quest name") },
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        onRenameQuest(quest, questNameDraft.trim())
                        renamingQuest = null
                    },
                    enabled = questNameDraft.trim().isNotEmpty() && questNameDraft.trim() != quest.title,
                ) { Text("Save name") }
            },
            dismissButton = {
                TextButton(onClick = { renamingQuest = null }) { Text("Cancel") }
            },
            containerColor = Paper,
        )
    }
}

@Composable
internal fun DiscoveryTaxonPreviewDialog(
    taxon: DiscoveryTaxon,
    onMap: (() -> Unit)?,
    onDismiss: () -> Unit,
) {
    val uriHandler = LocalUriHandler.current
    val previewImageUrl = taxon.collectionPhotoUrl
        .takeIf { taxon.collected && !it.isNullOrBlank() }
        ?: taxon.referencePhoto?.url.orEmpty()
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Column {
                Text(
                    if (taxon.collected && !taxon.collectionPhotoUrl.isNullOrBlank()) {
                        "YOUR OBSERVATION"
                    } else {
                        "REFERENCE SPECIMEN"
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = TrailText,
                )
                Text(taxon.commonName, style = MaterialTheme.typography.headlineMedium, color = Ink)
                Text(
                    taxon.scientificName,
                    style = MaterialTheme.typography.bodyMedium.copy(fontStyle = FontStyle.Italic),
                    color = InkMuted,
                )
            }
        },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                AsyncImage(
                    model = ImageRequest.Builder(LocalContext.current)
                        .data(previewImageUrl)
                        .crossfade(true)
                        .build(),
                    contentDescription = "${taxon.commonName} in color",
                    modifier = Modifier.fillMaxWidth().height(320.dp),
                    contentScale = ContentScale.Crop,
                )
                if (taxon.collected && !taxon.collectionPhotoUrl.isNullOrBlank()) {
                    Text(
                        listOf(
                            "Your HikeJournal observation",
                            taxon.collectedAt?.take(10).orEmpty(),
                        )
                            .filter { it.isNotBlank() }
                            .joinToString(" · "),
                        style = MaterialTheme.typography.labelSmall,
                        color = InkMuted,
                        modifier = Modifier.padding(top = 9.dp),
                    )
                } else {
                    taxon.referencePhoto?.let { photo ->
                        Text(
                            listOf(photo.attribution, photo.licenseCode)
                                .filter { it.isNotBlank() }
                                .joinToString(" · "),
                            style = MaterialTheme.typography.labelSmall,
                            color = InkMuted,
                            modifier = Modifier.padding(top = 9.dp),
                        )
                    }
                }
                Text(
                    "WHY IT’S HERE",
                    style = MaterialTheme.typography.labelSmall,
                    color = TrailText,
                    modifier = Modifier.padding(top = 18.dp),
                )
                Text(
                    taxon.matchReason.ifBlank {
                        "This species matched both the selected location and seasonal date window."
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    color = Ink,
                    modifier = Modifier.padding(top = 4.dp),
                )
                if (taxon.wikipediaSummary.isNotBlank()) {
                    Text(
                        "FROM WIKIPEDIA",
                        style = MaterialTheme.typography.labelSmall,
                        color = TrailText,
                        modifier = Modifier.padding(top = 18.dp),
                    )
                    Text(
                        taxon.wikipediaSummary,
                        style = MaterialTheme.typography.bodyMedium,
                        color = Ink,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
                if (taxon.wikipediaUrl.isNotBlank()) {
                    TextButton(
                        onClick = { uriHandler.openUri(taxon.wikipediaUrl) },
                        modifier = Modifier.padding(top = 2.dp),
                    ) {
                        Text("Read on Wikipedia")
                    }
                }
            }
        },
        confirmButton = {
            Row {
                if (onMap != null) {
                    Button(
                        onClick = {
                            onDismiss()
                            onMap()
                        },
                    ) {
                        Text("Map sightings")
                    }
                }
                TextButton(onClick = onDismiss) { Text("Close") }
            }
        },
        containerColor = Paper,
    )
}

@Composable
private fun SpeciesModeTabs(mode: SpeciesMode, onMode: (SpeciesMode) -> Unit) {
    Row(
        Modifier.fillMaxWidth().background(Color(0xFFE3DEC9)).padding(horizontal = 12.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        SpeciesMode.entries.forEach { item ->
            val color by animateColorAsState(if (item == mode) Moss else Color.Transparent, label = "species-mode")
            TextButton(
                onClick = { onMode(item) },
                modifier = Modifier.background(color, RoundedCornerShape(3.dp)),
            ) {
                Text(item.label, color = if (item == mode) Paper else Ink)
            }
        }
    }
}

@Composable
private fun NearbyControls(
    areas: List<DiscoveryArea>,
    areaSearch: String,
    selectedArea: DiscoveryArea?,
    targetDate: String,
    radiusKm: Int,
    iconicTaxa: List<String>,
    locationNotice: String?,
    loading: Boolean,
    onAreaSearch: (String) -> Unit,
    onArea: (DiscoveryArea) -> Unit,
    onDate: (String) -> Unit,
    onRadius: () -> Unit,
    onGroup: () -> Unit,
    onExplore: () -> Unit,
    onUseLocation: () -> Unit,
) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 18.dp)) {
        Text("Choose the ground you will walk", style = MaterialTheme.typography.headlineMedium, color = Ink)
        Text(
            "Lists use seasonally nearby iNaturalist reports—not a promise that a species will appear.",
            style = MaterialTheme.typography.bodyMedium,
            color = InkMuted,
            modifier = Modifier.padding(top = 4.dp, bottom = 12.dp),
        )
        OutlinedTextField(
            value = areaSearch,
            onValueChange = onAreaSearch,
            label = { Text("Search saved trails") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(4.dp),
        )
        if (shouldShowSavedTrailResults(areaSearch, selectedArea != null)) {
            when {
                areas.isNotEmpty() -> {
                    Text(
                        "SAVED TRAILS",
                        style = MaterialTheme.typography.labelSmall,
                        color = TrailText,
                        modifier = Modifier.padding(top = 10.dp, bottom = 2.dp),
                    )
                    areas.forEach { area ->
                        TextButton(onClick = { onArea(area) }, modifier = Modifier.fillMaxWidth()) {
                            Text(area.name, modifier = Modifier.fillMaxWidth(), color = Ink)
                        }
                    }
                }
                else -> {
                    Text(
                        "No saved trails match “$areaSearch”.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = InkMuted,
                        modifier = Modifier.padding(top = 10.dp),
                    )
                }
            }
        }
        OutlinedTextField(
            value = targetDate,
            onValueChange = onDate,
            label = { Text("Outing date · YYYY-MM-DD") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            shape = RoundedCornerShape(4.dp),
        )
        Row(
            Modifier.fillMaxWidth().padding(top = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onRadius) { Text("$radiusKm km radius") }
            TextButton(onClick = onGroup) {
                Text(iconicTaxonLabel(iconicTaxa))
                Spacer(Modifier.width(2.dp))
                Icon(
                    Icons.Rounded.KeyboardArrowDown,
                    contentDescription = "Choose a life group",
                    modifier = Modifier.size(18.dp),
                )
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = onExplore,
                enabled = selectedArea != null && !loading,
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(4.dp),
            ) {
                Text(if (loading) "Looking…" else "Explore nearby")
            }
            TextButton(onClick = onUseLocation, enabled = !loading) {
                Text("Use my location")
            }
        }
        Text(
            "Your location is used once for this iNaturalist search and rounded to about 1 km for privacy.",
            style = MaterialTheme.typography.labelSmall,
            color = InkMuted,
            modifier = Modifier.padding(top = 6.dp),
        )
        if (!locationNotice.isNullOrBlank()) {
            Text(
                locationNotice,
                style = MaterialTheme.typography.bodyMedium,
                color = TrailText,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
    }
}

@Composable
private fun QuestTile(quest: FieldQuest, onOpen: () -> Unit) {
    val focusedTaxa = quest.taxa.filter { it.focusOrder != null }.sortedBy { it.focusOrder }
    val found = focusedTaxa.count { it.collected }
    val progress = if (focusedTaxa.isEmpty()) 0f else found.toFloat() / focusedTaxa.size.toFloat()
    val leadTaxon = focusedTaxa.firstOrNull() ?: quest.taxa.firstOrNull()
    val leadImage = leadTaxon?.collectionPhotoUrl?.takeIf { leadTaxon.collected && it.isNotBlank() }
        ?: leadTaxon?.referencePhoto?.url
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp, vertical = 7.dp)
            .background(Paper, RoundedCornerShape(6.dp))
            .clickable(onClick = onOpen)
            .padding(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(86.dp)
                .clip(RoundedCornerShape(4.dp))
                .background(Color(0xFFDBE1D2)),
            contentAlignment = Alignment.Center,
        ) {
            if (!leadImage.isNullOrBlank()) {
                AsyncImage(
                    model = ImageRequest.Builder(LocalContext.current).data(leadImage).crossfade(true).build(),
                    contentDescription = leadTaxon?.commonName,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            } else {
                Text("FIELD\nQUEST", style = MaterialTheme.typography.labelSmall, color = TrailText)
            }
        }
        Column(Modifier.weight(1f).padding(start = 14.dp, end = 4.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top,
            ) {
                Column(Modifier.weight(1f)) {
                Text(
                    quest.title,
                    style = MaterialTheme.typography.titleLarge,
                    color = Ink,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    "${quest.areaName} · ${quest.periodLabel}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                }
                Text("$found/${focusedTaxa.size}", style = MaterialTheme.typography.labelMedium, color = Moss)
            }
            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(4.dp),
                color = Moss,
                trackColor = Line,
            )
            Text(
                leadTaxon?.commonName?.let { "Lead target · $it" } ?: "Open quest",
                style = MaterialTheme.typography.labelSmall,
                color = TrailText,
                modifier = Modifier.padding(top = 6.dp),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun DiscoveryProgressHeader(
    progress: Int,
    total: Int,
    label: String,
    detail: String,
    noun: String = "collected",
) {
    val target = if (total <= 0) 0f else progress.toFloat() / total.toFloat()
    val animated by animateFloatAsState(target, label = "quest-progress")
    Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 14.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column(Modifier.weight(1f)) {
                Text(label, style = MaterialTheme.typography.labelMedium, color = TrailText)
                Text("$progress of $total $noun", style = MaterialTheme.typography.headlineMedium, color = Ink)
            }
            Text("${total - progress} left", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
        }
        LinearProgressIndicator(
            progress = { animated },
            modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(5.dp),
            color = Moss,
            trackColor = Line,
        )
        Text(detail, style = MaterialTheme.typography.labelSmall, color = InkMuted, modifier = Modifier.padding(top = 7.dp))
    }
}

@Composable
private fun QuestTargetStrip(selectedCount: Int, pending: Boolean) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(Color(0xFFE4DDC5))
            .padding(horizontal = 20.dp, vertical = 10.dp),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                "QUEST TARGETS",
                style = MaterialTheme.typography.labelSmall,
                color = TrailText,
            )
            Spacer(Modifier.weight(1f))
            Text(
                "$selectedCount/$QuestFocusLimit",
                style = MaterialTheme.typography.labelMedium,
                color = if (selectedCount > 0) Trail else Ink,
            )
            if (pending) {
                Icon(
                    Icons.Rounded.CloudOff,
                    "Quest target sync pending",
                    tint = TrailText,
                    modifier = Modifier.padding(start = 6.dp).size(15.dp),
                )
            }
        }
        Row(
            Modifier.fillMaxWidth().padding(top = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            repeat(QuestFocusLimit) { index ->
                val isSelected = index < selectedCount
                val markerColor by animateColorAsState(
                    if (isSelected) Trail else Color(0xFFC7C0AA),
                    label = "quest-target-${index + 1}",
                )
                Box(
                    Modifier
                        .size(22.dp)
                        .background(markerColor, CircleShape),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        "${index + 1}",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (isSelected) Paper else InkMuted,
                    )
                }
            }
        }
    }
}

internal fun shouldShowSavedTrailResults(searchText: String, hasSelectedArea: Boolean): Boolean =
    searchText.isNotBlank() && !hasSelectedArea

internal fun questTargetPrompt(selectedCount: Int): String {
    return if (selectedCount <= 0) "Pick at least 1" else "Save quest"
}

internal fun discoveryStatusLabel(collected: Boolean, frequencyBand: String): String {
    val band = frequencyBand.ifBlank { "Nearby record" }.uppercase(Locale.US)
    return if (collected) "COLLECTED · $band" else band
}

@Composable
private fun DiscoverySpeciesRow(
    taxon: DiscoveryTaxon,
    focusOrder: Int?,
    onToggleFocus: (() -> Unit)?,
    onPreview: () -> Unit,
    selectionEnabled: Boolean = true,
) {
    val saturation by animateFloatAsState(if (taxon.collected) 1f else 0f, label = "species-reveal")
    val imageUrl = taxon.collectionPhotoUrl.takeIf { taxon.collected && !it.isNullOrBlank() }
        ?: taxon.referencePhoto?.url.orEmpty()
    val matrix = ColorMatrix().apply { setToSaturation(saturation) }
    Column(
        Modifier.fillMaxWidth().background(
            if (focusOrder != null) Color(0x1FB2673A) else Color.Transparent,
        ),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                Modifier
                    .size(86.dp)
                    .background(Color(0xFFD0CFBD))
                    .clickable(
                        enabled = imageUrl.isNotBlank(),
                        onClick = onPreview,
                    ),
            ) {
                AsyncImage(
                    model = ImageRequest.Builder(LocalContext.current).data(imageUrl).crossfade(true).build(),
                    contentDescription = taxon.commonName,
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.Crop,
                    colorFilter = ColorFilter.colorMatrix(matrix),
                )
                if (imageUrl.isNotBlank()) {
                    Text(
                        if (taxon.collected && !taxon.collectionPhotoUrl.isNullOrBlank()) {
                            "OPEN PHOTO"
                        } else {
                            "VIEW IN COLOR"
                        },
                        style = MaterialTheme.typography.labelSmall,
                        color = Paper,
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .fillMaxWidth()
                            .background(Color(0xB81A2A20))
                            .padding(horizontal = 4.dp, vertical = 3.dp),
                    )
                }
            }
            Column(Modifier.weight(1f).padding(start = 14.dp)) {
                Text(
                    discoveryStatusLabel(taxon.collected, taxon.frequencyBand),
                    style = MaterialTheme.typography.labelSmall,
                    color = if (taxon.collected) Moss else TrailText,
                )
                Text(taxon.commonName, style = MaterialTheme.typography.titleLarge, color = Ink, maxLines = 2)
                Text(
                    taxon.scientificName,
                    style = MaterialTheme.typography.bodyMedium.copy(fontStyle = FontStyle.Italic),
                    color = InkMuted,
                    maxLines = 1,
                )
                if (taxon.pendingCredit) {
                    Text("PENDING CREDIT", style = MaterialTheme.typography.labelSmall, color = Trail)
                } else if (!taxon.collected && taxon.referencePhoto?.attribution?.isNotBlank() == true) {
                    Text(
                        "${taxon.referencePhoto.attribution} · ${taxon.referencePhoto.licenseCode}",
                        style = MaterialTheme.typography.labelSmall,
                        color = InkMuted,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            if (onToggleFocus != null) {
                TextButton(onClick = onToggleFocus, enabled = selectionEnabled) {
                    Text(if (focusOrder != null) "Selected $focusOrder/$QuestFocusLimit" else "Select")
                }
            }
        }
        HorizontalDivider(color = Line, thickness = 1.dp)
    }
}

@Composable
private fun DiscoveryEmpty(message: String) {
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 32.dp, vertical = 70.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        if (message.endsWith("…")) CircularProgressIndicator(color = Moss, strokeWidth = 2.dp)
        Text(message, style = MaterialTheme.typography.bodyLarge, color = InkMuted, modifier = Modifier.padding(top = 12.dp))
    }
}

private fun toggleFocus(current: List<Long>, taxonId: Long): List<Long> =
    if (taxonId in current) current.filterNot { it == taxonId }
    else if (current.size >= QuestFocusLimit) current else current + taxonId

private val NearbyLifeGroups = listOf<String?>(
    null,
    "Plantae",
    "Aves",
    "Mammalia",
    "Reptilia",
    "Amphibia",
    "Insecta",
    "Arachnida",
    "Fungi",
    "Actinopterygii",
    "Mollusca",
)

@Composable
private fun NearbyLifeFilterSheet(
    selectedGroups: List<String>,
    onApply: (List<String>) -> Unit,
    onDismiss: () -> Unit,
) {
    var draftSelectedGroups by remember(selectedGroups) { mutableStateOf(selectedGroups) }
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Paper) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding()) {
            Column(Modifier.padding(horizontal = 20.dp)) {
                Text("NEARBY SPECIES", style = MaterialTheme.typography.labelSmall, color = TrailText)
                Text("Choose life groups", style = MaterialTheme.typography.headlineLarge, color = Ink)
                Text(
                    "Select as many branches of life as you want.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            LazyColumn(Modifier.fillMaxWidth().heightIn(max = 520.dp).padding(top = 10.dp)) {
                items(NearbyLifeGroups, key = { it ?: "all-life" }) { group ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clickable {
                                draftSelectedGroups = if (group == null) {
                                    emptyList()
                                } else if (group in draftSelectedGroups) {
                                    draftSelectedGroups.filterNot { it == group }
                                } else {
                                    draftSelectedGroups + group
                                }
                            }
                            .padding(horizontal = 20.dp, vertical = 15.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            iconicTaxonLabel(group),
                            style = MaterialTheme.typography.titleMedium,
                            color = Ink,
                            modifier = Modifier.weight(1f),
                        )
                        androidx.compose.animation.AnimatedVisibility(
                            visible = (group == null && draftSelectedGroups.isEmpty()) ||
                                (group != null && group in draftSelectedGroups),
                        ) {
                            Icon(Icons.Rounded.Check, "Selected", tint = Moss, modifier = Modifier.size(22.dp))
                        }
                    }
                    HorizontalDivider(color = Line, modifier = Modifier.padding(start = 20.dp))
                }
                item { Spacer(Modifier.height(14.dp)) }
            }
            Button(
                onClick = { onApply(draftSelectedGroups) },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 10.dp),
                shape = RoundedCornerShape(4.dp),
            ) {
                Text("Apply filters")
            }
        }
    }
}

internal fun iconicTaxonLabel(value: String?): String = iconicTaxonLabel(iconicTaxaForFilter(value))

internal fun iconicTaxonLabel(values: List<String>): String = when (values.size) {
    0 -> "All life"
    1 -> iconicTaxonNameLabel(values.first())
    else -> "${values.size} life groups"
}

private fun iconicTaxonNameLabel(value: String): String = when (value) {
    "Plantae" -> "Plants"
    "Aves" -> "Birds"
    "Mammalia" -> "Mammals"
    "Reptilia" -> "Reptiles"
    "Amphibia" -> "Amphibians"
    "Insecta" -> "Insects"
    "Arachnida" -> "Arachnids"
    "Fungi" -> "Fungi"
    "Actinopterygii" -> "Fish"
    "Mollusca" -> "Mollusks"
    else -> value
}

private fun iconicTaxaForFilter(value: String?): List<String> = value
    ?.split(",")
    ?.map(String::trim)
    ?.filter(String::isNotBlank)
    .orEmpty()

@Suppress("MissingPermission")
internal fun requestOneShotLocation(
    context: Context,
    onLocation: (Location) -> Unit,
    onUnavailable: () -> Unit,
) {
    val manager = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
        ?: return onUnavailable()
    val hasFineLocation = ContextCompat.checkSelfPermission(
        context,
        Manifest.permission.ACCESS_FINE_LOCATION,
    ) == PackageManager.PERMISSION_GRANTED
    val hasCoarseLocation = ContextCompat.checkSelfPermission(
        context,
        Manifest.permission.ACCESS_COARSE_LOCATION,
    ) == PackageManager.PERMISSION_GRANTED
    val provider = when {
        hasFineLocation && manager.isProviderEnabled(LocationManager.GPS_PROVIDER) ->
            LocationManager.GPS_PROVIDER
        (hasFineLocation || hasCoarseLocation) &&
            manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER) ->
            LocationManager.NETWORK_PROVIDER
        else -> return onUnavailable()
    }
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
        manager.getCurrentLocation(provider, null, context.mainExecutor) { location ->
            if (location == null) onUnavailable() else onLocation(location)
        }
    } else {
        val listener = object : LocationListener {
            override fun onLocationChanged(location: Location) {
                manager.removeUpdates(this)
                onLocation(location)
            }
            override fun onProviderDisabled(provider: String) = onUnavailable()
            override fun onProviderEnabled(provider: String) = Unit
            @Deprecated("Deprecated in Android")
            override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit
        }
        manager.requestSingleUpdate(provider, listener, null)
    }
}

@Composable
private fun SpeciesIndexRow(record: SpeciesRecord, onOpen: (String) -> Unit) {
    Column(Modifier.fillMaxWidth().clickable { onOpen(record.key) }) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 13.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(Modifier.size(92.dp).background(Moss)) {
                AsyncImage(
                    model = ImageRequest.Builder(LocalContext.current).data(record.coverUrl).crossfade(true).build(),
                    contentDescription = record.commonName,
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.Crop,
                )
            }
            Column(Modifier.weight(1f).padding(start = 15.dp)) {
                Text(record.commonName, style = MaterialTheme.typography.titleLarge, color = Ink, maxLines = 2, overflow = TextOverflow.Ellipsis)
                if (record.scientificName.isNotBlank()) {
                    Text(
                        record.scientificName,
                        style = MaterialTheme.typography.bodyMedium.copy(fontStyle = FontStyle.Italic),
                        color = InkMuted,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Text(
                    "${record.encounterCount} encounter${if (record.encounterCount == 1) "" else "s"} · ${record.hikeCount} outing${if (record.hikeCount == 1) "" else "s"}",
                    style = MaterialTheme.typography.labelMedium,
                    color = TrailText,
                    modifier = Modifier.padding(top = 5.dp),
                )
            }
            Text(record.encounterCount.toString().padStart(2, '0'), style = MaterialTheme.typography.headlineSmall, color = FernText)
        }
        HorizontalDivider(color = Line, modifier = Modifier.padding(start = 127.dp))
    }
}

@Composable
fun SpeciesDetailScreen(
    species: SpeciesRecord,
    allSpecies: List<SpeciesRecord>,
    browseContext: String?,
    loading: Boolean,
    onBack: () -> Unit,
    onOpenSpecies: (String) -> Unit,
    onOpenPhoto: (Photo) -> Unit,
) {
    val currentIndex = allSpecies.indexOfFirst { it.key == species.key }
    var horizontalDragDistance by remember(species.key) { mutableFloatStateOf(0f) }
    LazyColumn(
        Modifier.fillMaxSize().background(Parchment).pointerInput(species.key, currentIndex) {
            detectHorizontalDragGestures(
                onHorizontalDrag = { _, dragAmount -> horizontalDragDistance += dragAmount },
                onDragEnd = {
                    when {
                        horizontalDragDistance > 72f && currentIndex > 0 -> onOpenSpecies(allSpecies[currentIndex - 1].key)
                        horizontalDragDistance < -72f && currentIndex >= 0 && currentIndex < allSpecies.lastIndex -> onOpenSpecies(allSpecies[currentIndex + 1].key)
                    }
                    horizontalDragDistance = 0f
                },
                onDragCancel = { horizontalDragDistance = 0f },
            )
        },
        contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 54.dp),
    ) {
        item { SpeciesHero(species, onBack) }
        item {
            Column(Modifier.padding(horizontal = 20.dp, vertical = 24.dp)) {
                Text(
                    browseContext?.let { "FIELD GUIDE \u00b7 $it" } ?: "PERSONAL FIELD GUIDE",
                    style = MaterialTheme.typography.labelSmall,
                    color = TrailText,
                )
                Text(species.commonName, style = MaterialTheme.typography.displayMedium, color = Ink)
                if (species.scientificName.isNotBlank()) {
                    Text(
                        species.scientificName,
                        style = MaterialTheme.typography.titleLarge.copy(fontStyle = FontStyle.Italic),
                        color = InkMuted,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
                Text(
                    "${species.encounterCount} encounter${if (species.encounterCount == 1) "" else "s"} across ${species.hikeCount} outing${if (species.hikeCount == 1) "" else "s"}",
                    style = MaterialTheme.typography.labelMedium,
                    color = TrailText,
                    modifier = Modifier.padding(top = 13.dp),
                )
                if (species.wikipediaSummary.isNotBlank()) {
                    Text(species.wikipediaSummary, style = MaterialTheme.typography.bodyLarge, color = Ink, modifier = Modifier.padding(top = 20.dp))
                } else {
                    Text(
                        "Your confirmed photographs, arranged from the most recent encounter backward.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = InkMuted,
                        modifier = Modifier.padding(top = 20.dp),
                    )
                }
            }
        }
        if (species.seasonalHistory.observationCount > 0) {
            item {
                Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 24.dp)) {
                    Text("YOUR SEASONAL HISTORY", style = MaterialTheme.typography.labelSmall, color = TrailText)
                    Text(
                        "When this species appears in your journal",
                        style = MaterialTheme.typography.headlineSmall,
                        color = Ink,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                    SeasonalBand(species.seasonalHistory, Modifier.padding(top = 20.dp))
                    Text(
                        species.seasonalHistory.guidance,
                        style = MaterialTheme.typography.bodySmall.copy(fontStyle = FontStyle.Italic),
                        color = InkMuted,
                        modifier = Modifier.padding(top = 12.dp),
                    )
                }
                HorizontalDivider(color = Line)
            }
        }
        item {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Bottom,
            ) {
                Column {
                    Text("ENCOUNTER HISTORY", style = MaterialTheme.typography.labelSmall, color = TrailText)
                    Text("Field records", style = MaterialTheme.typography.headlineMedium, color = Ink)
                }
                if (loading) CircularProgressIndicator(Modifier.size(20.dp), color = Moss, strokeWidth = 2.dp)
            }
        }
        items(species.encounters, key = { it.photo.id }) { encounter ->
            EncounterRow(encounter, onOpenPhoto)
        }
    }
}

@Composable
private fun SpeciesHero(species: SpeciesRecord, onBack: () -> Unit) {
    Box(Modifier.fillMaxWidth().height(390.dp).background(Moss)) {
        AsyncImage(species.coverUrl, species.commonName, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        Box(
            Modifier.fillMaxSize().background(
                Brush.verticalGradient(listOf(Color(0x88000000), Color.Transparent, Color(0x99101B15))),
            ),
        )
        FilledIconButton(
            onClick = onBack,
            modifier = Modifier.statusBarsPadding().padding(10.dp),
            colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(containerColor = Color(0x99172820)),
        ) {
            Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back", tint = Paper)
        }
        Column(Modifier.align(Alignment.BottomStart).padding(20.dp)) {
            Text("HikeJournal", style = MaterialTheme.typography.headlineSmall, color = Color(0xFFD7DFD2))
            Text(species.commonName, style = MaterialTheme.typography.headlineLarge, color = Paper, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun EncounterRow(encounter: Encounter, onOpenPhoto: (Photo) -> Unit) {
    Column(
        Modifier.fillMaxWidth().clickable { onOpenPhoto(encounter.photo) },
    ) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 13.dp), verticalAlignment = Alignment.CenterVertically) {
            AsyncImage(
                encounter.photo.url,
                encounter.photo.caption.ifBlank { encounter.hikeTitle },
                Modifier.width(136.dp).height(104.dp).background(Moss),
                contentScale = ContentScale.Crop,
            )
            Column(Modifier.weight(1f).padding(start = 15.dp)) {
                Text(formatSpeciesDate(encounter.observedOn).uppercase(Locale.US), style = MaterialTheme.typography.labelSmall, color = TrailText)
                Text(encounter.hikeTitle, style = MaterialTheme.typography.titleMedium, color = Ink, maxLines = 2, overflow = TextOverflow.Ellipsis)
                if (encounter.locationName.isNotBlank()) {
                    Text(encounter.locationName, style = MaterialTheme.typography.bodyMedium, color = InkMuted, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                if (encounter.photo.caption.isNotBlank()) {
                    Text(encounter.photo.caption, style = MaterialTheme.typography.bodyMedium, color = InkMuted, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Text("View this species photo", style = MaterialTheme.typography.labelSmall, color = TrailText, modifier = Modifier.padding(top = 5.dp))
            }
        }
        HorizontalDivider(color = Line, modifier = Modifier.padding(start = 171.dp))
    }
}

private fun formatSpeciesDate(raw: String?): String {
    if (raw.isNullOrBlank()) return "Field record"
    return try {
        LocalDate.parse(raw.take(10)).format(DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US))
    } catch (_: Exception) {
        raw.take(10)
    }
}
