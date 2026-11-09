package tech.potluri.blog.data.repository

import java.io.IOException
import retrofit2.HttpException
import tech.potluri.blog.data.model.AuthorResponse
import tech.potluri.blog.data.model.AuthResponse
import tech.potluri.blog.data.model.Comment
import tech.potluri.blog.data.model.LoginRequest
import tech.potluri.blog.data.model.AuthUser
import tech.potluri.blog.data.model.Post
import tech.potluri.blog.data.model.PostsResponse
import tech.potluri.blog.data.model.ReactionResponse
import tech.potluri.blog.data.model.TagItem
import tech.potluri.blog.data.remote.BlogApiService
import tech.potluri.blog.data.remote.NetworkModule

class BlogRepository(
    private val api: BlogApiService = NetworkModule.api
) {
    suspend fun login(username: String, password: String): Result<AuthResponse> =
        requestResponse { api.login(LoginRequest(username, password)) }

    suspend fun logout(): Result<Unit> =
        requestResponse { api.logout() }.map { Unit }

    suspend fun currentUser(): Result<AuthUser> =
        requestResponse { api.currentUser() }.fold(
            onSuccess = { response ->
                response.user?.let { Result.success(it) }
                    ?: Result.failure(IOException("Authenticated user missing from server response"))
            },
            onFailure = { Result.failure(it) }
        )

    suspend fun createPost(
        content: String,
        title: String? = null,
        type: String = "post",
        tags: List<String> = emptyList()
    ): Result<Post> = requestResponse {
        api.createPost(tech.potluri.blog.data.model.CreatePostRequest(
            content = content,
            title = title,
            type = type,
            tags = tags
        ))
    }.fold(
        onSuccess = { response ->
            response.post?.let { Result.success(it) }
                ?: Result.failure(IllegalStateException(response.message ?: "Failed to create post"))
        },
        onFailure = { Result.failure(it) }
    )

    suspend fun fetchPosts(
        page: Int,
        limit: Int,
        type: String?,
        tag: String?,
        query: String?
    ): Result<PostsResponse> = request { api.getPosts(page, limit, type, tag, query) }

    suspend fun fetchPostDetail(postId: String): Result<Post> =
        request { api.getPost(postId).post }

    suspend fun fetchComments(postId: String): Result<List<Comment>> =
        request { api.getComments(postId).comments }

    suspend fun postComment(postId: String, name: String, body: String): Result<Comment> =
        request { api.addComment(postId, name, body).comment }

    suspend fun submitReaction(postId: String, type: String): Result<ReactionResponse> =
        request { api.react(postId, type) }

    suspend fun recordShare(postId: String): Result<Int> =
        request { api.share(postId).shares }

    suspend fun fetchTags(): Result<List<TagItem>> =
        request { api.getTags().tags }

    suspend fun fetchAuthor(): Result<AuthorResponse> =
        request { api.getAuthor() }

    private suspend fun <T> request(block: suspend () -> T): Result<T> =
        try {
            Result.success(block())
        } catch (error: kotlinx.coroutines.CancellationException) {
            throw error
        } catch (error: Exception) {
            Result.failure(error)
        }

    private suspend fun <T> requestResponse(
        block: suspend () -> retrofit2.Response<T>
    ): Result<T> =
        try {
            val response = block()
            if (response.isSuccessful) {
                response.body()?.let { Result.success(it) }
                    ?: Result.failure(IllegalStateException("Empty server response"))
            } else {
                Result.failure(HttpException(response))
            }
        } catch (error: kotlinx.coroutines.CancellationException) {
            throw error
        } catch (error: Exception) {
            Result.failure(error)
        }
}
