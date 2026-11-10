package tech.potluri.blog

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AdminPanelSettings
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.RssFeed
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import tech.potluri.blog.ui.auth.AuthScreen
import tech.potluri.blog.ui.auth.AuthViewModel
import tech.potluri.blog.ui.author.AuthorScreen
import tech.potluri.blog.ui.author.AuthorViewModel
import tech.potluri.blog.ui.detail.DetailScreen
import tech.potluri.blog.ui.feed.FeedScreen
import tech.potluri.blog.ui.feed.FeedViewModel
import tech.potluri.blog.ui.navigation.Screen
import tech.potluri.blog.ui.theme.AppThemeMode
import tech.potluri.blog.ui.theme.BlogTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val prefs = getSharedPreferences("blog_prefs", Context.MODE_PRIVATE)
            val savedMode = prefs.getString("theme_mode", AppThemeMode.DARK.name) ?: AppThemeMode.DARK.name
            var currentThemeMode by rememberSaveable {
                mutableStateOf(try { AppThemeMode.valueOf(savedMode) } catch (e: Exception) { AppThemeMode.DARK })
            }

            fun updateThemeMode(mode: AppThemeMode) {
                currentThemeMode = mode
                prefs.edit().putString("theme_mode", mode.name).apply()
            }

            BlogTheme(themeMode = currentThemeMode) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    BlogApp(
                        currentThemeMode = currentThemeMode,
                        onThemeModeChanged = ::updateThemeMode,
                        onToggleTheme = {
                            val nextMode = when (currentThemeMode) {
                                AppThemeMode.LIGHT -> AppThemeMode.DARK
                                AppThemeMode.DARK -> AppThemeMode.NIGHT
                                AppThemeMode.NIGHT -> AppThemeMode.LIGHT
                            }
                            updateThemeMode(nextMode)
                        }
                    )
                }
            }
        }
    }
}

@Composable
fun BlogApp(
    currentThemeMode: AppThemeMode = AppThemeMode.DARK,
    onThemeModeChanged: (AppThemeMode) -> Unit = {},
    onToggleTheme: () -> Unit = {},
    feedViewModel: FeedViewModel = viewModel(),
    authViewModel: AuthViewModel = viewModel(),
    authorViewModel: AuthorViewModel = viewModel()
) {
    var currentTab by rememberSaveable { mutableStateOf(Screen.Feed.route) }
    var selectedPostId by rememberSaveable { mutableStateOf<String?>(null) }

    BackHandler(enabled = selectedPostId != null || currentTab != Screen.Feed.route) {
        if (selectedPostId != null) {
            selectedPostId = null
        } else {
            currentTab = Screen.Feed.route
        }
    }

    val showBottomBar = selectedPostId == null

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                val navItemColors = NavigationBarItemDefaults.colors(
                    selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                    selectedTextColor = MaterialTheme.colorScheme.primary,
                    indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                    unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Column {
                    HorizontalDivider(
                        thickness = 1.dp,
                        color = MaterialTheme.colorScheme.outlineVariant
                    )
                    NavigationBar(
                        containerColor = MaterialTheme.colorScheme.surface,
                        contentColor = MaterialTheme.colorScheme.onSurface,
                        tonalElevation = 0.dp
                    ) {
                        NavigationBarItem(
                            selected = currentTab == Screen.Feed.route,
                            onClick = {
                                selectedPostId = null
                                currentTab = Screen.Feed.route
                            },
                            icon = {
                                Icon(
                                    imageVector = Icons.Default.RssFeed,
                                    contentDescription = "Feed",
                                    tint = if (currentTab == Screen.Feed.route)
                                        MaterialTheme.colorScheme.onPrimaryContainer
                                    else
                                        MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            },
                            label = {
                                Text(
                                    "Feed",
                                    fontWeight = if (currentTab == Screen.Feed.route) FontWeight.ExtraBold else FontWeight.Medium,
                                    color = if (currentTab == Screen.Feed.route)
                                        MaterialTheme.colorScheme.primary
                                    else
                                        MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            },
                            colors = navItemColors
                        )

                        NavigationBarItem(
                            selected = currentTab == Screen.Admin.route,
                            onClick = {
                                selectedPostId = null
                                currentTab = Screen.Admin.route
                            },
                            icon = {
                                Icon(
                                    imageVector = Icons.Default.AdminPanelSettings,
                                    contentDescription = "Admin",
                                    tint = if (currentTab == Screen.Admin.route)
                                        MaterialTheme.colorScheme.onPrimaryContainer
                                    else
                                        MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            },
                            label = {
                                Text(
                                    "Admin",
                                    fontWeight = if (currentTab == Screen.Admin.route) FontWeight.ExtraBold else FontWeight.Medium,
                                    color = if (currentTab == Screen.Admin.route)
                                        MaterialTheme.colorScheme.primary
                                    else
                                        MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            },
                            colors = navItemColors
                        )

                        NavigationBarItem(
                            selected = currentTab == Screen.Author.route,
                            onClick = {
                                selectedPostId = null
                                authorViewModel.ensureLoaded()
                                currentTab = Screen.Author.route
                            },
                            icon = {
                                Icon(
                                    imageVector = Icons.Default.Person,
                                    contentDescription = "About",
                                    tint = if (currentTab == Screen.Author.route)
                                        MaterialTheme.colorScheme.onPrimaryContainer
                                    else
                                        MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            },
                            label = {
                                Text(
                                    "About",
                                    fontWeight = if (currentTab == Screen.Author.route) FontWeight.ExtraBold else FontWeight.Medium,
                                    color = if (currentTab == Screen.Author.route)
                                        MaterialTheme.colorScheme.primary
                                    else
                                        MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            },
                            colors = navItemColors
                        )
                    }
                }
            }
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            val activePostId = selectedPostId
            if (activePostId != null) {
                DetailScreen(
                    postId = activePostId,
                    onBack = { selectedPostId = null }
                )
            } else {
                Crossfade(
                    targetState = currentTab,
                    animationSpec = tween(durationMillis = 180),
                    label = "tab_crossfade"
                ) { tab ->
                    when (tab) {
                        Screen.Admin.route -> {
                            AuthScreen(
                                viewModel = authViewModel,
                                onPublished = {
                                    feedViewModel.refresh()
                                },
                                onNavigateToFeed = {
                                    currentTab = Screen.Feed.route
                                }
                            )
                        }
                        Screen.Author.route -> {
                            AuthorScreen(
                                viewModel = authorViewModel,
                                currentThemeMode = currentThemeMode,
                                onThemeModeChanged = onThemeModeChanged,
                                onBack = {
                                    currentTab = Screen.Feed.route
                                }
                            )
                        }
                        else -> {
                            FeedScreen(
                                viewModel = feedViewModel,
                                currentThemeMode = currentThemeMode,
                                onToggleTheme = onToggleTheme,
                                onPostClick = { postId ->
                                    selectedPostId = postId
                                },
                                onNavigateToAdmin = {
                                    currentTab = Screen.Admin.route
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}
