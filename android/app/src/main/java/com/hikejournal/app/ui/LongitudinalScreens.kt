package com.hikejournal.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.ArrowForward
import androidx.compose.material.icons.rounded.BugReport
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.Cloud
import androidx.compose.material.icons.rounded.Explore
import androidx.compose.material.icons.rounded.FlutterDash
import androidx.compose.material.icons.rounded.KeyboardArrowUp
import androidx.compose.material.icons.rounded.KeyboardArrowDown
import androidx.compose.material.icons.rounded.LocalFlorist
import androidx.compose.material.icons.rounded.LocationOn
import androidx.compose.material.icons.rounded.Map
import androidx.compose.material.icons.rounded.Park
import androidx.compose.material.icons.rounded.Pets
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.hikejournal.app.data.BriefingItem
import com.hikejournal.app.data.ComparisonHike
import com.hikejournal.app.data.ComparisonSpecies
import com.hikejournal.app.data.FieldBriefing
import com.hikejournal.app.data.HikeComparison
import com.hikejournal.app.data.PlaceProfile
import com.hikejournal.app.data.PlaceTaxonGroup
import com.hikejournal.app.data.SeasonalHistory
import com.hikejournal.app.data.WeatherSnapshot
import com.hikejournal.app.data.toDiscoveryTaxon
import com.hikejournal.app.ui.theme.Fern
import com.hikejournal.app.ui.theme.FernText
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.TrailText
import java.util.Locale
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

