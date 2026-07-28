@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.hikejournal.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.DirectionsWalk
import androidx.compose.material.icons.rounded.BugReport
import androidx.compose.material.icons.rounded.Explore
import androidx.compose.material.icons.rounded.Flag
import androidx.compose.material.icons.rounded.FlutterDash
import androidx.compose.material.icons.rounded.Landscape
import androidx.compose.material.icons.rounded.LocalFlorist
import androidx.compose.material.icons.rounded.Park
import androidx.compose.material.icons.rounded.Pets
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Route
import androidx.compose.material.icons.rounded.Star
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.hikejournal.app.AppState
import com.hikejournal.app.data.BadgeCategory
import com.hikejournal.app.data.BadgeFinish
import com.hikejournal.app.data.BadgeMetric
import com.hikejournal.app.data.BadgeSymbol
import com.hikejournal.app.data.TrailBadge
import com.hikejournal.app.data.calculateTrailBadges
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.TrailText
import kotlinx.coroutines.delay
import java.util.Locale
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

@Composable
fun BadgesScreen(
    state: AppState,
    loading: Boolean,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
) {
    val badges = calculateTrailBadges(state.hikes, state.species, state.speciesQuests)
    val earnedCount = badges.count { it.earned }
    val nextBadge = badges
        .filterNot { it.earned }
        .maxWithOrNull(compareBy<TrailBadge> { it.progress }.thenByDescending { -it.definition.target })
    var selectedBadge by remember { mutableStateOf<TrailBadge?>(null) }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(Parchment),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 52.dp),
    ) {
        item {
            BadgesHeader(
                earnedCount = earnedCount,
                totalCount = badges.size,
                nextBadge = nextBadge,
                loading = loading,
                onBack = onBack,
                onRefresh = onRefresh,
            )
        }
        if (loading) {
            item {
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp, color = Moss)
                    Text(
                        "Refreshing species and Field Quest progress…",
                        style = MaterialTheme.typography.bodyMedium,
                        color = InkMuted,
                        modifier = Modifier.padding(start = 10.dp),
                    )
                }
            }
        }
        state.badgeNotice?.let { notice ->
            item {
                Text(
                    notice,
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.fillMaxWidth().background(Color(0xFFE7E5D9))
                        .padding(horizontal = 20.dp, vertical = 11.dp),
                )
            }
        }
        BadgeCategory.entries.forEach { category ->
            val categoryBadges = badges.filter { it.definition.category == category }
            item(key = "heading-${category.name}") {
                BadgeSectionHeader(category)
            }
            item(key = "grid-${category.name}") {
                BadgeGrid(
                    badges = categoryBadges,
                    startIndex = badges.indexOf(categoryBadges.first()),
                    onSelect = { selectedBadge = it },
                )
            }
        }
    }

    selectedBadge?.let { badge ->
        BadgeDetailSheet(badge = badge, onDismiss = { selectedBadge = null })
    }
}

@Composable
private fun BadgesHeader(
    earnedCount: Int,
    totalCount: Int,
    nextBadge: TrailBadge?,
    loading: Boolean,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
) {
    Column(
        Modifier.fillMaxWidth().background(Moss).statusBarsPadding().padding(bottom = 24.dp),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(start = 6.dp, end = 6.dp, top = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back", tint = Paper)
            }
            Column(Modifier.weight(1f)) {
                Text("HIKEJOURNAL", style = MaterialTheme.typography.labelSmall, color = Color(0xFFB8C9B6))
                Text("Trail medals", style = MaterialTheme.typography.headlineLarge, color = Paper)
            }
            IconButton(onClick = onRefresh, enabled = !loading) {
                if (loading) {
                    CircularProgressIndicator(Modifier.size(19.dp), color = Paper, strokeWidth = 2.dp)
                } else {
                    Icon(Icons.Rounded.Refresh, "Refresh medals", tint = Paper)
                }
            }
        }
        Text(
            "$earnedCount OF $totalCount EARNED · LIFETIME PROGRESS",
            style = MaterialTheme.typography.labelSmall,
            color = Trail,
            modifier = Modifier.padding(start = 20.dp, top = 4.dp),
        )
        if (nextBadge != null) {
            Row(
                Modifier.fillMaxWidth().padding(start = 16.dp, end = 20.dp, top = 20.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                MedalSeal(
                    badge = nextBadge,
                    modifier = Modifier.size(102.dp),
                    forcePreview = true,
                )
                Column(Modifier.weight(1f).padding(start = 16.dp)) {
                    Text("NEXT MEDAL", style = MaterialTheme.typography.labelSmall, color = Color(0xFFB8C9B6))
                    Text(nextBadge.definition.title, style = MaterialTheme.typography.headlineSmall, color = Paper)
                    Text(
                        badgeProgressLabel(nextBadge),
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color(0xFFD8E0D5),
                        modifier = Modifier.padding(top = 2.dp),
                    )
                    LinearProgressIndicator(
                        progress = { nextBadge.progress },
                        modifier = Modifier.fillMaxWidth().padding(top = 10.dp).height(3.dp),
                        color = Trail,
                        trackColor = Color(0xFF486357),
                    )
                }
            }
        } else {
            Text(
                "Every trail medal is in your collection.",
                style = MaterialTheme.typography.titleMedium,
                color = Paper,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 22.dp),
            )
        }
    }
}

