package com.hikejournal.app.ui

import android.graphics.Bitmap
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import com.hikejournal.app.data.RoutePoint
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail
import com.hikejournal.app.ui.theme.TrailText

@Composable
internal fun JournalRoutePreview(
    routeSegments: List<List<RoutePoint>>,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val summary = remember(routeSegments) { journalRouteSummary(routeSegments) }
    var satelliteMap by remember(routeSegments) { mutableStateOf<Bitmap?>(null) }
    var loading by remember(routeSegments) { mutableStateOf(true) }

    LaunchedEffect(routeSegments) {
        loading = true
        satelliteMap = captureSatelliteRouteMap(context, routeSegments)
        loading = false
    }

    Column(modifier.fillMaxWidth()) {
        Text(
            "ROUTE",
            style = MaterialTheme.typography.labelSmall,
            color = TrailText,
        )
        Box(
            Modifier
                .fillMaxWidth()
                .padding(top = 8.dp)
                .height(230.dp)
                .semantics(mergeDescendants = true) {
                    contentDescription = "Recorded route"
                    stateDescription = summary
                },
            contentAlignment = Alignment.Center,
        ) {
            JournalRouteSketch(routeSegments, Modifier.fillMaxSize())
            satelliteMap?.let { bitmap ->
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
                Box(
                    Modifier
                        .fillMaxSize()
                        .background(
                            Brush.verticalGradient(
                                0.45f to Color.Transparent,
                                1f to Color.Black.copy(alpha = 0.22f),
                            ),
                        ),
                )
            }
            if (loading) {
                CircularProgressIndicator(
                    color = Paper,
                    strokeWidth = 2.dp,
                )
            }
        }
        Text(
            summary,
            style = MaterialTheme.typography.bodySmall,
            color = InkMuted,
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}

@Composable
private fun JournalRouteSketch(
    routeSegments: List<List<RoutePoint>>,
    modifier: Modifier = Modifier,
) {
    Canvas(
        modifier.background(
            Brush.linearGradient(
                colors = listOf(Color(0xFF1F4935), Color(0xFF506D42)),
            ),
        ),
    ) {
        val projected = projectShareRoute(
            routeSegments = routeSegments,
            width = size.width,
            height = size.height,
            padding = 34.dp.toPx(),
        )
        projected.filter { it.size >= 2 }.forEach { segment ->
            val path = Path().apply {
                moveTo(segment.first().x, segment.first().y)
                segment.drop(1).forEach { point -> lineTo(point.x, point.y) }
            }
            drawPath(
                path = path,
                color = Color(0xC714251D),
                style = Stroke(
                    width = 10.dp.toPx(),
                    cap = StrokeCap.Round,
                    join = StrokeJoin.Round,
                ),
            )
            drawPath(
                path = path,
                color = Trail,
                style = Stroke(
                    width = 6.dp.toPx(),
                    cap = StrokeCap.Round,
                    join = StrokeJoin.Round,
                ),
            )
        }
        val start = projected.firstOrNull()?.firstOrNull()
        val end = projected.lastOrNull()?.lastOrNull()
        if (start != null && end != null) {
            drawCircle(
                color = Paper,
                radius = 7.dp.toPx(),
                center = Offset(start.x, start.y),
            )
            drawCircle(
                color = Color(0xFF183A2D),
                radius = 3.dp.toPx(),
                center = Offset(start.x, start.y),
            )
            drawCircle(
                color = Trail,
                radius = 7.dp.toPx(),
                center = Offset(end.x, end.y),
            )
            drawCircle(
                color = Paper,
                radius = 7.dp.toPx(),
                center = Offset(end.x, end.y),
                style = Stroke(width = 2.dp.toPx()),
            )
        }
    }
}

internal fun journalRouteSummary(routeSegments: List<List<RoutePoint>>): String {
    val pointCount = routeSegments.sumOf(List<RoutePoint>::size)
    val segmentCount = routeSegments.size
    return "$pointCount saved GPS points · $segmentCount ${if (segmentCount == 1) "segment" else "segments"}"
}