@Composable
internal fun PlaceProfileScreen(
    profile: PlaceProfile?,
    loading: Boolean,
    loadingPlaceName: String,
    loadingCoverUrl: String,
    placePositionLabel: String,
    onBack: () -> Unit,
    onOpenHike: (String) -> Unit,
    onOpenSpecies: (String) -> Unit,
    onPreviousPlace: (() -> Unit)?,
    onNextPlace: (() -> Unit)?,
) {
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val coverUrl = if (profile == null) {
        loadingCoverUrl
    } else {
        profile.visits.firstOrNull()?.coverUrl.orEmpty()
    }
    BackHandler(onBack = onBack)
    LazyColumn(
        Modifier.fillMaxSize().background(Parchment).pointerInput(
            profile?.locationId,
            loading,
            onPreviousPlace != null,
            onNextPlace != null,
        ) {
            if (!loading && profile != null && (onPreviousPlace != null || onNextPlace != null)) {
                val swipeThreshold = 72.dp.toPx()
                var horizontalDragDistance = 0f
                detectHorizontalDragGestures(
                    onHorizontalDrag = { change, dragAmount ->
                        change.consume()
                        horizontalDragDistance += dragAmount
                    },
                    onDragEnd = {
                        when {
                            horizontalDragDistance <= -swipeThreshold -> onNextPlace?.invoke()
                            horizontalDragDistance >= swipeThreshold -> onPreviousPlace?.invoke()
                        }
                        horizontalDragDistance = 0f
                    },
                    onDragCancel = { horizontalDragDistance = 0f },
                )
            }
        },
        state = listState,
    ) {
        item {
            FieldPageHero(
                kicker = listOf("PLACE PROFILE", placePositionLabel).filter(String::isNotBlank).joinToString(" · "),
                title = profile?.name ?: loadingPlaceName.ifBlank { "Reading this place…" },
                subtitle = profile?.let {
                    "${it.outingCount} recorded visit${if (it.outingCount == 1) "" else "s"} · ${formatMiles(it.totalDistanceMiles)}"
                }.orEmpty(),
                imageUrl = coverUrl,
                imageDescription = profile?.let { "Most recent hike at ${it.name}" } ?: "Hike cover while the place profile loads",
                onBack = onBack,
            )
        }
        if (loading || profile == null) {
            item {
                FieldPageLoading(
                    title = "Gathering your field notes…",
                    detail = "Reviewing visits, seasons, and the life you recorded here.",
                )
            }
        } else {
            item {
                Column(Modifier.padding(horizontal = 20.dp, vertical = 28.dp)) {
                    Text("YOUR RECORD HERE", style = MaterialTheme.typography.labelMedium, color = TrailText)
                    Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                        FieldNumber(profile.speciesCount.toString(), "SPECIES")
                        FieldNumber(profile.observationCount.toString(), "OBSERVATIONS")
                        FieldNumber(profile.firstVisit?.take(4).orEmpty().ifBlank { "—" }, "SINCE")
                    }
                    Text(
                        profile.guidance,
                        style = MaterialTheme.typography.bodyMedium,
                        color = Ink,
                        fontStyle = FontStyle.Italic,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.padding(top = 18.dp),
                    )
                }
            }
            item {
                FieldSection("WHEN YOU VISIT", "Your recorded activity and observations by month.") {
                    SeasonalBand(profile.seasonalHistory)
                }
            }
            if (profile.taxonCounts.isNotEmpty()) {
                item {
                    FieldSection("LIFE RECORDED", "Open a life group to browse every distinct confirmed species recorded here.") {
                        if (profile.taxonGroups.isNotEmpty()) {
                            LifeRecordedGroups(profile.taxonGroups, onOpenSpecies)
                        } else {
                            profile.taxonCounts.forEach { (name, count) ->
                                LifeGroupHeader(name = name, count = count, expanded = false, onClick = {})
                            }
                        }
                    }
                }
            }
            item {
                Text(
                    "VISIT HISTORY",
                    style = MaterialTheme.typography.labelMedium,
                    color = TrailText,
                    modifier = Modifier.padding(start = 20.dp, end = 20.dp, top = 30.dp, bottom = 8.dp),
                )
            }
            items(profile.visits, key = { it.hikeId }) { visit ->
                Row(
                    Modifier.fillMaxWidth().clickable { onOpenHike(visit.hikeId) }
                        .padding(horizontal = 20.dp, vertical = 15.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(Modifier.width(92.dp).height(72.dp).background(Color(0xFFD0CFBD))) {
                        if (visit.coverUrl.isNotBlank()) {
                            AsyncImage(
                                model = visit.coverUrl,
                                contentDescription = "Cover photo for ${visit.title}",
                                modifier = Modifier.fillMaxSize(),
                                contentScale = ContentScale.Crop,
                            )
                        } else {
                            Icon(
                                Icons.Rounded.Park,
                                contentDescription = null,
                                tint = Moss.copy(alpha = 0.55f),
                                modifier = Modifier.align(Alignment.Center).size(30.dp),
                            )
                        }
                    }
                    Column(Modifier.weight(1f).padding(start = 14.dp)) {
                        Text(visit.hikeDate, style = MaterialTheme.typography.labelMedium, color = TrailText)
                        Text(visit.title, style = MaterialTheme.typography.titleLarge, color = Ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(
                            "${visit.speciesCount} species · ${visit.newSpeciesCount} new then · ${visit.cumulativeSpeciesCount} cumulative",
                            style = MaterialTheme.typography.bodyMedium,
                            color = InkMuted,
                            fontWeight = FontWeight.Medium,
                        )
                    }
                    Icon(Icons.AutoMirrored.Rounded.ArrowForward, contentDescription = "Open journal", tint = FernText)
                }
                HorizontalDivider(color = Line, modifier = Modifier.padding(start = 20.dp))
            }
            if (profile.visits.size > 5) {
                item {
                    FieldBackToTop {
                        scope.launch { listState.animateScrollToItem(0) }
                    }
                }
            }
            item { Spacer(Modifier.height(60.dp)) }
        }
    }
}

@Composable
internal fun FieldBriefingScreen(
    briefing: FieldBriefing?,
    loading: Boolean,
    onBack: () -> Unit,
    onOpenSightings: (BriefingItem) -> Unit,
) {
    var previewItem by remember { mutableStateOf<BriefingItem?>(null) }
    var selectedLifeGroups by rememberSaveable { mutableStateOf(emptyList<String>()) }
    var lifeFilterOpen by remember { mutableStateOf(false) }
    val visibleSections = briefing?.sections.orEmpty().mapNotNull { section ->
        val visibleItems = section.items.filter { item ->
            selectedLifeGroups.isEmpty() || selectedLifeGroups.any {
                it.equals(item.iconicTaxonName, ignoreCase = true)
            }
        }
        section.copy(items = visibleItems).takeIf { visibleItems.isNotEmpty() }
    }
    val coverSpecies = briefing?.sections.orEmpty()
        .flatMap { it.items }
        .firstOrNull { it.referencePhotoUrl.isNotBlank() }
    BackHandler(onBack = onBack)
    LazyColumn(Modifier.fillMaxSize().background(Parchment)) {
        item {
            FieldPageHero(
                kicker = "FIELD BRIEFING · ${briefing?.targetDate.orEmpty()}",
                title = "What should I look for today?",
                subtitle = briefing?.areaName.orEmpty(),
                imageUrl = coverSpecies?.referencePhotoUrl.orEmpty(),
                imageDescription = coverSpecies?.let { "${it.commonName}, the first illustrated species in today's briefing" }
                    ?: "Field briefing cover",
                onBack = onBack,
            )
        }
        if (loading || briefing == null) {
            item {
                FieldPageLoading(
                    title = "Preparing today’s field briefing…",
                    detail = "Matching the season with nearby reports and your own field records.",
                )
            }
        } else {
            item {
                Text(
                    briefing.guidance,
                    style = MaterialTheme.typography.bodyMedium,
                    fontStyle = FontStyle.Italic,
                    fontWeight = FontWeight.Medium,
                    color = Ink,
                    modifier = Modifier.padding(20.dp),
                )
            }
            item {
                Row(
                    Modifier.fillMaxWidth().background(Paper).padding(horizontal = 20.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("LIFE GROUP", style = MaterialTheme.typography.labelMedium, color = TrailText)
                        Text(
                            if (selectedLifeGroups.isEmpty()) "Every recommendation" else "Filtered briefing",
                            style = MaterialTheme.typography.bodyMedium,
                            color = InkMuted,
                            fontWeight = FontWeight.Medium,
                        )
                    }
                    TextButton(onClick = { lifeFilterOpen = true }) {
                        Text(iconicTaxonLabel(selectedLifeGroups))
                        Icon(
                            Icons.Rounded.KeyboardArrowDown,
                            contentDescription = "Choose a life group",
                            modifier = Modifier.padding(start = 3.dp).size(18.dp),
                        )
                    }
                }
            }
            visibleSections.forEach { section ->
                item {
                    Text(
                        section.title,
                        style = MaterialTheme.typography.headlineSmall,
                        color = Ink,
                        modifier = Modifier.padding(start = 20.dp, end = 20.dp, top = 28.dp, bottom = 4.dp),
                    )
                    Text(
                        "${section.items.size} field note${if (section.items.size == 1) "" else "s"}",
                        style = MaterialTheme.typography.labelMedium,
                        color = TrailText,
                        modifier = Modifier.padding(horizontal = 20.dp, vertical = 2.dp),
                    )
                }
                items(section.items, key = { "${section.title}:${it.key}" }) { item ->
                    BriefingRow(
                        item = item,
                        onOpenSpecies = { previewItem = item },
                        onOpenSightings = { onOpenSightings(item) },
                    )
                }
            }
            if (visibleSections.isEmpty()) {
                item {
                    Text(
                        "No ${iconicTaxonLabel(selectedLifeGroups).lowercase(Locale.US)} appear in today’s briefing.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = InkMuted,
                        modifier = Modifier.padding(20.dp),
                    )
                }
            }
            item { Spacer(Modifier.height(60.dp)) }
        }
    }
    previewItem?.let { item ->
        DiscoveryTaxonPreviewDialog(
            taxon = item.toDiscoveryTaxon(),
            onMap = item.taxonId?.let { { onOpenSightings(item) } },
            onDismiss = { previewItem = null },
        )
    }
    if (lifeFilterOpen) {
        NearbyLifeFilterSheet(
            selectedGroups = selectedLifeGroups,
            onApply = {
                selectedLifeGroups = it
                lifeFilterOpen = false
            },
            onDismiss = { lifeFilterOpen = false },
        )
    }
}

@Composable
private fun BriefingRow(
    item: BriefingItem,
    onOpenSpecies: () -> Unit,
    onOpenSightings: () -> Unit,
) {
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 15.dp),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(94.dp).background(Color(0xFFD0CFBD)).clickable(
                    enabled = item.referencePhotoUrl.isNotBlank(),
                    onClick = onOpenSpecies,
                ),
            ) {
                if (item.referencePhotoUrl.isNotBlank()) {
                    AsyncImage(
                        model = item.referencePhotoUrl,
                        contentDescription = item.commonName,
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop,
                    )
                } else {
                    Icon(
                        lifeGroupIcon(item.iconicTaxonName),
                        contentDescription = null,
                        tint = Moss.copy(alpha = 0.55f),
                        modifier = Modifier.align(Alignment.Center).size(34.dp),
                    )
                }
            }
            Column(Modifier.weight(1f).padding(start = 14.dp).clickable(onClick = onOpenSpecies)) {
                Text(item.commonName, style = MaterialTheme.typography.titleLarge, color = Ink)
                if (item.scientificName.isNotBlank()) {
                    Text(item.scientificName, style = MaterialTheme.typography.bodyMedium, color = FernText, fontStyle = FontStyle.Italic)
                }
                val credit = listOf(item.referencePhotoAttribution, item.referencePhotoLicenseCode)
                    .filter(String::isNotBlank)
                    .joinToString(" · ")
                if (credit.isNotBlank()) {
                    Text(
                        credit,
                        style = MaterialTheme.typography.labelMedium,
                        color = InkMuted,
                        modifier = Modifier.padding(top = 4.dp),
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
        item.reasons.forEach { reason ->
            Text(
                "· $reason",
                style = MaterialTheme.typography.bodyMedium,
                color = Ink,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
        Row(Modifier.fillMaxWidth().padding(top = 7.dp), horizontalArrangement = Arrangement.End) {
            TextButton(onClick = onOpenSpecies) { Text("Species details") }
            if (item.taxonId != null) {
                TextButton(onClick = onOpenSightings) {
                    Icon(Icons.Rounded.Map, contentDescription = null, modifier = Modifier.size(18.dp))
                    Text("Map sightings", modifier = Modifier.padding(start = 6.dp))
                }
            }
        }
    }
    HorizontalDivider(color = Line, modifier = Modifier.padding(start = 20.dp))
}

@Composable
private fun LifeRecordedGroups(groups: List<PlaceTaxonGroup>, onOpenSpecies: (String) -> Unit) {
    var expanded by remember(groups) { mutableStateOf(setOf<String>()) }
    groups.forEach { group ->
        val isExpanded = group.name in expanded
        LifeGroupHeader(
            name = group.name,
            count = group.count,
            expanded = isExpanded,
            onClick = {
                expanded = if (isExpanded) expanded - group.name else expanded + group.name
            },
        )
        AnimatedVisibility(
            visible = isExpanded,
            enter = fadeIn() + expandVertically(),
            exit = fadeOut() + shrinkVertically(),
        ) {
            Column(Modifier.fillMaxWidth().padding(start = 50.dp, bottom = 10.dp)) {
                group.species.forEach { species ->
                    Row(
                        Modifier.fillMaxWidth()
                            .clickable(enabled = species.key.isNotBlank()) { onOpenSpecies(species.key) }
                            .padding(vertical = 9.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Box(Modifier.size(44.dp).clip(CircleShape).background(Color(0xFFD0CFBD))) {
                            if (species.referencePhotoUrl.isNotBlank()) {
                                AsyncImage(
                                    model = species.referencePhotoUrl,
                                    contentDescription = species.commonName,
                                    modifier = Modifier.fillMaxSize(),
                                    contentScale = ContentScale.Crop,
                                )
                            } else {
                                Icon(
                                    lifeGroupIcon(group.name),
                                    contentDescription = null,
                                    tint = Moss.copy(alpha = 0.55f),
                                    modifier = Modifier.align(Alignment.Center).size(20.dp),
                                )
                            }
                        }
                        Column(Modifier.weight(1f).padding(start = 11.dp)) {
                            Text(species.commonName, style = MaterialTheme.typography.bodyLarge, color = Ink)
                            Text(
                                listOf(
                                    species.scientificName,
                                    "${species.encounterCount} encounter${if (species.encounterCount == 1) "" else "s"}",
                                ).filter(String::isNotBlank).joinToString(" · "),
                                style = MaterialTheme.typography.bodyMedium,
                                color = InkMuted,
                                fontStyle = FontStyle.Italic,
                                fontWeight = FontWeight.Medium,
                            )
                        }
                        Icon(
                            Icons.AutoMirrored.Rounded.ArrowForward,
                            contentDescription = "Open ${species.commonName} in the species log",
                            tint = FernText,
                            modifier = Modifier.padding(horizontal = 10.dp).size(18.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun LifeGroupHeader(name: String, count: Int, expanded: Boolean, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(38.dp).background(Color(0xFFE0E7D8), CircleShape), contentAlignment = Alignment.Center) {
            Icon(lifeGroupIcon(name), contentDescription = null, tint = Moss, modifier = Modifier.size(22.dp))
        }
        Text(friendlyTaxon(name), style = MaterialTheme.typography.bodyLarge, color = Ink, modifier = Modifier.weight(1f).padding(start = 12.dp))
        Text(count.toString(), style = MaterialTheme.typography.titleMedium, color = FernText)
        Icon(
            Icons.Rounded.KeyboardArrowDown,
            contentDescription = if (expanded) "Collapse" else "Expand",
            tint = InkMuted,
            modifier = Modifier.padding(start = 6.dp).rotate(if (expanded) 180f else 0f),
        )
    }
}

@Composable
internal fun HikeComparisonScreen(
    comparison: HikeComparison?,
    loading: Boolean,
    coverUrl: String,
    onBack: () -> Unit,
    onOpenSpecies: (String) -> Unit,
) {
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val latestHike = comparison?.let {
        if (it.hikeA.hikeDate >= it.hikeB.hikeDate) it.hikeA else it.hikeB
    }
    BackHandler(onBack = onBack)
    LazyColumn(Modifier.fillMaxSize().background(Parchment), state = listState) {
        item {
            FieldPageHero(
                kicker = "FIELD JOURNAL COMPARISON",
                title = "What changed between these visits?",
                subtitle = comparison?.let { "${it.hikeA.hikeDate}  ↔  ${it.hikeB.hikeDate}" }.orEmpty(),
                imageUrl = coverUrl,
                imageDescription = latestHike?.let { "Cover photo from ${it.title}, the most recent compared hike" }
                    ?: "Field journal comparison cover",
                onBack = onBack,
            )
        }
        if (loading || comparison == null) {
            item {
                Box(Modifier.fillMaxWidth().padding(56.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Trail)
                }
            }
        } else {
            item {
                Row(Modifier.fillMaxWidth().padding(20.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    ComparisonColumn(comparison.hikeA, Modifier.weight(1f))
                    Box(Modifier.width(1.dp).height(150.dp).background(Line))
                    ComparisonColumn(comparison.hikeB, Modifier.weight(1f))
                }
            }
            item {
                Text(
                    comparison.guidance,
                    style = MaterialTheme.typography.bodySmall,
                    fontStyle = FontStyle.Italic,
                    color = InkMuted,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
                )
            }
            if (comparison.weatherA != null || comparison.weatherB != null) {
                item {
                    FieldSection("CONDITIONS", "Historical weather summarized over each recorded hike interval.") {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                            ComparisonWeatherColumn(
                                label = comparison.hikeA.hikeDate,
                                weather = comparison.weatherA,
                                modifier = Modifier.weight(1f),
                            )
                            ComparisonWeatherColumn(
                                label = comparison.hikeB.hikeDate,
                                weather = comparison.weatherB,
                                modifier = Modifier.weight(1f),
                            )
                        }
                        Text(
                            "Open-Meteo weather data · CC BY 4.0",
                            style = MaterialTheme.typography.labelSmall,
                            color = InkMuted,
                            modifier = Modifier.padding(top = 14.dp),
                        )
                    }
                }
            }
            item { SpeciesDifference("RECORDED ON BOTH", comparison.shared, onOpenSpecies) }
            item { SpeciesDifference("ONLY ON ${comparison.hikeA.hikeDate}", comparison.onlyA, onOpenSpecies) }
            item { SpeciesDifference("ONLY ON ${comparison.hikeB.hikeDate}", comparison.onlyB, onOpenSpecies) }
            item {
                FieldBackToTop {
                    scope.launch { listState.animateScrollToItem(0) }
                }
            }
            item { Spacer(Modifier.height(60.dp)) }
        }
    }
}

@Composable
private fun ComparisonWeatherColumn(label: String, weather: WeatherSnapshot?, modifier: Modifier = Modifier) {
    Column(modifier) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Rounded.Cloud, contentDescription = null, tint = Trail, modifier = Modifier.size(20.dp))
            Text(label, style = MaterialTheme.typography.labelSmall, color = TrailText, modifier = Modifier.padding(start = 6.dp))
        }
        if (weather == null) {
            Text("Not enriched", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 8.dp))
        } else {
            Text(weatherTemperature(weather), style = MaterialTheme.typography.titleLarge, color = Ink, modifier = Modifier.padding(top = 7.dp))
            Text(weather.conditionLabel, style = MaterialTheme.typography.bodyMedium, color = Fern)
            weather.precipitationTotalMm?.let {
                Text("${String.format(Locale.US, "%.2f", it / 25.4)} in rain", style = MaterialTheme.typography.bodySmall, color = InkMuted)
            }
            weather.relativeHumidityMeanPercent?.let {
                Text("${it.roundToInt()}% avg humidity", style = MaterialTheme.typography.bodySmall, color = InkMuted)
            }
        }
    }
}

private fun weatherTemperature(weather: WeatherSnapshot): String {
    fun fahrenheit(value: Double): Int = (value * 9 / 5 + 32).roundToInt()
    return when {
        weather.temperatureMinC != null && weather.temperatureMaxC != null ->
            "${fahrenheit(weather.temperatureMinC)}–${fahrenheit(weather.temperatureMaxC)}°F"
        weather.temperatureMeanC != null -> "${fahrenheit(weather.temperatureMeanC)}°F"
        else -> "Temperature unavailable"
    }
}

@Composable
private fun ComparisonColumn(hike: ComparisonHike, modifier: Modifier = Modifier) {
    Column(modifier) {
        Text(hike.hikeDate, style = MaterialTheme.typography.labelSmall, color = TrailText)
        Text(hike.title, style = MaterialTheme.typography.titleLarge, color = Ink, maxLines = 2, overflow = TextOverflow.Ellipsis)
        Text(hike.locationName, style = MaterialTheme.typography.bodySmall, color = InkMuted, maxLines = 1)
        Spacer(Modifier.height(12.dp))
        Text("${hike.speciesCount} species", style = MaterialTheme.typography.titleMedium, color = Fern)
        Text("${hike.observationCount} observations", style = MaterialTheme.typography.bodyMedium, color = InkMuted)
        Text(formatMiles(hike.distanceMiles ?: 0.0), style = MaterialTheme.typography.bodyMedium, color = InkMuted)
    }
}

@Composable
private fun SpeciesDifference(
    title: String,
    species: List<ComparisonSpecies>,
    onOpenSpecies: (String) -> Unit,
) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 20.dp)) {
        Text(title, style = MaterialTheme.typography.labelSmall, color = TrailText)
        if (species.isEmpty()) {
            Text("No confirmed species in this group.", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 10.dp))
        } else {
            species.forEach { item ->
                Row(
                    Modifier.fillMaxWidth()
                        .clickable(enabled = item.key.isNotBlank()) { onOpenSpecies(item.key) }
                        .padding(vertical = 7.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(Modifier.size(54.dp).clip(CircleShape).background(Color(0xFFD0CFBD))) {
                        if (item.referencePhotoUrl.isNotBlank()) {
                            AsyncImage(
                                model = item.referencePhotoUrl,
                                contentDescription = item.commonName,
                                modifier = Modifier.fillMaxSize(),
                                contentScale = ContentScale.Crop,
                            )
                        } else {
                            Icon(
                                lifeGroupIcon(item.iconicTaxonName),
                                contentDescription = null,
                                tint = Moss.copy(alpha = 0.55f),
                                modifier = Modifier.align(Alignment.Center).size(24.dp),
                            )
                        }
                    }
                    Column(Modifier.weight(1f).padding(start = 12.dp)) {
                        Text(item.commonName, style = MaterialTheme.typography.bodyLarge, color = Ink)
                        Text(item.scientificName, style = MaterialTheme.typography.bodySmall, color = InkMuted, fontStyle = FontStyle.Italic)
                    }
                    Icon(
                        Icons.AutoMirrored.Rounded.ArrowForward,
                        contentDescription = "Open ${item.commonName} in the species log",
                        tint = FernText,
                        modifier = Modifier.padding(start = 10.dp).size(18.dp),
                    )
                }
            }
        }
    }
    HorizontalDivider(color = Line)
}

@Composable
internal fun SeasonalBand(history: SeasonalHistory, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            history.months.take(12).forEach { month ->
                Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                    Box(
                        Modifier.fillMaxWidth().height((8 + 34 * month.relativeIntensity).dp)
                            .background(
                                if (month.count > 0) Trail.copy(alpha = 0.35f + (month.relativeIntensity * 0.65f).toFloat())
                                else Line,
                            ),
                    )
                    Text(month.label.take(1), style = MaterialTheme.typography.labelMedium, color = Ink, modifier = Modifier.padding(top = 5.dp))
                }
            }
        }
        if (history.observationCount == 0) {
            Text("No dated observations yet.", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 10.dp))
        }
    }
}

