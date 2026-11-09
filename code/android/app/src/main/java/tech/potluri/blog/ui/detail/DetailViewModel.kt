package tech.potluri.blog.ui.detail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import tech.potluri.blog.data.model.Comment
import tech.potluri.blog.data.model.Post
import tech.potluri.blog.data.repository.BlogRepository

data class DetailUiState(
    val isLoading: Boolean = true,
    val post: Post? = null,
    val comments: List<Comment> = emptyList(),
    val isCommentsLoading: Boolean = false,
    val commentsError: String? = null,
    val error: String? = null
)

class DetailViewModel(
    private val repository: BlogRepository = BlogRepository()
) : ViewModel() {

    private val _uiState = MutableStateFlow(DetailUiState())
    val uiState: StateFlow<DetailUiState> = _uiState.asStateFlow()
    private val reactionMutex = Mutex()

    private var reactionRequest = 0L

    fun loadPost(postId: String) {
        reactionRequest++
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
            _uiState.value = _uiState.value.copy(isCommentsLoading = true, commentsError = null)
            repository.fetchComments(postId).fold(
                onSuccess = { comments ->
                    _uiState.value = _uiState.value.copy(
                        comments = comments,
                        isCommentsLoading = false,
                        commentsError = null
                    )
                },
                onFailure = { error ->
                    _uiState.value = _uiState.value.copy(
                        isCommentsLoading = false,
                        commentsError = error.localizedMessage ?: "Failed to load comments"
                    )
                }
            )
        }
    }

    suspend fun addComment(postId: String, name: String, body: String): Boolean {
        return repository.postComment(postId, name, body).fold(
            onSuccess = { newComment ->
                _uiState.value = _uiState.value.copy(
                    comments = _uiState.value.comments + newComment,
                    commentsError = null
                )
                true
            },
            onFailure = {
                false
            }
        )
    }

    fun react(reactionType: String) {
        val postId = _uiState.value.post?.post_id ?: return
        val request = ++reactionRequest
        viewModelScope.launch {
            reactionMutex.withLock {
                repository.submitReaction(postId, reactionType).onSuccess { response ->
                    _uiState.value.post?.takeIf {
                        it.post_id == postId && request == reactionRequest
                    }?.let { currentPost ->
                        _uiState.value = _uiState.value.copy(
                            post = currentPost.copy(
                                reactions = response.reactions,
                                likes = response.likes
                            )
                        )
                    }
                }
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