@Composable
private fun BadgeSectionHeader(category: BadgeCategory) {
    Column(Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, top = 30.dp, bottom = 14.dp)) {
        Text(category.label, style = MaterialTheme.typography.headlineMedium, color = Ink)
        Text(category.description, style = MaterialTheme.typography.bodyMedium, color = InkMuted)
    }
}

@Composable
private fun BadgeGrid(
    badges: List<TrailBadge>,
    startIndex: Int,
    onSelect: (TrailBadge) -> Unit,
) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp)) {
        badges.chunked(3).forEachIndexed { rowIndex, rowBadges ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                rowBadges.forEachIndexed { columnIndex, badge ->
                    BadgeTile(
                        badge = badge,
                        entranceIndex = startIndex + rowIndex * 3 + columnIndex,
                        onClick = { onSelect(badge) },
                        modifier = Modifier.weight(1f),
                    )
                }
                repeat(3 - rowBadges.size) {
                    Spacer(Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
private fun BadgeTile(
    badge: TrailBadge,
    entranceIndex: Int,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var visible by remember(badge.definition.id) { mutableStateOf(false) }
    val interactionSource = remember { MutableInteractionSource() }
    val pressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed) 0.94f else 1f,
        animationSpec = tween(130),
        label = "medal-press",
    )
    LaunchedEffect(badge.definition.id) {
        delay((entranceIndex % 9) * 38L)
        visible = true
    }
    AnimatedVisibility(
        visible = visible,
        modifier = modifier,
        enter = fadeIn(tween(260)) + slideInVertically(tween(300)) { it / 8 },
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .graphicsLayer { scaleX = scale; scaleY = scale }
                .clickable(
                    interactionSource = interactionSource,
                    indication = null,
                    onClick = onClick,
                )
                .padding(horizontal = 4.dp, vertical = 10.dp)
                .alpha(if (badge.earned) 1f else 0.76f),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            MedalSeal(badge = badge, modifier = Modifier.size(86.dp))
            Text(
                badge.definition.title,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
                color = if (badge.earned) Ink else InkMuted,
                textAlign = TextAlign.Center,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.fillMaxWidth().padding(top = 7.dp),
            )
            Text(
                if (badge.earned) "EARNED" else compactProgressLabel(badge),
                style = MaterialTheme.typography.labelSmall,
                color = if (badge.earned) TrailText else InkMuted,
                textAlign = TextAlign.Center,
                maxLines = 1,
                modifier = Modifier.fillMaxWidth().padding(top = 2.dp),
            )
        }
    }
}

@Composable
private fun MedalSeal(
    badge: TrailBadge,
    modifier: Modifier = Modifier,
    forcePreview: Boolean = false,
) {
    val active = badge.earned || forcePreview
    val palette = medalPalette(badge.definition.finish, active)
    Box(modifier, contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val centerX = size.width / 2f
            val medalCenter = androidx.compose.ui.geometry.Offset(centerX, size.height * 0.45f)
            val outerRadius = size.minDimension * 0.37f
            val ribbonTop = size.height * 0.55f
            val ribbonBottom = size.height * 0.96f
            val leftRibbon = Path().apply {
                moveTo(centerX - outerRadius * 0.62f, ribbonTop)
                lineTo(centerX - outerRadius * 0.13f, ribbonTop)
                lineTo(centerX - outerRadius * 0.24f, ribbonBottom)
                lineTo(centerX - outerRadius * 0.67f, ribbonBottom * 0.89f)
                close()
            }
            val rightRibbon = Path().apply {
                moveTo(centerX + outerRadius * 0.13f, ribbonTop)
                lineTo(centerX + outerRadius * 0.62f, ribbonTop)
                lineTo(centerX + outerRadius * 0.67f, ribbonBottom * 0.89f)
                lineTo(centerX + outerRadius * 0.24f, ribbonBottom)
                close()
            }
            drawPath(leftRibbon, palette.ribbonDark)
            drawPath(rightRibbon, palette.ribbon)
            drawCircle(
                color = Color(0x32000000),
                radius = outerRadius,
                center = medalCenter.copy(y = medalCenter.y + size.height * 0.025f),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(palette.metalLight, palette.metal, palette.metalDark),
                    center = medalCenter.copy(
                        x = medalCenter.x - outerRadius * 0.3f,
                        y = medalCenter.y - outerRadius * 0.32f,
                    ),
                    radius = outerRadius * 1.4f,
                ),
                radius = outerRadius,
                center = medalCenter,
            )
            drawCircle(color = palette.face, radius = outerRadius * 0.76f, center = medalCenter)
            drawCircle(
                color = palette.metalLight.copy(alpha = 0.74f),
                radius = outerRadius * 0.65f,
                center = medalCenter,
                style = androidx.compose.ui.graphics.drawscope.Stroke(width = outerRadius * 0.035f),
            )
            repeat(8) { index ->
                val angle = index * PI / 4.0
                drawCircle(
                    color = palette.metalLight.copy(alpha = 0.82f),
                    radius = outerRadius * 0.035f,
                    center = androidx.compose.ui.geometry.Offset(
                        x = medalCenter.x + cos(angle).toFloat() * outerRadius * 0.86f,
                        y = medalCenter.y + sin(angle).toFloat() * outerRadius * 0.86f,
                    ),
                )
            }
        }
        Icon(
            badge.definition.symbol.icon(),
            contentDescription = null,
            tint = palette.icon,
            modifier = Modifier.size(if (forcePreview) 34.dp else 28.dp).graphicsLayer {
                translationY = -size.height * 0.055f
            },
        )
    }
}