@Composable
private fun FieldPageHero(
    kicker: String,
    title: String,
    subtitle: String,
    onBack: () -> Unit,
    imageUrl: String = "",
    imageDescription: String = title,
) {
    Box(
        Modifier.fillMaxWidth().height(360.dp).background(
            Brush.linearGradient(listOf(Color(0xFF315844), Moss)),
        ),
    ) {
        if (imageUrl.isNotBlank()) {
            AsyncImage(
                model = ImageRequest.Builder(LocalContext.current)
                    .data(imageUrl)
                    .crossfade(220)
                    .build(),
                contentDescription = imageDescription,
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop,
            )
        }
        Box(
            Modifier.fillMaxSize().background(
                Brush.verticalGradient(
                    listOf(Color(0xA3131D17), Color(0x22131D17), Color(0xE6111A14)),
                ),
            ),
        )
        FilledIconButton(
            onClick = onBack,
            modifier = Modifier.statusBarsPadding().padding(10.dp),
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = Color(0xB0142119)),
        ) {
            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back", tint = Paper)
        }
        Column(Modifier.align(Alignment.BottomStart).padding(horizontal = 20.dp, vertical = 24.dp)) {
            Text("HikeJournal", style = MaterialTheme.typography.headlineSmall, color = Paper)
            Text(
                kicker,
                style = MaterialTheme.typography.labelMedium,
                color = Color(0xFFF1C37A),
                modifier = Modifier.padding(top = 14.dp),
            )
            Text(title, style = MaterialTheme.typography.headlineLarge, color = Paper, modifier = Modifier.padding(top = 4.dp))
            if (subtitle.isNotBlank()) {
                Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Rounded.LocationOn, contentDescription = null, tint = Paper, modifier = Modifier.size(18.dp))
                    Text(
                        subtitle,
                        style = MaterialTheme.typography.bodyMedium,
                        color = Paper,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(start = 5.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun FieldPageLoading(title: String, detail: String) {
    Row(
        Modifier.fillMaxWidth().background(Paper).padding(horizontal = 20.dp, vertical = 28.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(52.dp).background(Color(0xFFE0E7D8), CircleShape), contentAlignment = Alignment.Center) {
            CircularProgressIndicator(Modifier.size(34.dp), color = Trail, strokeWidth = 2.dp)
            Icon(Icons.Rounded.LocalFlorist, contentDescription = null, tint = Moss, modifier = Modifier.size(18.dp))
        }
        Column(Modifier.weight(1f).padding(start = 16.dp)) {
            Text(title, style = MaterialTheme.typography.titleLarge, color = Ink)
            Text(
                detail,
                style = MaterialTheme.typography.bodyMedium,
                color = InkMuted,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(top = 3.dp),
            )
        }
    }
    HorizontalDivider(color = Line)
}

@Composable
internal fun FieldBackToTop(onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 22.dp),
        horizontalArrangement = Arrangement.Center,
    ) {
        TextButton(onClick = onClick) {
            Icon(Icons.Rounded.KeyboardArrowUp, contentDescription = null, modifier = Modifier.size(20.dp))
            Text("Back to top", modifier = Modifier.padding(start = 5.dp))
        }
    }
}

@Composable
private fun FieldSection(kicker: String, subtitle: String, content: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 24.dp)) {
        Text(kicker, style = MaterialTheme.typography.labelMedium, color = TrailText)
        Text(
            subtitle,
            style = MaterialTheme.typography.bodyMedium,
            color = Ink,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(top = 4.dp, bottom = 18.dp),
        )
        content()
    }
    HorizontalDivider(color = Line)
}

