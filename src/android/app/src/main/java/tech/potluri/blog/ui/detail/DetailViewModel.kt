package tech.potluri.blog.ui.detail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tech.potluri.blog.data.model.Comment
import tech.potluri.blog.data.model.Post
import tech.potluri.blog.data.repository.BlogRepository

data class DetailUiState(
    val isLoading: Boolean = true,
    val post: Post? = null,
    val comments: List<Comment> = emptyList(),
    val isCommentsLoading: Boolean = false,
    val error: String? = null
)

class DetailViewModel(
    private val repository: BlogRepository = BlogRepository()
) : ViewModel() {

    private val _uiState = MutableStateFlow(DetailUiState())
    val uiState: StateFlow<DetailUiState> = _uiState.asStateFlow()

    fun loadPost(postId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            repository.fetchPostDetail(postId).fold(
                onSuccess = { post ->
                    _uiState.value = _uiState.value.copy(isLoading = false, post = post)
                    loadComments(postId)
                },
                onFailure = { err ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = err.localizedMessage ?: "Failed to load post"
                    )
                }
            )
        }
    }

    fun loadComments(postId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isCommentsLoading = true)
            repository.fetchComments(postId).onSuccess { comments ->
                _uiState.value = _uiState.value.copy(
                    comments = comments,
                    isCommentsLoading = false
                )
            }
        }
    }

    suspend fun addComment(postId: String, name: String, body: String): Boolean {
        return repository.postComment(postId, name, body).fold(
            onSuccess = { newComment ->
                _uiState.value = _uiState.value.copy(
                    comments = _uiState.value.comments + newComment
                )
                true
            },
            onFailure = {
                false
            }
        )
    }

    fun react(reactionType: String) {
        val currentPost = _uiState.value.post ?: return
        viewModelScope.launch {
            repository.submitReaction(currentPost.post_id, reactionType).onSuccess { updatedReactions ->
                _uiState.value = _uiState.value.copy(
                    post = currentPost.copy(
                        reactions = updatedReactions,
                        likes = currentPost.likes + 1
                    )
                )
            }
        }
    }

    fun sharePost(onShareIntentReady: (title: String, url: String) -> Unit) {
        val currentPost = _uiState.value.post ?: return
        viewModelScope.launch {
            repository.recordShare(currentPost.post_id)
            val url = "https://blog.potluri-krishna-priyatham.tech/${if (currentPost.type == "article") "article" else "post"}/${currentPost.post_id}"
            onShareIntentReady(currentPost.title.ifBlank { "Check out this post" }, url)
        }
    }
}
