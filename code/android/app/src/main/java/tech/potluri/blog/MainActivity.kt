package tech.potluri.blog

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AdminPanelSettings
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.RssFeed
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
import androidx.lifecycle.viewmodel.compose.viewModel
import tech.potluri.blog.ui.author.AuthorScreen
import tech.potluri.blog.ui.author.AuthorViewModel
import tech.potluri.blog.ui.auth.AuthScreen
import tech.potluri.blog.ui.auth.AuthViewModel
import tech.potluri.blog.ui.detail.DetailScreen
import tech.potluri.blog.ui.feed.FeedScreen
import tech.potluri.blog.ui.feed.FeedViewModel
import tech.potluri.blog.ui.navigation.Screen
import tech.potluri.blog.ui.theme.BlogTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            BlogTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    BlogApp()
                }
            }
        }
    }
}

@Composable
fun BlogApp(
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
                NavigationBar(
                    containerColor = MaterialTheme.colorScheme.surface,
                    contentColor = MaterialTheme.colorScheme.primary
                ) {
                    NavigationBarItem(
                        selected = currentTab == Screen.Feed.route,
                        onClick = {
                            selectedPostId = null
                            currentTab = Screen.Feed.route
                        },
                        icon = { Icon(Icons.Default.RssFeed, contentDescription = "Feed") },
                        label = { Text("Feed") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = MaterialTheme.colorScheme.primary,
                            indicatorColor = MaterialTheme.colorScheme.primaryContainer
                        )
                    )

                    NavigationBarItem(
                        selected = currentTab == Screen.Admin.route,
                        onClick = {
                            selectedPostId = null
                            currentTab = Screen.Admin.route
                        },
                        icon = { Icon(Icons.Default.AdminPanelSettings, contentDescription = "Admin") },
                        label = { Text("Admin") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = MaterialTheme.colorScheme.primary,
                            indicatorColor = MaterialTheme.colorScheme.primaryContainer
                        )
                    )

                    NavigationBarItem(
                        selected = currentTab == Screen.Author.route,
                        onClick = {
                            selectedPostId = null
                            authorViewModel.ensureLoaded()
                            currentTab = Screen.Author.route
                        },
                        icon = { Icon(Icons.Default.Person, contentDescription = "About") },
                        label = { Text("About") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = MaterialTheme.colorScheme.primary,
                            indicatorColor = MaterialTheme.colorScheme.primaryContainer
                        )
                    )
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
                when (currentTab) {
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
                            onBack = {
                                currentTab = Screen.Feed.route
                            }
                        )
                    }
                    else -> {
                        FeedScreen(
                            viewModel = feedViewModel,
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