@Composable
private fun FieldNumber(value: String, label: String) {
    Column(horizontalAlignment = Alignment.Start) {
        Text(value, style = MaterialTheme.typography.headlineMedium, color = FernText, fontWeight = FontWeight.Bold)
        Text(label, style = MaterialTheme.typography.labelMedium, color = InkMuted)
    }
}

private fun formatMiles(value: Double): String = String.format(Locale.US, "%.1f mi", value)

private fun friendlyTaxon(value: String): String = when (value.lowercase(Locale.US)) {
    "plantae" -> "Plants"
    "aves" -> "Birds"
    "mammalia" -> "Mammals"
    "fungi" -> "Fungi"
    "insecta" -> "Insects"
    "arachnida" -> "Arachnids"
    "reptilia" -> "Reptiles"
    "amphibia" -> "Amphibians"
    "actinopterygii" -> "Fish"
    "mollusca" -> "Mollusks"
    "animalia" -> "Other animals"
    else -> value.ifBlank { "Other" }
}

private fun lifeGroupIcon(value: String): ImageVector = when (value.lowercase(Locale.US)) {
    "plantae" -> Icons.Rounded.LocalFlorist
    "aves" -> Icons.Rounded.FlutterDash
    "mammalia", "reptilia", "amphibia", "actinopterygii", "mollusca", "animalia" -> Icons.Rounded.Pets
    "fungi" -> Icons.Rounded.Park
    "insecta", "arachnida" -> Icons.Rounded.BugReport
    else -> Icons.Rounded.Explore
}
