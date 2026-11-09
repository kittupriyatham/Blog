package tech.potluri.blog.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tech.potluri.blog.data.model.AuthUser
import tech.potluri.blog.data.repository.BlogRepository

data class AuthUiState(
    val isLoading: Boolean = true,
    val user: AuthUser? = null,
    val error: String? = null
)

class AuthViewModel(
    private val repository: BlogRepository = BlogRepository()
) : ViewModel() {
    private val _uiState = MutableStateFlow(AuthUiState())
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    init {
        loadSession()
    }

    private fun loadSession() {
        viewModelScope.launch {
            repository.currentUser().fold(
                onSuccess = { user -> _uiState.value = AuthUiState(user = user) },
                onFailure = { _uiState.value = AuthUiState(isLoading = false) }
            )
        }
    }

    fun login(username: String, password: String) {
        if (username.isBlank() || password.isBlank()) {
            _uiState.value = _uiState.value.copy(error = "Enter a username and password.")
            return
        }
        viewModelScope.launch {
            _uiState.value = AuthUiState(isLoading = true)
            repository.login(username.trim(), password).fold(
                onSuccess = { response ->
                    _uiState.value = AuthUiState(user = response.user)
                },
                onFailure = { error ->
                    _uiState.value = AuthUiState(error = "Sign in failed. Check your credentials.")
                }
            )
        }
    }

    fun loginDemo() = login("demo", "demo")

    fun logout() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            repository.logout().fold(
                onSuccess = { _uiState.value = AuthUiState() },
                onFailure = { _uiState.value = _uiState.value.copy(isLoading = false, error = "Sign out failed.") }
            )
        }
    }
}
