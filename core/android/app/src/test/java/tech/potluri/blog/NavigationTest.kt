package tech.potluri.blog

import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import retrofit2.Response
import tech.potluri.blog.data.model.AuthResponse
import tech.potluri.blog.data.model.AuthUser
import tech.potluri.blog.data.model.AuthorInfo
import tech.potluri.blog.data.model.AuthorResponse
import tech.potluri.blog.data.model.CommentResponse
import tech.potluri.blog.data.model.CommentsResponse
import tech.potluri.blog.data.model.CreatePostRequest
import tech.potluri.blog.data.model.CreatePostResponse
import tech.potluri.blog.data.model.LoginRequest
import tech.potluri.blog.data.model.Post
import tech.potluri.blog.data.model.PostResponse
import tech.potluri.blog.data.model.PostsResponse
import tech.potluri.blog.data.model.ReactionResponse
import tech.potluri.blog.data.model.ShareResponse
import tech.potluri.blog.data.model.TagItem
import tech.potluri.blog.data.model.TagsResponse
import tech.potluri.blog.data.remote.BlogApiService
import tech.potluri.blog.data.repository.BlogRepository
import tech.potluri.blog.ui.auth.AuthViewModel
import tech.potluri.blog.ui.author.AuthorViewModel
import tech.potluri.blog.ui.feed.FeedViewModel
import tech.potluri.blog.ui.theme.BlogTheme

import okhttp3.MultipartBody
import tech.potluri.blog.data.model.ArticlesResponse
import tech.potluri.blog.data.model.MediaUploadResponse
import tech.potluri.blog.data.model.SyndicationPlatform
import tech.potluri.blog.data.model.SyndicationPlatformsResponse

private class FakeBlogApiService : BlogApiService {
    private var currentUser: AuthUser? = null
    private val posts = mutableListOf(
        Post(
            post_id = "post-1",
            type = "post",
            title = "Initial Quantum Post",
            content = "Exploring quantum compilers in Rust.",
            timestamp = "2026-10-31",
            tags = listOf("quantum", "rust")
        )
    )
    private val articles = mutableListOf(
        Post(
            post_id = "art-1",
            type = "article",
            title = "Deep Dive Quantum Error Correction",
            content = "Full guide to surface codes.",
            timestamp = "2026-11-01"
        )
    )

    override suspend fun login(request: LoginRequest): Response<AuthResponse> {
        val isDemo = request.username == "demo" && request.password == "demo"
        val user = AuthUser(
            username = if (isDemo) "Demo Publisher" else request.username,
            is_demo = isDemo,
            is_admin = !isDemo
        )
        currentUser = user
        return Response.success(AuthResponse(status = "success", user = user))
    }

    override suspend fun currentUser(): Response<AuthResponse> {
        val user = currentUser
        return if (user != null) {
            Response.success(AuthResponse(status = "success", user = user))
        } else {
            Response.error(401, okhttp3.ResponseBody.create(null, ""))
        }
    }

    override suspend fun logout(): Response<AuthResponse> {
        currentUser = null
        return Response.success(AuthResponse(status = "success"))
    }

    override suspend fun createPost(request: CreatePostRequest): Response<CreatePostResponse> {
        val created = Post(
            post_id = "post-${posts.size + 1}",
            type = request.type,
            title = request.title ?: "",
            content = request.content,
            timestamp = "2026-11-09",
            tags = request.tags,
            media_paths = request.media_paths
        )
        posts.add(0, created)
        return Response.success(
            CreatePostResponse(status = "success", message = "Post created", post = created)
        )
    }

    override suspend fun uploadMedia(file: MultipartBody.Part): Response<MediaUploadResponse> {
        return Response.success(
            MediaUploadResponse(
                status = "success",
                post_id = "post-temp",
                url = "/media/test_upload.png",
                name = "test_upload.png"
            )
        )
    }

    override suspend fun getSyndicationPlatforms(kind: String): SyndicationPlatformsResponse {
        return SyndicationPlatformsResponse(
            status = "success",
            platforms = listOf(
                SyndicationPlatform(id = "linkedin", label = "LinkedIn", configured = true, limit = 3000),
                SyndicationPlatform(id = "twitter", label = "X / Twitter", configured = true, limit = 280)
            )
        )
    }

    override suspend fun getArticles(): ArticlesResponse {
        return ArticlesResponse(
            status = "success",
            count = articles.size,
            articles = articles.toList()
        )
    }

    override suspend fun getPosts(
        page: Int,
        limit: Int,
        type: String?,
        tag: String?,
        query: String?
    ): PostsResponse {
        return PostsResponse(
            posts = posts.toList(),
            page = 1,
            per_page = limit,
            total = posts.size,
            total_pages = 1,
            has_next = false,
            has_prev = false
        )
    }