@Composable
private fun BadgeDetailSheet(
    badge: TrailBadge,
    onDismiss: () -> Unit,
) {
    var animateProgress by remember(badge.definition.id) { mutableStateOf(false) }
    val progress by animateFloatAsState(
        targetValue = if (animateProgress) badge.progress else 0f,
        animationSpec = tween(650),
        label = "badge-progress",
    )
    LaunchedEffect(badge.definition.id) { animateProgress = true }

    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Paper) {
        Column(
            Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 24.dp).padding(bottom = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            MedalSeal(badge, Modifier.size(138.dp), forcePreview = badge.earned)
            Text(
                if (badge.earned) "MEDAL EARNED" else badge.definition.category.label.uppercase(Locale.US),
                style = MaterialTheme.typography.labelSmall,
                color = if (badge.earned) TrailText else InkMuted,
                modifier = Modifier.padding(top = 8.dp),
            )
            Text(
                badge.definition.title,
                style = MaterialTheme.typography.headlineLarge,
                color = Ink,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 2.dp),
            )
            Text(
                badge.definition.requirement,
                style = MaterialTheme.typography.bodyLarge,
                color = InkMuted,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 6.dp),
            )
            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier.fillMaxWidth().padding(top = 24.dp).height(5.dp).clip(CircleShape),
                color = if (badge.earned) Trail else Moss,
                trackColor = Line,
            )
            Text(
                badgeProgressLabel(badge),
                style = MaterialTheme.typography.titleMedium,
                color = Ink,
                modifier = Modifier.padding(top = 10.dp),
            )
            if (!badge.earned) {
                Text(
                    remainingLabel(badge),
                    style = MaterialTheme.typography.bodyMedium,
                    color = InkMuted,
                    modifier = Modifier.padding(top = 2.dp),
                )
            }
            HorizontalDivider(color = Line, modifier = Modifier.padding(top = 24.dp))
            TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth().padding(top = 6.dp)) {
                Text("Close")
            }
        }
    }
}

private data class MedalPalette(
    val metalLight: Color,
    val metal: Color,
    val metalDark: Color,
    val face: Color,
    val icon: Color,
    val ribbon: Color,
    val ribbonDark: Color,
)

private fun medalPalette(finish: BadgeFinish, active: Boolean): MedalPalette {
    if (!active) {
        return MedalPalette(
            metalLight = Color(0xFFD8D6CF),
            metal = Color(0xFFA9AAA5),
            metalDark = Color(0xFF747973),
            face = Color(0xFFE4E2DA),
            icon = Color(0xFF7C817B),
            ribbon = Color(0xFF9A9E97),
            ribbonDark = Color(0xFF7E837D),
        )
    }
    return when (finish) {
        BadgeFinish.Bronze -> MedalPalette(
            Color(0xFFF4D5A7), Color(0xFFB8733D), Color(0xFF754022),
            Color(0xFF244638), Paper, Trail, Color(0xFFA75E32),
        )
        BadgeFinish.Silver -> MedalPalette(
            Color(0xFFF2F3EE), Color(0xFFB8C1BC), Color(0xFF68756F),
            Color(0xFF294B53), Paper, Color(0xFF6E8B88), Color(0xFF4C6966),
        )
        BadgeFinish.Gold -> MedalPalette(
            Color(0xFFFFE3A1), Color(0xFFD0A642), Color(0xFF856522),
            Color(0xFF6A422B), Paper, Color(0xFFD17D42), Color(0xFFA95D31),
        )
        BadgeFinish.Evergreen -> MedalPalette(
            Color(0xFFAEC8AF), Color(0xFF52755C), Color(0xFF1C3A2D),
            Color(0xFFF3E8C9), Moss, Color(0xFF315844), Color(0xFF183A2D),
        )
    }
}

