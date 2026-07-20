package com.hikejournal.app.ui

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.FactCheck
import androidx.compose.material.icons.rounded.CollectionsBookmark
import androidx.compose.material.icons.rounded.CloudUpload
import androidx.compose.material.icons.rounded.Map
import androidx.compose.material.icons.rounded.TravelExplore
import androidx.compose.material3.Icon
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
import androidx.compose.ui.unit.dp
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail

enum class TopDestination { Archive, Species, Review, Publish, Map }

@Composable
fun TopNavigation(
    selected: TopDestination,
    onSelect: (TopDestination) -> Unit,
    modifier: Modifier = Modifier,
) {
    NavigationBar(
        modifier = modifier.fillMaxWidth().background(Moss),
        containerColor = Moss,
        contentColor = Paper,
        tonalElevation = 0.dp,
    ) {
        TopDestination.entries.forEach { destination ->
            val icon = when (destination) {
                TopDestination.Archive -> Icons.Rounded.CollectionsBookmark
                TopDestination.Species -> Icons.Rounded.TravelExplore
                TopDestination.Review -> Icons.AutoMirrored.Rounded.FactCheck
                TopDestination.Publish -> Icons.Rounded.CloudUpload
                TopDestination.Map -> Icons.Rounded.Map
            }
            NavigationBarItem(
                modifier = Modifier.background(Moss),
                selected = selected == destination,
                onClick = { onSelect(destination) },
                icon = { Icon(icon, contentDescription = destination.name) },
                label = { Text(destination.name, style = MaterialTheme.typography.labelMedium) },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = Moss,
                    selectedTextColor = Paper,
                    indicatorColor = Trail,
                    unselectedIconColor = Color(0xFFB7C8B5),
                    unselectedTextColor = Color(0xFFB7C8B5),
                ),
            )
        }
    }
}
