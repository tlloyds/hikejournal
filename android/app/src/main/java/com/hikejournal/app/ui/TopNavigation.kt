package com.hikejournal.app.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.FloatingActionButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.hikejournal.app.R
import com.hikejournal.app.ui.theme.Fern
import com.hikejournal.app.ui.theme.Moss
import com.hikejournal.app.ui.theme.Paper
import com.hikejournal.app.ui.theme.Trail

enum class TopDestination { Archive, Species, Review, Publish, Map }

@Composable
fun TopNavigation(
    selected: TopDestination,
    onSelect: (TopDestination) -> Unit,
    modifier: Modifier = Modifier,
    onAdd: (() -> Unit)? = null,
) {
    val destinations = if (selected in setOf(TopDestination.Species, TopDestination.Review, TopDestination.Publish)) {
        TopDestination.entries
    } else {
        TopDestination.entries.filterNot { it == TopDestination.Publish }
    }
    val floating = onAdd != null
    Row(
        modifier.fillMaxWidth().then(if (floating) Modifier else Modifier.background(Moss)).navigationBarsPadding()
            .padding(horizontal = if (floating) 16.dp else 0.dp, vertical = if (floating) 8.dp else 0.dp),
        horizontalArrangement = Arrangement.spacedBy(if (floating) 8.dp else 0.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            Modifier.weight(1f).height(if (floating) 64.dp else 72.dp)
                .then(if (floating) Modifier.clip(CircleShape) else Modifier)
                .background(Moss).selectableGroup().padding(horizontal = if (floating) 8.dp else 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            destinations.forEach { destination ->
                val active = selected == destination
                val icon = when (destination) {
                    TopDestination.Archive -> if (active) R.drawable.hj_nav_hikes_green else R.drawable.hj_nav_hikes_white
                    TopDestination.Species -> if (active) R.drawable.hj_nav_species_green else R.drawable.hj_nav_species_white
                    TopDestination.Review -> if (active) R.drawable.hj_nav_review_green else R.drawable.hj_nav_review_white
                    TopDestination.Publish -> if (active) R.drawable.hj_nav_publish_green else R.drawable.hj_nav_publish_white
                    TopDestination.Map -> if (active) R.drawable.hj_nav_map_green else R.drawable.hj_nav_map_white
                }
                val label = if (destination == TopDestination.Archive) "Hikes" else destination.name
                val labelColor by animateColorAsState(if (active) Fern else Paper, label = "navigation-selection")
                Column(
                    Modifier.weight(1f).height(if (floating) 64.dp else 72.dp)
                        .selectable(selected = active, role = Role.Tab, onClick = { onSelect(destination) }),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Image(painterResource(icon), null, Modifier.size(if (floating) 25.dp else 28.dp))
                    Text(label, style = MaterialTheme.typography.labelMedium.copy(
                        fontSize = if (floating) 12.sp else 11.sp,
                        fontWeight = FontWeight.SemiBold,
                        letterSpacing = 0.sp,
                    ), color = labelColor, modifier = Modifier.padding(top = 4.dp), maxLines = 1)
                }
            }
        }
        onAdd?.let { add ->
            FloatingActionButton(
                onClick = add,
                modifier = Modifier.size(64.dp),
                containerColor = Trail,
                contentColor = Paper,
                shape = CircleShape,
                elevation = FloatingActionButtonDefaults.elevation(0.dp, 0.dp, 0.dp, 0.dp),
            ) {
                Icon(Icons.Rounded.Add, "Add hike or everyday sighting", Modifier.size(38.dp))
            }
        }
    }
}
