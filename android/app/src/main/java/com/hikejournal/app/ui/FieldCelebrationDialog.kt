package com.hikejournal.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.AsyncImage
import com.hikejournal.app.data.FieldCelebration
import com.hikejournal.app.ui.theme.Moss
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
    val actionBottomPadding = 18.dp
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(
            dismissOnBackPress = true,
            dismissOnClickOutside = false,
            usePlatformDefaultWidth = false,
            decorFitsSystemWindows = false,
        ),
    ) {
        BoxWithConstraints(
            Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(12.dp),
            contentAlignment = Alignment.Center,
        ) {
        val imageHeight = (maxHeight * 0.34f).coerceIn(160.dp, 290.dp)
        Column(
            Modifier.widthIn(max = 560.dp).fillMaxWidth().heightIn(max = maxHeight)
                .clip(RoundedCornerShape(22.dp)).background(Moss),
        ) {
            CelebrationImagePlane(
                urls = celebration.imageUrls,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(imageHeight)
                    .alpha(imagePresence)
                    .scale(0.98f + imagePresence * 0.02f),
            )
            AnimatedVisibility(
                visible = revealed,
                enter = fadeIn(tween(420, delayMillis = 100)) +
                    slideInVertically(tween(480, delayMillis = 100)) { it / 8 },
                modifier = Modifier.weight(1f, fill = false),
            ) {
                Column(
                    Modifier,
                ) {
                    Column(
                        Modifier
                            .weight(1f, fill = false)
                            .verticalScroll(rememberScrollState())
                            .padding(horizontal = 24.dp)
                            .padding(top = 18.dp, bottom = 6.dp),
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
                            style = MaterialTheme.typography.headlineLarge,
                            color = Paper,
                            modifier = Modifier.padding(top = 6.dp),
                        )
                        Text(
                            celebration.detail,
                            style = MaterialTheme.typography.bodyLarge,
                            color = Color(0xFFD6E0D3),
                            modifier = Modifier.padding(top = 6.dp),
                        )
                        if (celebration.highlights.isNotEmpty()) {
                            HorizontalDivider(
                                color = Color.White.copy(alpha = 0.18f),
                                modifier = Modifier.padding(top = 16.dp, bottom = 12.dp),
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
                                Modifier.fillMaxWidth().padding(top = 16.dp),
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
                            .padding(top = 8.dp, bottom = actionBottomPadding),
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
            PatternedForestSurface(Modifier.fillMaxSize()) {
                BrandWordmark(Modifier.widthIn(max = 250.dp).fillMaxWidth().height(68.dp)
                    .padding(horizontal = 24.dp).align(Alignment.Center))
            }
        }
    }
}
