package com.hikejournal.app.ui

import android.graphics.Bitmap
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import com.hikejournal.app.data.MapRoute
import com.hikejournal.app.data.RoutePoint
import com.hikejournal.app.ui.theme.InkMuted
import com.hikejournal.app.ui.theme.Paper

@Composable
internal fun PlaceRoutePreview(
    routes: List<MapRoute>,
    placeName: String,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val routeSegments = remember(routes) { routes.flatMap(MapRoute::segments) }
    val pointCount = remember(routes) { routeSegments.sumOf(List<RoutePoint>::size) }
    val routeCount = routes.size
    val routeCountLabel = "$routeCount saved outing ${if (routeCount == 1) "route" else "routes"}"
    var satelliteMap by remember(routes) { mutableStateOf<Bitmap?>(null) }
    var loading by remember(routes) { mutableStateOf(true) }

    LaunchedEffect(routes) {
        loading = true
        satelliteMap = captureSatelliteRouteMap(context, routeSegments)
        loading = false
    }

    Column(modifier.fillMaxWidth()) {
        Box(
            Modifier
                .fillMaxWidth()
                .height(230.dp)
                .semantics(mergeDescendants = true) {
                    contentDescription = "Recorded routes at $placeName"
                    stateDescription = "$routeCountLabel and $pointCount GPS points"
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
            "$routeCountLabel · $pointCount GPS points",
            style = MaterialTheme.typography.bodySmall,
            color = InkMuted,
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}