private fun BadgeSymbol.icon(): ImageVector = when (this) {
    BadgeSymbol.Boot -> Icons.AutoMirrored.Rounded.DirectionsWalk
    BadgeSymbol.Mountain -> Icons.Rounded.Landscape
    BadgeSymbol.Route -> Icons.Rounded.Route
    BadgeSymbol.Flag -> Icons.Rounded.Flag
    BadgeSymbol.Rare -> Icons.Rounded.Star
    BadgeSymbol.Compass -> Icons.Rounded.Explore
    BadgeSymbol.Plant -> Icons.Rounded.LocalFlorist
    BadgeSymbol.Mammal -> Icons.Rounded.Pets
    BadgeSymbol.Fungi -> Icons.Rounded.Park
    BadgeSymbol.Bird -> Icons.Rounded.FlutterDash
    BadgeSymbol.Insect -> Icons.Rounded.BugReport
}

private fun compactProgressLabel(badge: TrailBadge): String = when (badge.definition.metric) {
    BadgeMetric.TotalMiles, BadgeMetric.LongestHike ->
        "${formatMiles(badge.current)} / ${formatMiles(badge.definition.target)} MI"
    else -> "${badge.current.roundToInt()} / ${badge.definition.target.roundToInt()}"
}

private fun badgeProgressLabel(badge: TrailBadge): String = when (badge.definition.metric) {
    BadgeMetric.TotalMiles ->
        if (badge.earned) "${formatMiles(badge.current)} lifetime miles recorded"
        else "${formatMiles(badge.current)} of ${formatMiles(badge.definition.target)} lifetime miles"
    BadgeMetric.LongestHike ->
        if (badge.earned) "Longest hike · ${formatMiles(badge.current)} miles"
        else "${formatMiles(badge.current)} of ${formatMiles(badge.definition.target)} miles in one hike"
    BadgeMetric.HikeCount ->
        if (badge.earned) "${badge.current.roundToInt()} hikes logged"
        else "${badge.current.roundToInt()} of ${badge.definition.target.roundToInt()} hikes"
    BadgeMetric.CompletedQuests ->
        if (badge.earned) "${badge.current.roundToInt()} Field Quests completed"
        else "${badge.current.roundToInt()} of ${badge.definition.target.roundToInt()} completed quests"
    BadgeMetric.RareFinds ->
        if (badge.earned) "${badge.current.roundToInt()} less-often-reported finds"
        else "${badge.current.roundToInt()} of ${badge.definition.target.roundToInt()} less-often-reported finds"
    BadgeMetric.SpeciesCount ->
        if (badge.earned) "${badge.current.roundToInt()} distinct species logged"
        else "${badge.current.roundToInt()} of ${badge.definition.target.roundToInt()} distinct species"
    BadgeMetric.Plants ->
        if (badge.earned) "${badge.current.roundToInt()} distinct plants logged"
        else "${badge.current.roundToInt()} of ${badge.definition.target.roundToInt()} plants"
    BadgeMetric.Mammals ->
        if (badge.earned) "${badge.current.roundToInt()} distinct mammals logged"
        else "${badge.current.roundToInt()} of ${badge.definition.target.roundToInt()} mammals"
    BadgeMetric.Fungi ->
        if (badge.earned) "${badge.current.roundToInt()} distinct fungi logged"
        else "${badge.current.roundToInt()} of ${badge.definition.target.roundToInt()} fungi"
    BadgeMetric.Birds ->
        if (badge.earned) "${badge.current.roundToInt()} distinct birds logged"
        else "${badge.current.roundToInt()} of ${badge.definition.target.roundToInt()} birds"
    BadgeMetric.Insects ->
        if (badge.earned) "${badge.current.roundToInt()} distinct insects logged"
        else "${badge.current.roundToInt()} of ${badge.definition.target.roundToInt()} insects"
}

private fun remainingLabel(badge: TrailBadge): String {
    val remaining = (badge.definition.target - badge.current).coerceAtLeast(0.0)
    return when (badge.definition.metric) {
        BadgeMetric.TotalMiles, BadgeMetric.LongestHike -> "${formatMiles(remaining)} miles to go"
        else -> "${remaining.roundToInt()} to go"
    }
}

private fun formatMiles(value: Double): String =
    if (value % 1.0 == 0.0) String.format(Locale.US, "%,.0f", value)
    else String.format(Locale.US, "%,.1f", value)
