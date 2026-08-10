package com.hikejournal.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.ArrowForward
import androidx.compose.material.icons.rounded.BugReport
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.Cloud
import androidx.compose.material.icons.rounded.Explore
import androidx.compose.material.icons.rounded.FlutterDash
import androidx.compose.material.icons.rounded.KeyboardArrowDown
import androidx.compose.material.icons.rounded.LocalFlorist
import androidx.compose.material.icons.rounded.LocationOn
import androidx.compose.material.icons.rounded.Map
import androidx.compose.material.icons.rounded.Park
import androidx.compose.material.icons.rounded.Pets
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
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
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.TrailText
import java.util.Locale
import kotlin.math.roundToInt

@Composable
internal fun PlaceProfileScreen(
    profile: PlaceProfile?,
    loading: Boolean,
    onBack: () -> Unit,
    onOpenHike: (String) -> Unit,
) {
    BackHandler(onBack = onBack)
    LazyColumn(Modifier.fillMaxSize().background(Parchment)) {
        item {
            FieldPageHero(
                kicker = "PLACE PROFILE",
                title = profile?.name ?: "Reading this place…",
                subtitle = profile?.let {
                    "${it.outingCount} recorded visit${if (it.outingCount == 1) "" else "s"} · ${formatMiles(it.totalDistanceMiles)}"
                }.orEmpty(),
                onBack = onBack,
            )
        }
        if (loading || profile == null) {
            item {
                Box(Modifier.fillMaxWidth().padding(56.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Trail)
                }
            }
        } else {
            item {
                Column(Modifier.padding(horizontal = 20.dp, vertical = 28.dp)) {
                    Text("YOUR RECORD HERE", style = MaterialTheme.typography.labelSmall, color = TrailText)
                    Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                        FieldNumber(profile.speciesCount.toString(), "SPECIES")
                        FieldNumber(profile.observationCount.toString(), "OBSERVATIONS")
                        FieldNumber(profile.firstVisit?.take(4).orEmpty().ifBlank { "—" }, "SINCE")
                    }
                    Text(
                        profile.guidance,
                        style = MaterialTheme.typography.bodySmall,
                        color = InkMuted,
                        fontStyle = FontStyle.Italic,
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
                            LifeRecordedGroups(profile.taxonGroups)
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
                    style = MaterialTheme.typography.labelSmall,
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
                        Text(visit.hikeDate, style = MaterialTheme.typography.labelSmall, color = TrailText)
                        Text(visit.title, style = MaterialTheme.typography.titleLarge, color = Ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(
                            "${visit.speciesCount} species · ${visit.newSpeciesCount} new then · ${visit.cumulativeSpeciesCount} cumulative",
                            style = MaterialTheme.typography.bodySmall,
                            color = InkMuted,
                        )
                    }
                    Icon(Icons.AutoMirrored.Rounded.ArrowForward, contentDescription = "Open journal", tint = Fern)
                }
                HorizontalDivider(color = Line, modifier = Modifier.padding(start = 20.dp))
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
    BackHandler(onBack = onBack)
    LazyColumn(Modifier.fillMaxSize().background(Parchment)) {
        item {
            FieldPageHero(
                kicker = "FIELD BRIEFING · ${briefing?.targetDate.orEmpty()}",
                title = "What should I look for today?",
                subtitle = briefing?.areaName.orEmpty(),
                onBack = onBack,
            )
        }
        if (loading || briefing == null) {
            item {
                Box(Modifier.fillMaxWidth().padding(56.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Trail)
                }
            }
        } else {
            item {
                Text(
                    briefing.guidance,
                    style = MaterialTheme.typography.bodySmall,
                    fontStyle = FontStyle.Italic,
                    color = InkMuted,
                    modifier = Modifier.padding(20.dp),
                )
            }
            briefing.sections.forEach { section ->
                item {
                    Text(
                        section.title.uppercase(Locale.US),
                        style = MaterialTheme.typography.labelSmall,
                        color = TrailText,
                        modifier = Modifier.padding(start = 20.dp, top = 22.dp, bottom = 4.dp),
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
                    Text(item.scientificName, style = MaterialTheme.typography.bodyMedium, color = Fern, fontStyle = FontStyle.Italic)
                }
                val credit = listOf(item.referencePhotoAttribution, item.referencePhotoLicenseCode)
                    .filter(String::isNotBlank)
                    .joinToString(" · ")
                if (credit.isNotBlank()) {
                    Text(
                        credit,
                        style = MaterialTheme.typography.labelSmall,
                        color = InkMuted,
                        modifier = Modifier.padding(top = 4.dp),
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
        item.reasons.forEach { reason ->
            Text("· $reason", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 4.dp))
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
private fun LifeRecordedGroups(groups: List<PlaceTaxonGroup>) {
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
                    Row(Modifier.fillMaxWidth().padding(vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(42.dp).background(Color(0xFFD0CFBD), CircleShape)) {
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
                                style = MaterialTheme.typography.bodySmall,
                                color = InkMuted,
                                fontStyle = FontStyle.Italic,
                            )
                        }
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
        Text(count.toString(), style = MaterialTheme.typography.titleMedium, color = Fern)
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
    onBack: () -> Unit,
) {
    BackHandler(onBack = onBack)
    LazyColumn(Modifier.fillMaxSize().background(Parchment)) {
        item {
            FieldPageHero(
                kicker = "FIELD JOURNAL COMPARISON",
                title = "What changed between these visits?",
                subtitle = comparison?.let { "${it.hikeA.hikeDate}  ↔  ${it.hikeB.hikeDate}" }.orEmpty(),
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
            item { SpeciesDifference("RECORDED ON BOTH", comparison.shared) }
            item { SpeciesDifference("ONLY ON ${comparison.hikeA.hikeDate}", comparison.onlyA) }
            item { SpeciesDifference("ONLY ON ${comparison.hikeB.hikeDate}", comparison.onlyB) }
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
private fun SpeciesDifference(title: String, species: List<ComparisonSpecies>) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 20.dp)) {
        Text(title, style = MaterialTheme.typography.labelSmall, color = TrailText)
        if (species.isEmpty()) {
            Text("No confirmed species in this group.", style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 10.dp))
        } else {
            species.forEach { item ->
                Row(Modifier.fillMaxWidth().padding(vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(6.dp).background(Trail))
                    Column(Modifier.padding(start = 11.dp)) {
                        Text(item.commonName, style = MaterialTheme.typography.bodyLarge, color = Ink)
                        Text(item.scientificName, style = MaterialTheme.typography.bodySmall, color = InkMuted, fontStyle = FontStyle.Italic)
                    }
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
                    Text(month.label.take(1), style = MaterialTheme.typography.labelSmall, color = InkMuted, modifier = Modifier.padding(top = 5.dp))
                }
            }
        }
        if (history.observationCount == 0) {
            Text("No dated observations yet.", style = MaterialTheme.typography.bodySmall, color = InkMuted, modifier = Modifier.padding(top = 10.dp))
        }
    }
}

@Composable
private fun FieldPageHero(kicker: String, title: String, subtitle: String, onBack: () -> Unit) {
    Box(Modifier.fillMaxWidth().background(Moss).statusBarsPadding().padding(bottom = 32.dp)) {
        Column(Modifier.fillMaxWidth()) {
            IconButton(onClick = onBack, modifier = Modifier.padding(start = 4.dp, top = 4.dp)) {
                Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Back", tint = Paper)
            }
            Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp)) {
                Text("HikeJournal", style = MaterialTheme.typography.titleMedium, color = Color(0xFFD6E0D3))
                Text(kicker, style = MaterialTheme.typography.labelSmall, color = Color(0xFFE7B868), modifier = Modifier.padding(top = 20.dp))
                Text(title, style = MaterialTheme.typography.displaySmall, color = Paper, modifier = Modifier.padding(top = 4.dp))
                if (subtitle.isNotBlank()) {
                    Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Rounded.LocationOn, contentDescription = null, tint = Color(0xFFD6E0D3), modifier = Modifier.size(18.dp))
                        Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = Color(0xFFD6E0D3), modifier = Modifier.padding(start = 5.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun FieldSection(kicker: String, subtitle: String, content: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 24.dp)) {
        Text(kicker, style = MaterialTheme.typography.labelSmall, color = TrailText)
        Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = InkMuted, modifier = Modifier.padding(top = 4.dp, bottom = 18.dp))
        content()
    }
    HorizontalDivider(color = Line)
}

@Composable
private fun FieldNumber(value: String, label: String) {
    Column(horizontalAlignment = Alignment.Start) {
        Text(value, style = MaterialTheme.typography.headlineMedium, color = Fern, fontWeight = FontWeight.Bold)
        Text(label, style = MaterialTheme.typography.labelSmall, color = InkMuted)
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
