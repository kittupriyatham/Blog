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
    val isLoading: Boolean = false,
    val user: AuthUser? = null,
    val error: String? = null
)

class AuthViewModel(
    private val repository: BlogRepository = BlogRepository()
) : ViewModel() {
    private val _uiState = MutableStateFlow(AuthUiState())
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

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
}
