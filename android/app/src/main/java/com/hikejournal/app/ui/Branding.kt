package com.hikejournal.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.ui.unit.dp
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.ui.text.style.TextOverflow
import com.hikejournal.app.R
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.Fern
import com.hikejournal.app.ui.theme.BrandFamily

@Composable
fun PatternedForestSurface(
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit,
) {
    Box(modifier = modifier.background(Moss)) {
        Image(
            painter = painterResource(R.drawable.hj_pattern_green),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier.matchParentSize(),
        )
        content()
    }
}

@Composable
fun BrandScreenHeader(
    title: String,
    detail: String,
    modifier: Modifier = Modifier,
    actions: @Composable RowScope.() -> Unit = {},
) {
    PatternedForestSurface(modifier.fillMaxWidth()) {
        androidx.compose.foundation.layout.Column(
            Modifier.fillMaxWidth().statusBarsPadding().padding(start = 18.dp, end = 8.dp, top = 12.dp, bottom = 16.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                BrandMark(Modifier.size(width = 42.dp, height = 50.dp))
                BoxWithConstraints(Modifier.weight(1f).padding(start = 10.dp)) {
                    val titleStyle = MaterialTheme.typography.titleLarge.copy(
                        fontSize = 27.sp, lineHeight = 32.sp, fontWeight = FontWeight.Bold,
                    )
                    val titleWidth = rememberTextMeasurer().measure(
                        title, style = titleStyle, maxLines = 1, softWrap = false,
                    ).size.width.coerceAtLeast(1)
                    val availableWidth = with(LocalDensity.current) { maxWidth.toPx() }
                    val titleScale = (availableWidth / titleWidth).coerceAtMost(1f).let {
                        if (it < 1f) it * 0.98f else it
                    }
                    Text(
                        title,
                        style = titleStyle.copy(fontSize = 27.sp * titleScale),
                        color = Color.White,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                Row(verticalAlignment = Alignment.CenterVertically, content = actions)
            }
            Text(
                detail,
                style = MaterialTheme.typography.bodyMedium,
                color = Color(0xFFE4E9DF),
                modifier = Modifier.padding(start = 52.dp, top = 2.dp),
            )
        }
    }
}

@Composable
fun TrailHighlightLabel(
    text: String,
    modifier: Modifier = Modifier,
) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelLarge.copy(
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.35.sp,
        ),
        color = Moss,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = modifier
            .clip(RoundedCornerShape(2.dp))
            .background(Trail)
            .padding(horizontal = 10.dp, vertical = 4.dp),
    )
}

@Composable
fun BrandMark(
    modifier: Modifier = Modifier,
) {
    Image(
        painter = painterResource(R.drawable.hj_logo_color_icon),
        contentDescription = null,
        contentScale = ContentScale.Fit,
        modifier = modifier,
    )
}

/** All page marks use the green outline with white bars from the source artwork. */
@Composable
fun BrandWordmark(modifier: Modifier = Modifier) {
    BoxWithConstraints(modifier) {
        val markHeight = minOf(maxHeight, maxWidth / 5.4f)
        val wordmarkSize = (maxWidth.value / 9.2f).sp
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            BrandMark(Modifier.size(width = markHeight * 0.84f, height = markHeight))
            Text(
                "HikeJournal",
                style = MaterialTheme.typography.titleLarge.copy(
                    fontFamily = BrandFamily,
                    fontWeight = FontWeight.Bold,
                    fontSize = wordmarkSize,
                    lineHeight = wordmarkSize * 1.2f,
                    letterSpacing = (-0.6).sp,
                ),
                color = Color.White,
                maxLines = 1,
                modifier = Modifier.weight(1f).padding(start = 7.dp),
            )
        }
    }
}

@Composable
internal fun BrandSectionTabs(
    labels: List<String>,
    selectedIndex: Int,
    onSelect: (Int) -> Unit,
) {
    Row(Modifier.fillMaxWidth().background(Color(0xFFDDE6BD))) {
        labels.forEachIndexed { index, label ->
            val background by androidx.compose.animation.animateColorAsState(
                if (index == selectedIndex) Fern else Color.Transparent,
                label = "section-tab",
            )
            androidx.compose.material3.TextButton(
                onClick = { onSelect(index) },
                modifier = Modifier.weight(1f).background(background).height(50.dp),
                shape = RoundedCornerShape(0.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 4.dp),
            ) {
                Text(label.uppercase(java.util.Locale.US), style = MaterialTheme.typography.labelMedium.copy(
                    fontWeight = FontWeight.Bold, letterSpacing = 0.sp,
                ), color = Moss, maxLines = 1)
            }
        }
    }
}
