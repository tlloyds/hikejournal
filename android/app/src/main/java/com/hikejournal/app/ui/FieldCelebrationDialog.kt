package com.hikejournal.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material.icons.rounded.WorkspacePremium
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.AsyncImage
import com.hikejournal.app.data.FieldCelebration
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.MossSoft
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail

@Composable
internal fun FieldCelebrationDialog(
    celebration: FieldCelebration,
    onDismiss: () -> Unit,
) {
    var revealed by remember(celebration.id) { mutableStateOf(false) }
    LaunchedEffect(celebration.id) { revealed = true }
    val imagePresence by animateFloatAsState(
        targetValue = if (revealed) 1f else 0f,
        animationSpec = tween(520),
        label = "celebration-image",
    )
    val navigationBarPadding = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    // Dialogs opt out of decor fitting, so some Android versions report a zero
    // navigation inset here even though the gesture area is still consuming space.
    // Keep a conservative floor so the action is always fully tappable.
    val actionBottomPadding = maxOf(navigationBarPadding, 48.dp) + 24.dp
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(
            dismissOnBackPress = true,
            dismissOnClickOutside = false,
            usePlatformDefaultWidth = false,
            decorFitsSystemWindows = false,
        ),
    ) {
        Column(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        colors = listOf(MossSoft, Moss, Color(0xFF10281F)),
                    )
                )
                .statusBarsPadding(),
        ) {
            CelebrationImagePlane(
                urls = celebration.imageUrls,
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(0.43f)
                    .alpha(imagePresence)
                    .scale(0.98f + imagePresence * 0.02f),
            )
            AnimatedVisibility(
                visible = revealed,
                enter = fadeIn(tween(420, delayMillis = 100)) +
                    slideInVertically(tween(480, delayMillis = 100)) { it / 8 },
                modifier = Modifier.weight(0.57f),
            ) {
                Column(
                    Modifier.fillMaxHeight(),
                ) {
                    Column(
                        Modifier
                            .weight(1f)
                            .verticalScroll(rememberScrollState())
                            .padding(horizontal = 24.dp)
                            .padding(top = 22.dp, bottom = 10.dp),
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Rounded.AutoAwesome, null, tint = Trail, modifier = Modifier.size(20.dp))
                            Text(
                                celebration.eyebrow,
                                style = MaterialTheme.typography.labelMedium,
                                color = Color(0xFFF1BE79),
                                modifier = Modifier.padding(start = 8.dp),
                            )
                        }
                        Text(
                            celebration.title,
                            style = MaterialTheme.typography.displayMedium,
                            color = Paper,
                            modifier = Modifier.padding(top = 8.dp),
                        )
                        Text(
                            celebration.detail,
                            style = MaterialTheme.typography.bodyLarge,
                            color = Color(0xFFD6E0D3),
                            modifier = Modifier.padding(top = 8.dp),
                        )
                        if (celebration.highlights.isNotEmpty()) {
                            HorizontalDivider(
                                color = Color.White.copy(alpha = 0.18f),
                                modifier = Modifier.padding(top = 20.dp, bottom = 16.dp),
                            )
                            Row(
                                Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                celebration.highlights.take(3).forEach { highlight ->
                                    Column(Modifier.weight(1f), horizontalAlignment = Alignment.Start) {
                                        Text(
                                            highlight.value,
                                            style = MaterialTheme.typography.headlineMedium,
                                            color = Paper,
                                            fontWeight = FontWeight.Bold,
                                        )
                                        Text(
                                            highlight.label.uppercase(),
                                            style = MaterialTheme.typography.labelSmall,
                                            color = Color(0xFFB8C9BC),
                                        )
                                    }
                                }
                            }
                        }
                        if (!celebration.badgeTitle.isNullOrBlank() || !celebration.badgeProgress.isNullOrBlank()) {
                            Row(
                                Modifier.fillMaxWidth().padding(top = 20.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Icon(
                                    Icons.Rounded.WorkspacePremium,
                                    contentDescription = null,
                                    tint = Color(0xFFF1BE79),
                                    modifier = Modifier.size(34.dp),
                                )
                                Column(Modifier.padding(start = 12.dp)) {
                                    Text(
                                        celebration.badgeTitle ?: "BADGE PROGRESS",
                                        style = MaterialTheme.typography.titleMedium,
                                        color = Paper,
                                    )
                                    celebration.badgeProgress?.let { progress ->
                                        Text(
                                            progress,
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = Color(0xFFD6E0D3),
                                        )
                                    }
                                }
                            }
                        }
                    }
                    Box(
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 24.dp)
                            .padding(top = 12.dp, bottom = actionBottomPadding),
                    ) {
                        Button(
                            onClick = onDismiss,
                            modifier = Modifier.fillMaxWidth().height(54.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Trail, contentColor = Paper),
                        ) {
                            Text(celebration.actionLabel, style = MaterialTheme.typography.labelLarge)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CelebrationImagePlane(urls: List<String>, modifier: Modifier = Modifier) {
    Box(modifier.background(Color(0xFF234A39))) {
        if (urls.isNotEmpty()) {
            Row(Modifier.fillMaxSize()) {
                urls.take(3).forEach { url ->
                    AsyncImage(
                        model = url,
                        contentDescription = "Field discovery",
                        modifier = Modifier.fillMaxHeight().weight(1f),
                        contentScale = ContentScale.Crop,
                    )
                }
            }
            Box(
                Modifier.fillMaxSize().background(
                    Brush.verticalGradient(
                        0f to Color.Transparent,
                        0.72f to Color.Transparent,
                        1f to Moss.copy(alpha = 0.72f),
                    )
                )
            )
        } else {
            Canvas(Modifier.fillMaxSize()) {
                val line = Color(0xFF89A18F).copy(alpha = 0.24f)
                repeat(7) { index ->
                    val radius = size.minDimension * (0.12f + index * 0.08f)
                    drawCircle(
                        color = line,
                        radius = radius,
                        center = Offset(size.width * 0.5f, size.height * 0.52f),
                        style = Stroke(width = 2f),
                    )
                }
            }
            Text(
                "HikeJournal",
                style = MaterialTheme.typography.displayMedium,
                color = Paper.copy(alpha = 0.88f),
                textAlign = TextAlign.Center,
                modifier = Modifier.align(Alignment.Center),
            )
        }
    }
}
