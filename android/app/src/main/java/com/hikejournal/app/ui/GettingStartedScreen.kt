package com.hikejournal.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.DirectionsWalk
import androidx.compose.material.icons.rounded.CameraAlt
import androidx.compose.material.icons.rounded.Explore
import androidx.compose.material.icons.rounded.Map
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.hikejournal.app.ui.theme.Fern
import com.hikejournal.app.ui.theme.Ink
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Line
import com.hikejournal.app.ui.theme.Lichen
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Parchment
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.TrailText

private data class GettingStartedPage(
    val eyebrow: String,
    val title: String,
    val body: String,
    val icon: ImageVector,
    val iconLabel: String,
)

private val GettingStartedPages = listOf(
    GettingStartedPage(
        eyebrow = "A FIELD JOURNAL FOR THE OUTDOORS",
        title = "Keep the whole outing.",
        body = "Track the walk, notice what you find, and build a field journal you can return to.",
        icon = Icons.Rounded.Explore,
        iconLabel = "Explore",
    ),
    GettingStartedPage(
        eyebrow = "CAPTURE THE WALK",
        title = "Let the trail tell its story.",
        body = "Start tracking for route, active time, and distance—even when the trail has no signal. Add photos and notes, or create a hike manually later.",
        icon = Icons.AutoMirrored.Rounded.DirectionsWalk,
        iconLabel = "Track a hike",
    ),
    GettingStartedPage(
        eyebrow = "NOTICE WHAT IS AROUND YOU",
        title = "Turn a find into a record.",
        body = "Add an Everyday Sighting for a quick observation. Review photos with species suggestions, then keep confirmed finds in your Field Guide.",
        icon = Icons.Rounded.CameraAlt,
        iconLabel = "Record a find",
    ),
    GettingStartedPage(
        eyebrow = "REVISIT AND SHARE",
        title = "Build a living map of your time outside.",
        body = "See routes and geotagged photos on the map, turn on trail overlays, follow place histories, and earn Trail Medals through Field Quests. Connect iNaturalist when you are ready to share.",
        icon = Icons.Rounded.Map,
        iconLabel = "Revisit your journal",
    ),
)

@Composable
fun GettingStartedScreen(
    onDismiss: () -> Unit,
    onStartOuting: () -> Unit,
) {
    var page by remember { mutableIntStateOf(0) }
    var direction by remember { mutableIntStateOf(1) }
    val scrollState = rememberScrollState()
    val current = GettingStartedPages[page]

    fun close() = onDismiss()

    BackHandler(onBack = ::close)

    Box(
        Modifier
            .fillMaxSize()
            .background(Parchment),
    ) {
        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(scrollState)
                .navigationBarsPadding(),
        ) {
            GettingStartedHero(
                onDismiss = ::close,
                page = page,
            )
            Column(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp, vertical = 26.dp),
            ) {
                AnimatedContent(
                    targetState = current,
                    transitionSpec = {
                        val enter: EnterTransition = slideInHorizontally { fullWidth -> direction * fullWidth / 2 } + fadeIn()
                        val exit: ExitTransition = slideOutHorizontally { fullWidth -> -direction * fullWidth / 2 } + fadeOut()
                        enter togetherWith exit
                    },
                    label = "getting-started-page",
                ) { content ->
                    GettingStartedPageContent(content)
                }
                GettingStartedProgress(
                    page = page,
                    modifier = Modifier.padding(top = 28.dp),
                )
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(top = 25.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (page > 0) {
                        TextButton(
                            onClick = {
                                direction = -1
                                page -= 1
                            },
                        ) {
                            Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = null)
                            Spacer(Modifier.width(7.dp))
                            Text("Back")
                        }
                    } else {
                        Spacer(Modifier.width(1.dp))
                    }
                    Button(
                        onClick = {
                            if (page == GettingStartedPages.lastIndex) {
                                onStartOuting()
                            } else {
                                direction = 1
                                page += 1
                            }
                        },
                    ) {
                        Text(if (page == GettingStartedPages.lastIndex) "Start an outing" else "Next")
                    }
                }
            }
        }
    }
}

@Composable
private fun GettingStartedHero(
    onDismiss: () -> Unit,
    page: Int,
) {
    Box(
        Modifier
            .fillMaxWidth()
            .height(290.dp),
    ) {
        GettingStartedLandscape(Modifier.fillMaxSize())
        Row(
            Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(horizontal = 18.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "HIKEJOURNAL",
                style = MaterialTheme.typography.displaySmall,
                color = Paper,
            )
            TextButton(onClick = onDismiss) {
                Text("Skip", color = Paper)
            }
        }
        Text(
            "${page + 1} / ${GettingStartedPages.size}",
            style = MaterialTheme.typography.labelSmall,
            color = Paper,
            modifier = Modifier
                .align(Alignment.BottomStart)
                .padding(22.dp),
        )
    }
}

@Composable
private fun GettingStartedPageContent(page: GettingStartedPage) {
    Column(
        Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.Start,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(Lichen),
                contentAlignment = Alignment.Center,
            ) {
                Icon(page.icon, contentDescription = page.iconLabel, tint = Moss, modifier = Modifier.size(25.dp))
            }
            Text(
                page.eyebrow,
                style = MaterialTheme.typography.labelSmall,
                color = TrailText,
                modifier = Modifier.padding(start = 12.dp),
            )
        }
        Text(
            page.title,
            style = MaterialTheme.typography.displayMedium,
            color = Ink,
            modifier = Modifier.padding(top = 15.dp),
        )
        Text(
            page.body,
            style = MaterialTheme.typography.bodyLarge,
            color = InkMuted,
            modifier = Modifier.padding(top = 12.dp),
        )
    }
}

@Composable
private fun GettingStartedProgress(
    page: Int,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        GettingStartedPages.indices.forEach { index ->
            Box(
                Modifier
                    .weight(1f)
                    .height(4.dp)
                    .clip(CircleShape)
                    .background(if (index <= page) Trail else Line),
            )
        }
    }
}

@Composable
private fun GettingStartedLandscape(modifier: Modifier = Modifier) {
    Canvas(
        modifier.background(
            Brush.linearGradient(
                listOf(Color(0xFF315844), Moss),
            ),
        ),
    ) {
        val back = Path().apply {
            moveTo(0f, size.height * .82f)
            lineTo(size.width * .28f, size.height * .35f)
            lineTo(size.width * .48f, size.height * .66f)
            lineTo(size.width * .68f, size.height * .25f)
            lineTo(size.width, size.height * .70f)
            lineTo(size.width, size.height)
            lineTo(0f, size.height)
            close()
        }
        drawPath(back, Fern)

        val middle = Path().apply {
            moveTo(0f, size.height)
            cubicTo(
                size.width * .25f,
                size.height * .72f,
                size.width * .45f,
                size.height * .88f,
                size.width * .64f,
                size.height * .62f,
            )
            cubicTo(
                size.width * .78f,
                size.height * .42f,
                size.width * .87f,
                size.height * .55f,
                size.width,
                size.height * .46f,
            )
        }
        drawPath(middle, Trail, style = Stroke(width = size.width * .035f))
        drawPath(
            middle,
            Color(0x66FFF8E7),
            style = Stroke(width = size.width * .008f),
        )
        drawCircle(
            Color(0x99F4F0E5),
            radius = size.minDimension * .045f,
            center = Offset(size.width * .80f, size.height * .18f),
        )
    }
}
