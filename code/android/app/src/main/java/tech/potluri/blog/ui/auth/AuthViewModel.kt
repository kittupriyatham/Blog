package tech.potluri.blog.ui.auth

import java.io.IOException
import retrofit2.HttpException
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tech.potluri.blog.data.model.AuthUser
import tech.potluri.blog.data.model.Post
import tech.potluri.blog.data.model.SyndicationPlatform
import tech.potluri.blog.data.repository.BlogRepository

data class AttachedMediaItem(
    val url: String,
    val name: String
)

data class AuthUiState(
    val isLoading: Boolean = false,
    val user: AuthUser? = null,
    val error: String? = null,
    val loginSucceeded: Boolean = false,
    val isPosting: Boolean = false,
    val postCreated: Boolean = false,
    val postError: String? = null,
    val draftTitle: String = "",
    val draftContent: String = "",
    val draftTags: String = "",
    val syndicationPlatforms: List<SyndicationPlatform> = emptyList(),
    val selectedPlatforms: Set<String> = emptySet(),
    val attachedMedia: List<AttachedMediaItem> = emptyList(),
    val isUploadingMedia: Boolean = false,
    val uploadError: String? = null,
    val availableArticles: List<Post> = emptyList(),
    val isLoadingArticles: Boolean = false
)

