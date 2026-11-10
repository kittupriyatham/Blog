package tech.potluri.blog.ui.author

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import tech.potluri.blog.data.model.AuthorInfo
import tech.potluri.blog.data.repository.BlogRepository

data class AuthorUiState(
    val isLoading: Boolean = true,
    val author: AuthorInfo? = null,
    val error: String? = null
)

class AuthorViewModel(
    private val repository: BlogRepository = BlogRepository()
) : ViewModel() {

    private val _uiState = MutableStateFlow(AuthorUiState())
    val uiState: StateFlow<AuthorUiState> = _uiState.asStateFlow()

    init {
        loadAuthor()
    }

    fun ensureLoaded() {
        if (!_uiState.value.isLoading && _uiState.value.author == null) {
            loadAuthor()
        }
    }

    fun loadAuthor() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            repository.fetchAuthor().fold(
                onSuccess = { response ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        author = response.author,
                        error = null
                    )
                },
                onFailure = { err ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = err.localizedMessage ?: "Failed to load author details"
                    )
                }
            )
        }
    }
}
