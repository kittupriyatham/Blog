package tech.potluri.blog.ui.feed

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tech.potluri.blog.data.model.Post
import tech.potluri.blog.data.model.TagItem
import tech.potluri.blog.data.repository.BlogRepository

data class FeedUiState(
    val isLoading: Boolean = false,
    val posts: List<Post> = emptyList(),
    val tags: List<TagItem> = emptyList(),
    val selectedTab: Int = 0, // 0 = All, 1 = Posts, 2 = Articles
    val selectedTag: String? = null,
    val searchQuery: String = "",
    val error: String? = null,
    val page: Int = 1,
    val hasNext: Boolean = false
)

class FeedViewModel(
    private val repository: BlogRepository = BlogRepository()
) : ViewModel() {

    private val _uiState = MutableStateFlow(FeedUiState())
    val uiState: StateFlow<FeedUiState> = _uiState.asStateFlow()

    init {
        loadFeed()
        loadTags()
    }

    fun loadFeed(refresh: Boolean = false) {
        viewModelScope.launch {
            val currentPage = if (refresh) 1 else _uiState.value.page
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            val typeFilter = when (_uiState.value.selectedTab) {
                1 -> "post"
                2 -> "article"
                else -> null
            }

            val queryFilter = _uiState.value.searchQuery.ifBlank { null }
            val tagFilter = _uiState.value.selectedTag

            val result = repository.fetchPosts(
                page = currentPage,
                limit = 12,
                type = typeFilter,
                tag = tagFilter,
                query = queryFilter
            )

            result.fold(
                onSuccess = { response ->
                    val updatedPosts = if (refresh) response.posts else _uiState.value.posts + response.posts
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        posts = updatedPosts,
                        page = response.page,
                        hasNext = response.has_next,
                        error = null
                    )
                },
                onFailure = { err ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = err.localizedMessage ?: "Failed to load feed"
                    )
                }
            )
        }
    }

    private fun loadTags() {
        viewModelScope.launch {
            repository.fetchTags().onSuccess { tags ->
                _uiState.value = _uiState.value.copy(tags = tags)
            }
        }
    }

    fun onTabSelected(index: Int) {
        if (_uiState.value.selectedTab != index) {
            _uiState.value = _uiState.value.copy(selectedTab = index)
            loadFeed(refresh = true)
        }
    }

    fun onTagSelected(tag: String?) {
        _uiState.value = _uiState.value.copy(selectedTag = tag)
        loadFeed(refresh = true)
    }

    fun onSearchQueryChanged(q: String) {
        _uiState.value = _uiState.value.copy(searchQuery = q)
    }

    fun onSearchSubmitted() {
        loadFeed(refresh = true)
    }

    fun reactToPost(postId: String, reactionType: String) {
        viewModelScope.launch {
            repository.submitReaction(postId, reactionType).onSuccess { response ->
                val currentPosts = _uiState.value.posts.map { p ->
                    if (p.post_id == postId) {
                        p.copy(reactions = response.reactions, likes = response.likes)
                    } else p
                }
                _uiState.value = _uiState.value.copy(posts = currentPosts)
            }
        }
    }
}
