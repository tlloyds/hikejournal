package com.hikejournal.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.runtime.Composable
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.ui.text.style.TextOverflow
import com.hikejournal.app.R
import com.hikejournal.app.ui.theme.Moss

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
            alpha = 0.42f,
        )
        Box(
            Modifier
                .matchParentSize()
                .background(
                    Brush.verticalGradient(
                        listOf(Moss.copy(alpha = 0.12f), Moss.copy(alpha = 0.22f)),
                    ),
                ),
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
                Text(
                    title,
                    style = MaterialTheme.typography.headlineMedium,
                    color = Color(0xFFF4ECEB),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f).padding(start = 10.dp),
                )
                Row(verticalAlignment = Alignment.CenterVertically, content = actions)
            }
            Text(
                detail,
                style = MaterialTheme.typography.labelSmall,
                color = Color(0xFFD8E0D5),
                modifier = Modifier.padding(start = 52.dp, top = 2.dp),
            )
        }
    }
}

@Composable
fun BrandMark(
    modifier: Modifier = Modifier,
    white: Boolean = true,
) {
    Image(
        painter = painterResource(if (white) R.drawable.hj_logo_white_icon else R.drawable.hj_logo_color_icon),
        contentDescription = null,
        contentScale = ContentScale.Fit,
        modifier = modifier,
    )
}

@Composable
fun BrandWordmark(modifier: Modifier = Modifier) {
    Image(
        painter = painterResource(R.drawable.hj_logo_horizontal),
        contentDescription = "Hiking Journal",
        contentScale = ContentScale.Fit,
        modifier = modifier,
    )
}