class AuthViewModel(
    private val repository: BlogRepository = BlogRepository()
) : ViewModel() {
    private val _uiState = MutableStateFlow(AuthUiState(isLoading = true))
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    init {
        loadSession()
    }

    private fun loadSession() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            repository.currentUser().fold(
                onSuccess = { user ->
                    _uiState.value = _uiState.value.copy(isLoading = false, user = user, error = null)
                    loadComposerOptions()
                },
                onFailure = { _uiState.value = _uiState.value.copy(isLoading = false, user = null) }
            )
        }
    }

    fun loadComposerOptions() {
        viewModelScope.launch {
            // Load syndication platforms
            repository.fetchSyndicationPlatforms("post").fold(
                onSuccess = { platforms ->
                    _uiState.value = _uiState.value.copy(syndicationPlatforms = platforms)
                },
                onFailure = { /* non-fatal */ }
            )
            // Load available articles for attachment picker
            loadArticles()
        }
    }

    fun loadArticles() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoadingArticles = true)
            repository.fetchArticles().fold(
                onSuccess = { articles ->
                    _uiState.value = _uiState.value.copy(isLoadingArticles = false, availableArticles = articles)
                },
                onFailure = {
                    _uiState.value = _uiState.value.copy(isLoadingArticles = false)
                }
            )
        }
    }

    fun consumeLoginSuccess() {
        _uiState.value = _uiState.value.copy(loginSucceeded = false)
    }

    fun updateDraftTitle(title: String) {
        _uiState.value = _uiState.value.copy(draftTitle = title)
    }

    fun updateDraftContent(content: String) {
        _uiState.value = _uiState.value.copy(
            draftContent = content,
            postError = if (_uiState.value.postError != null) null else _uiState.value.postError
        )
    }

    fun updateDraftTags(tags: String) {
        _uiState.value = _uiState.value.copy(draftTags = tags)
    }

    fun togglePlatform(platformId: String) {
        val current = _uiState.value.selectedPlatforms.toMutableSet()
        if (current.contains(platformId)) {
            current.remove(platformId)
        } else {
            current.add(platformId)
        }
        _uiState.value = _uiState.value.copy(selectedPlatforms = current)
    }

    fun appendSnippet(snippet: String) {
        val currentContent = _uiState.value.draftContent
        val newContent = if (currentContent.isBlank()) {
            snippet
        } else {
            currentContent.trimEnd() + "\n\n" + snippet
        }
        updateDraftContent(newContent)
    }

    fun attachArticle(articleId: String) {
        appendSnippet("/article/$articleId")
    }

    fun attachPost(postId: String) {
        appendSnippet("/post/$postId")
    }

    fun uploadMediaFile(fileName: String, mimeType: String, bytes: ByteArray) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isUploadingMedia = true, uploadError = null)
            repository.uploadMedia(fileName, mimeType, bytes).fold(
                onSuccess = { response ->
                    val newMedia = _uiState.value.attachedMedia + AttachedMediaItem(
                        url = response.url,
                        name = response.name.ifBlank { fileName }
                    )
                    _uiState.value = _uiState.value.copy(
                        isUploadingMedia = false,
                        attachedMedia = newMedia,
                        uploadError = null
                    )
                },
                onFailure = { err ->
                    _uiState.value = _uiState.value.copy(
                        isUploadingMedia = false,
                        uploadError = err.localizedMessage ?: "Failed to upload file."
                    )
                }
            )
        }
    }

    fun removeAttachedMedia(url: String) {
        val updated = _uiState.value.attachedMedia.filter { it.url != url }
        _uiState.value = _uiState.value.copy(attachedMedia = updated)
    }

    fun logout() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            repository.logout().fold(
                onSuccess = { _uiState.value = AuthUiState() },
                onFailure = {
                    _uiState.value = _uiState.value.copy(isLoading = false, error = "Sign out failed. Try again.")
                }
            )
        }
    }

    fun login(username: String, password: String) {
        if (_uiState.value.isLoading) return
        if (username.isBlank() || password.isBlank()) {
            _uiState.value = _uiState.value.copy(error = "Enter a username and password.")
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            repository.login(username.trim(), password).fold(
                onSuccess = { response ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        user = response.user,
                        error = null,
                        loginSucceeded = response.user != null
                    )
                    loadComposerOptions()
                },
                onFailure = { error ->
                    val message = when {
                        error is HttpException && error.code() == 401 -> "Sign in failed. Check your credentials."
                        error is IOException -> "Unable to connect. Check your connection and try again."
                        else -> "Sign in is unavailable. Please try again later."
                    }
                    _uiState.value = _uiState.value.copy(isLoading = false, user = null, error = message)
                }
            )
        }
    }

    fun loginDemo() = login("demo", "demo")

    fun createPost(
        content: String,
        title: String? = null,
        tags: List<String> = emptyList(),
        onCreated: () -> Unit = {}
    ) {
        if (_uiState.value.isPosting) return
        val mediaUrls = _uiState.value.attachedMedia.map { it.url }
        if (content.isBlank() && mediaUrls.isEmpty()) {
            _uiState.value = _uiState.value.copy(postError = "Post content or an attachment is required.")
            return
        }
        val submittedTitle = _uiState.value.draftTitle
        val submittedContent = _uiState.value.draftContent
        val submittedTags = _uiState.value.draftTags
        val platformsList = _uiState.value.selectedPlatforms.toList()

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isPosting = true, postError = null, postCreated = false)
            repository.createPost(
                content = content.trim(),
                title = title?.trim()?.ifBlank { null },
                type = "post",
                tags = tags,
                mediaPaths = mediaUrls,
                platforms = platformsList
            ).fold(
                onSuccess = {
                    val cur = _uiState.value
                    _uiState.value = cur.copy(
                        isPosting = false,
                        postCreated = true,
                        postError = null,
                        draftTitle = if (cur.draftTitle == submittedTitle) "" else cur.draftTitle,
                        draftContent = if (cur.draftContent == submittedContent) "" else cur.draftContent,
                        draftTags = if (cur.draftTags == submittedTags) "" else cur.draftTags,
                        attachedMedia = emptyList(),
                        selectedPlatforms = emptySet()
                    )
                    onCreated()
                },
                onFailure = { err ->
                    _uiState.value = _uiState.value.copy(
                        isPosting = false,
                        postError = if (err is HttpException && err.code() == 401) {
                            "Your session expired. Sign out and sign in again to publish."
                        } else {
                            err.localizedMessage ?: "Failed to publish post. Try again."
                        }
                    )
                }
            )
        }
    }

    fun resetPostState() {
        _uiState.value = _uiState.value.copy(postCreated = false, postError = null)
    }
}
