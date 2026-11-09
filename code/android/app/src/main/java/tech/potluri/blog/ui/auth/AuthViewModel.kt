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
import tech.potluri.blog.data.repository.BlogRepository

data class AuthUiState(
    val isLoading: Boolean = false,
    val user: AuthUser? = null,
    val error: String? = null,
    val loginSucceeded: Boolean = false,
    val isPosting: Boolean = false,
    val postCreated: Boolean = false,
    val postError: String? = null
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
            _uiState.value = AuthUiState(isLoading = true)
            repository.currentUser().fold(
                onSuccess = { user -> _uiState.value = AuthUiState(user = user) },
                onFailure = { _uiState.value = AuthUiState(isLoading = false) }
            )
        }
    }

    fun consumeLoginSuccess() {
        _uiState.value = _uiState.value.copy(loginSucceeded = false)
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
            _uiState.value = AuthUiState(isLoading = true)
            repository.login(username.trim(), password).fold(
                onSuccess = { response ->
                    _uiState.value = AuthUiState(user = response.user, loginSucceeded = response.user != null)
                },
                onFailure = { error ->
                    val message = when {
                        error is HttpException && error.code() == 401 -> "Sign in failed. Check your credentials."
                        error is IOException -> "Unable to connect. Check your connection and try again."
                        else -> "Sign in is unavailable. Please try again later."
                    }
                    _uiState.value = AuthUiState(error = message)
                }
            )
        }
    }

    fun loginDemo() = login("demo", "demo")

    fun createPost(
        content: String,
        title: String? = null,
        type: String = "post",
        tags: List<String> = emptyList(),
        onCreated: () -> Unit = {}
    ) {
        if (_uiState.value.isPosting) return
        if (content.isBlank()) {
            _uiState.value = _uiState.value.copy(postError = "Post content cannot be empty.")
            return
        }
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isPosting = true, postError = null, postCreated = false)
            repository.createPost(
                content = content.trim(),
                title = title?.trim()?.ifBlank { null },
                type = type,
                tags = tags
            ).fold(
                onSuccess = {
                    _uiState.value = _uiState.value.copy(isPosting = false, postCreated = true, postError = null)
                    onCreated()
                },
                onFailure = { err ->
                    _uiState.value = _uiState.value.copy(
                        isPosting = false,
                        postError = err.localizedMessage ?: "Failed to publish post. Try again."
                    )
                }
            )
        }
    }

    fun resetPostState() {
        _uiState.value = _uiState.value.copy(postCreated = false, postError = null)
    }
}
