package com.hikejournal.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.hikejournal.app.R
import com.hikejournal.app.ui.theme.Fern
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper

enum class TopDestination { Archive, Species, Review, Publish, Map }

@Composable
fun TopNavigation(
    selected: TopDestination,
    onSelect: (TopDestination) -> Unit,
    modifier: Modifier = Modifier,
) {
    NavigationBar(
        modifier = modifier.fillMaxWidth().clip(RoundedCornerShape(topStart = 26.dp, topEnd = 26.dp)).background(Moss),
        containerColor = Moss,
        contentColor = Paper,
        tonalElevation = 0.dp,
    ) {
        TopDestination.entries.forEach { destination ->
            val icon = when (destination) {
                TopDestination.Archive -> if (selected == destination) R.drawable.hj_nav_hikes_green else R.drawable.hj_nav_hikes_white
                TopDestination.Species -> if (selected == destination) R.drawable.hj_nav_species_green else R.drawable.hj_nav_species_white
                TopDestination.Review -> if (selected == destination) R.drawable.hj_nav_review_green else R.drawable.hj_nav_review_white
                TopDestination.Publish -> if (selected == destination) R.drawable.hj_nav_publish_green else R.drawable.hj_nav_publish_white
                TopDestination.Map -> if (selected == destination) R.drawable.hj_nav_map_green else R.drawable.hj_nav_map_white
            }
            val label = when (destination) {
                TopDestination.Archive -> "Hikes"
                else -> destination.name
            }
            NavigationBarItem(
                modifier = Modifier.background(Moss),
                selected = selected == destination,
                onClick = { onSelect(destination) },
                icon = {
                    Image(
                        painter = painterResource(icon),
                        contentDescription = null,
                        modifier = Modifier.size(24.dp),
                    )
                },
                label = { Text(label, style = MaterialTheme.typography.labelMedium) },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = Color.Unspecified,
                    selectedTextColor = Fern,
                    indicatorColor = Moss,
                    unselectedIconColor = Color.Unspecified,
                    unselectedTextColor = Paper,
                ),
            )
        }
    }
}