    override suspend fun getPost(postId: String): PostResponse {
        val found = posts.find { it.post_id == postId } ?: articles.first { it.post_id == postId }
        return PostResponse(post = found)
    }

    override suspend fun getComments(postId: String): CommentsResponse = CommentsResponse()

    override suspend fun addComment(postId: String, name: String, body: String): CommentResponse {
        throw UnsupportedOperationException()
    }

    override suspend fun react(postId: String, type: String): ReactionResponse = ReactionResponse()

    override suspend fun share(postId: String, platform: String): ShareResponse = ShareResponse()

    override suspend fun getTags(): TagsResponse =
        TagsResponse(tags = listOf(TagItem(tag = "quantum", count = 1)))

    override suspend fun getAuthor(): AuthorResponse =
        AuthorResponse(
            author = AuthorInfo(
                name = "Potluri Krishna Priyatham",
                role = "PhD Scholar",
                organization = "SRM AP University",
                research_field = "Quantum Technologies & Quantum Computing",
                bio_full = "Researching Quantum Technologies and Quantum Computing."
            )
        )
}

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], qualifiers = "w411dp-h891dp-xxhdpi")
class NavigationTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    private fun clickBottomTab(label: String) {
        val nodes = composeTestRule.onAllNodesWithText(label)
        val count = nodes.fetchSemanticsNodes().size
        assertTrue("Expected bottom tab '$label' to exist", count >= 1)
        nodes[count - 1].performClick()
        composeTestRule.waitForIdle()
    }

    @Test
    fun testAllTabTransitionsAndMobilePublishing() {
        val repo = BlogRepository(FakeBlogApiService())
        val feedVm = FeedViewModel(repo)
        val authVm = AuthViewModel(repo)
        val authorVm = AuthorViewModel(repo)

        composeTestRule.setContent {
            var mode by androidx.compose.runtime.remember {
                androidx.compose.runtime.mutableStateOf(tech.potluri.blog.ui.theme.AppThemeMode.DARK)
            }
            BlogTheme(themeMode = mode) {
                BlogApp(
                    currentThemeMode = mode,
                    onThemeModeChanged = { mode = it },
                    onToggleTheme = {
                        mode = when (mode) {
                            tech.potluri.blog.ui.theme.AppThemeMode.LIGHT -> tech.potluri.blog.ui.theme.AppThemeMode.DARK
                            tech.potluri.blog.ui.theme.AppThemeMode.DARK -> tech.potluri.blog.ui.theme.AppThemeMode.NIGHT
                            tech.potluri.blog.ui.theme.AppThemeMode.NIGHT -> tech.potluri.blog.ui.theme.AppThemeMode.LIGHT
                        }
                    },
                    feedViewModel = feedVm,
                    authViewModel = authVm,
                    authorViewModel = authorVm
                )
            }
        }
        composeTestRule.waitForIdle()

        // 1. Initial Feed screen
        composeTestRule.onNodeWithText("Search posts & articles…").assertIsDisplayed()
        composeTestRule.onNodeWithText("Exploring quantum compilers in Rust.").assertIsDisplayed()

        // 2. Feed -> About
        clickBottomTab("About")
        composeTestRule.onNodeWithText("About Author").assertIsDisplayed()
        composeTestRule.onNodeWithText("Potluri Krishna Priyatham").assertIsDisplayed()

        // 3. About -> Feed -> About
        clickBottomTab("Feed")
        composeTestRule.onNodeWithText("Search posts & articles…").assertIsDisplayed()
        clickBottomTab("About")
        composeTestRule.onNodeWithText("About Author").assertIsDisplayed()

        // 4. About -> Admin -> Feed -> About
        clickBottomTab("Admin")
        composeTestRule.onNodeWithText("Admin Access").assertIsDisplayed()
        composeTestRule.onNodeWithText("Admin Sign In").assertIsDisplayed()
        composeTestRule.onNodeWithText("Use Google Passwords").assertIsDisplayed()
        clickBottomTab("Feed")
        composeTestRule.onNodeWithText("Search posts & articles…").assertIsDisplayed()
        clickBottomTab("About")
        composeTestRule.onNodeWithText("About Author").assertIsDisplayed()

        // 5. About -> Admin -> Sign in with real account credentials & save password
        clickBottomTab("Admin")
        composeTestRule.onNodeWithText("Username").performTextInput("kittu")
        composeTestRule.onNodeWithText("Password").performTextInput("secret")
        // Verify show/hide password toggle works
        composeTestRule.onNodeWithContentDescription("Show password").performClick()
        composeTestRule.waitForIdle()
        composeTestRule.onNodeWithContentDescription("Hide password").performClick()
        composeTestRule.waitForIdle()
        composeTestRule.onNodeWithText("Sign In & Save Password").performClick()
        composeTestRule.waitForIdle()

        composeTestRule.onNodeWithText("Publisher Studio").assertIsDisplayed()
        composeTestRule.onNodeWithText("Administrator").assertIsDisplayed()
        composeTestRule.onNodeWithText("New Post").assertIsDisplayed()
        composeTestRule.onNodeWithText("Upload File").assertIsDisplayed()
        composeTestRule.onNodeWithText("Attach Article").assertIsDisplayed()
        composeTestRule.onNodeWithText("Insert Block").assertIsDisplayed()
        composeTestRule.onNodeWithText("Syndicate to (POSSE)").assertIsDisplayed()
        composeTestRule.onNodeWithText("LinkedIn (3000ch)").assertIsDisplayed()

        // 5b. Sign out and verify saved password appears and works via "Use Google Passwords (kittu)"
        composeTestRule.onNodeWithText("Sign out").performClick()
        composeTestRule.waitForIdle()
        composeTestRule.onNodeWithText("Use Google Passwords (kittu)").assertIsDisplayed()
        composeTestRule.onNodeWithText("Sign in as kittu").assertIsDisplayed()
        composeTestRule.onNodeWithText("Use Google Passwords (kittu)").performClick()
        composeTestRule.waitForIdle()
        composeTestRule.onNodeWithText("Publisher Studio").assertIsDisplayed()

        // Select syndication platform
        composeTestRule.onNodeWithText("LinkedIn (3000ch)").performClick()

        // Attach Article via picker
        composeTestRule.onNodeWithText("Attach Article").performClick()
        composeTestRule.waitForIdle()
        composeTestRule.onNodeWithText("Deep Dive Quantum Error Correction").assertIsDisplayed()
        composeTestRule.onNodeWithText("Deep Dive Quantum Error Correction").performClick()
        composeTestRule.waitForIdle()

        // 6. Signed-in Admin -> Feed -> Signed-in Admin -> About -> Signed-in Admin
        clickBottomTab("Feed")
        composeTestRule.onNodeWithText("Search posts & articles…").assertIsDisplayed()
        clickBottomTab("Admin")
        composeTestRule.onNodeWithText("Publisher Studio").assertIsDisplayed()
        clickBottomTab("About")
        composeTestRule.onNodeWithText("About Author").assertIsDisplayed()
        composeTestRule.onNodeWithText("Potluri Krishna Priyatham").assertIsDisplayed()

        // 7. Test Theme Appearance switching (Light, Dark, Night) in About screen & verify icons in Night Mode
        composeTestRule.onNodeWithText("Appearance & Theme").assertIsDisplayed()
        composeTestRule.onNodeWithText("Light").performClick()
        composeTestRule.waitForIdle()
        composeTestRule.onNodeWithText("Night").performClick()
        composeTestRule.waitForIdle()

        // Verify Feed, Admin, and About bottom navigation icons are displayed in Night Mode
        composeTestRule.onNodeWithContentDescription("Feed", useUnmergedTree = true).assertIsDisplayed()
        composeTestRule.onNodeWithContentDescription("Admin", useUnmergedTree = true).assertIsDisplayed()
        composeTestRule.onNodeWithContentDescription("About", useUnmergedTree = true).assertIsDisplayed()

        // Navigate across tabs in Night Mode and assert icons remain displayed
        clickBottomTab("Feed")
        composeTestRule.onNodeWithContentDescription("Feed", useUnmergedTree = true).assertIsDisplayed()
        composeTestRule.onNodeWithContentDescription("Admin", useUnmergedTree = true).assertIsDisplayed()
        composeTestRule.onNodeWithContentDescription("About", useUnmergedTree = true).assertIsDisplayed()

        clickBottomTab("Admin")
        composeTestRule.onNodeWithContentDescription("Feed", useUnmergedTree = true).assertIsDisplayed()
        composeTestRule.onNodeWithContentDescription("Admin", useUnmergedTree = true).assertIsDisplayed()
        composeTestRule.onNodeWithContentDescription("About", useUnmergedTree = true).assertIsDisplayed()

        clickBottomTab("About")
        composeTestRule.onNodeWithText("Dark").performClick()
        composeTestRule.waitForIdle()

        // 8. About Back arrow -> Feed
        composeTestRule.onNodeWithContentDescription("Back").performClick()
        composeTestRule.waitForIdle()
        composeTestRule.onNodeWithText("Search posts & articles…").assertIsDisplayed()

        // 9. Publish the post from Admin with embedded article and verify it appears on Feed
        clickBottomTab("Admin")
        composeTestRule.onNodeWithText("Publish").performScrollTo().performClick()
        composeTestRule.waitForIdle()
        composeTestRule.onNodeWithText("Post published successfully!").assertIsDisplayed()

        clickBottomTab("Feed")
        composeTestRule.onNodeWithText("/article/art-1").assertIsDisplayed()
    }
}
