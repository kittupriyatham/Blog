package tech.potluri.blog.ui.feed

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Brightness2
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.Canvas
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import tech.potluri.blog.ui.components.PostCard
import tech.potluri.blog.ui.components.TagChipRow
import tech.potluri.blog.ui.theme.AccentViolet
import tech.potluri.blog.ui.theme.AppThemeMode
import tech.potluri.blog.ui.theme.Brand600

@Composable
fun FeedScreen(
    onPostClick: (String) -> Unit,
    onNavigateToAdmin: () -> Unit = {},
    currentThemeMode: AppThemeMode = AppThemeMode.DARK,
    onToggleTheme: () -> Unit = {},
    modifier: Modifier = Modifier,
    viewModel: FeedViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = onNavigateToAdmin,
                containerColor = MaterialTheme.colorScheme.primaryContainer,
                contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                shape = RoundedCornerShape(18.dp),
                icon = {
                    Icon(Icons.Default.Edit, contentDescription = "Create Post")
                },
                text = {
                    Text("Compose", fontWeight = FontWeight.Bold)
                }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = modifier
                .fillMaxSize()
                .padding(innerPadding)
                .background(MaterialTheme.colorScheme.background)
        ) {
            // Modern Editorial Top Header
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 18.dp, end = 14.dp, top = 14.dp, bottom = 6.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    BlogBrandLogo(
                        modifier = Modifier.size(38.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "Blog",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.ExtraBold,
                            color = MaterialTheme.colorScheme.onBackground
                        )
                        Text(
                            text = "Stories, Research & Code",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                // Quick Theme Mode Pill + Refresh Action
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Surface(
                        onClick = onToggleTheme,
                        shape = RoundedCornerShape(50),
                        color = MaterialTheme.colorScheme.surface,
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = when (currentThemeMode) {
                                    AppThemeMode.LIGHT -> Icons.Default.LightMode
                                    AppThemeMode.DARK -> Icons.Default.DarkMode
                                    AppThemeMode.NIGHT -> Icons.Default.Brightness2
                                },
                                contentDescription = "Toggle Theme (Light/Dark/Night)",
                                tint = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(modifier = Modifier.width(5.dp))
                            Text(
                                text = when (currentThemeMode) {
                                    AppThemeMode.LIGHT -> "Light"
                                    AppThemeMode.DARK -> "Dark"
                                    AppThemeMode.NIGHT -> "OLED"
                                },
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                        }
                    }

                    Surface(
                        onClick = { viewModel.loadFeed(refresh = true) },
                        shape = CircleShape,
                        color = MaterialTheme.colorScheme.surface,
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)
                    ) {
                        Box(
                            modifier = Modifier.size(34.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.Refresh,
                                contentDescription = "Refresh Feed",
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.size(17.dp)
                            )
                        }
                    }
                }
            }

            // Elevated Pill Search Bar
            OutlinedTextField(
                value = uiState.searchQuery,
                onValueChange = { viewModel.onSearchQueryChanged(it) },
                placeholder = { Text("Search posts & articles…") },
                leadingIcon = {
                    Icon(
                        imageVector = Icons.Default.Search,
                        contentDescription = "Search",
                        tint = MaterialTheme.colorScheme.primary
                    )
                },
                trailingIcon = {
                    if (uiState.searchQuery.isNotEmpty()) {
                        IconButton(onClick = {
                            viewModel.onSearchQueryChanged("")
                            viewModel.onSearchSubmitted()
                        }) {
                            Icon(
                                imageVector = Icons.Default.Close,
                                contentDescription = "Clear",
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                },
                singleLine = true,
                shape = RoundedCornerShape(18.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                    focusedBorderColor = MaterialTheme.colorScheme.primary,
                    unfocusedBorderColor = MaterialTheme.colorScheme.outlineVariant
                ),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { viewModel.onSearchSubmitted() }),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 6.dp)
            )

            // Modern Segmented Pill Switcher: All, Posts, Articles
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 6.dp),
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surface,
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.7f))
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(4.dp),
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    val tabs = listOf("All", "Posts", "Articles")
                    tabs.forEachIndexed { index, title ->
                        val isSelected = uiState.selectedTab == index
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(12.dp))
                                .background(
                                    if (isSelected) MaterialTheme.colorScheme.primaryContainer
                                    else Color.Transparent
                                )
                                .clickable { viewModel.onTabSelected(index) }
                                .padding(vertical = 9.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = title,
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = if (isSelected) FontWeight.ExtraBold else FontWeight.Medium,
                                color = if (isSelected)
                                    MaterialTheme.colorScheme.onPrimaryContainer
                                else
                                    MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }

            // Tag filter chips
            if (uiState.tags.isNotEmpty()) {
                TagChipRow(
                    tags = uiState.tags,
                    selectedTag = uiState.selectedTag,
                    onTagSelected = { viewModel.onTagSelected(it) }
                )
            }

            // Post Feed or Loading/Error State
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
            ) {
                if (uiState.isLoading && uiState.posts.isEmpty()) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                    }
                } else if (uiState.error != null && uiState.posts.isEmpty()) {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Text(
                            text = uiState.error ?: "Unable to load feed",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.error
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Button(
                            onClick = { viewModel.loadFeed(refresh = true) },
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("Retry")
                        }
                    }
                } else if (uiState.posts.isEmpty()) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "No posts found",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                } else {
                    LazyColumn(
                        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 88.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                        modifier = Modifier.fillMaxSize()
                    ) {
                        items(uiState.posts, key = { it.post_id }) { post ->
                            PostCard(
                                post = post,
                                onClick = { onPostClick(post.post_id) },
                                onReact = { reactionType ->
                                    viewModel.reactToPost(post.post_id, reactionType)
                                }
                            )
                        }

                        if (uiState.hasNext) {
                            item {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 16.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Button(
                                        onClick = { viewModel.loadFeed(refresh = false) },
                                        enabled = !uiState.isLoading,
                                        shape = RoundedCornerShape(14.dp)
                                    ) {
                                        if (uiState.isLoading) {
                                            CircularProgressIndicator(
                                                modifier = Modifier.width(20.dp),
                                                color = MaterialTheme.colorScheme.onPrimary,
                                                strokeWidth = 2.dp
                                            )
                                        } else {
                                            Text("Load More")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun BlogBrandLogo(
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(11.dp))
            .background(
                brush = Brush.linearGradient(
                    colors = listOf(Color(0xFF0F172A), Color(0xFF020617))
                )
            ),
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = Modifier.fillMaxSize().padding(4.dp)) {
            val scaleX = size.width / 108f
            val scaleY = size.height / 108f

            // Bottom Lobe / Manuscript Layer: Indigo -> Violet -> Rose Pink
            val bottomPath = Path().apply {
                fillType = PathFillType.EvenOdd
                moveTo(33.75f * scaleX, 52.95f * scaleY)
                cubicTo(
                    59.06f * scaleX, 52.95f * scaleY,
                    77.52f * scaleX, 54.84f * scaleY,
                    77.52f * scaleX, 66.97f * scaleY
                )
                cubicTo(
                    77.52f * scaleX, 81.21f * scaleY,
                    56.95f * scaleX, 81.21f * scaleY,
                    37.97f * scaleX, 81.21f * scaleY
                )
                cubicTo(
                    34.80f * scaleX, 81.21f * scaleY,
                    33.75f * scaleX, 80.16f * scaleY,
                    33.75f * scaleX, 76.99f * scaleY
                )
                close()
                // Inner counter hole for bottom lobe
                moveTo(44.3f * scaleX, 61.38f * scaleY)
                cubicTo(
                    55.37f * scaleX, 61.38f * scaleY,
                    65.39f * scaleX, 62.44f * scaleY,
                    65.39f * scaleX, 66.97f * scaleY
                )
                cubicTo(
                    65.39f * scaleX, 71.72f * scaleY,
                    55.37f * scaleX, 71.72f * scaleY,
                    44.3f * scaleX, 71.72f * scaleY
                )
                close()
            }
            drawPath(
                path = bottomPath,
                brush = Brush.linearGradient(
                    colors = listOf(Color(0xFF4F46E5), Color(0xFF8B5CF6), Color(0xFFF43F5E)),
                    start = Offset(33.75f * scaleX, 52.95f * scaleY),
                    end = Offset(77.52f * scaleX, 81.21f * scaleY)
                )
            )

            // Top Lobe / Front Publication Page: Cyan -> Electric Azure -> Royal Indigo
            val topPath = Path().apply {
                fillType = PathFillType.EvenOdd
                moveTo(33.75f * scaleX, 53.58f * scaleY)
                lineTo(33.75f * scaleX, 30.59f * scaleY)
                cubicTo(
                    33.75f * scaleX, 26.89f * scaleY,
                    34.80f * scaleX, 25.84f * scaleY,
                    37.97f * scaleX, 25.84f * scaleY
                )
                cubicTo(
                    54.84f * scaleX, 25.84f * scaleY,
                    71.72f * scaleX, 27.42f * scaleY,
                    71.72f * scaleX, 39.55f * scaleY
                )
                cubicTo(
                    71.72f * scaleX, 53.58f * scaleY,
                    54.84f * scaleX, 53.58f * scaleY,
                    33.75f * scaleX, 53.58f * scaleY
                )
                close()
                // Inner counter hole for top lobe
                moveTo(44.3f * scaleX, 34.28f * scaleY)
                cubicTo(
                    54.32f * scaleX, 34.28f * scaleY,
                    60.64f * scaleX, 35.33f * scaleY,
                    60.64f * scaleX, 39.55f * scaleY
                )
                cubicTo(
                    60.64f * scaleX, 44.30f * scaleY,
                    54.32f * scaleX, 44.30f * scaleY,
                    44.3f * scaleX, 44.30f * scaleY
                )
                close()
            }
            drawPath(
                path = topPath,
                brush = Brush.linearGradient(
                    colors = listOf(Color(0xFF38BDF8), Color(0xFF2563EB), Color(0xFF4F46E5)),
                    start = Offset(33.75f * scaleX, 25.84f * scaleY),
                    end = Offset(71.72f * scaleX, 53.58f * scaleY)
                )
            )

            // Sparkle Star at upper right
            val starPath = Path().apply {
                moveTo(74.8f * scaleX, 24.8f * scaleY)
                lineTo(76.2f * scaleX, 28.6f * scaleY)
                lineTo(80.0f * scaleX, 30.0f * scaleY)
                lineTo(76.2f * scaleX, 31.4f * scaleY)
                lineTo(74.8f * scaleX, 35.2f * scaleY)
                lineTo(73.4f * scaleX, 31.4f * scaleY)
                lineTo(69.6f * scaleX, 30.0f * scaleY)
                lineTo(73.4f * scaleX, 28.6f * scaleY)
                close()
            }
            drawPath(
                path = starPath,
                color = Color.White
            )
        }
    }
}
