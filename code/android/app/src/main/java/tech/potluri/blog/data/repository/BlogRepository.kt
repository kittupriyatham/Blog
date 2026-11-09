package tech.potluri.blog.data.repository

import java.io.IOException
import retrofit2.HttpException
import tech.potluri.blog.data.model.AuthorResponse
import tech.potluri.blog.data.model.Comment
import tech.potluri.blog.data.model.Post
import tech.potluri.blog.data.model.PostsResponse
import tech.potluri.blog.data.model.ReactionCounts
import tech.potluri.blog.data.model.TagItem
import tech.potluri.blog.data.remote.BlogApiService
import tech.potluri.blog.data.remote.NetworkModule

class BlogRepository(
    private val api: BlogApiService = NetworkModule.api
) {
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

    suspend fun submitReaction(postId: String, type: String): Result<ReactionCounts> =
        request { api.react(postId, type).reactions }

    suspend fun recordShare(postId: String): Result<Int> =
        request { api.share(postId).shares }

    suspend fun fetchTags(): Result<List<TagItem>> =
        request { api.getTags().tags }

    suspend fun fetchAuthor(): Result<AuthorResponse> =
        request { api.getAuthor() }

    private suspend fun <T> request(block: suspend () -> T): Result<T> =
        try {
            Result.success(block())
        } catch (error: IOException) {
            Result.failure(error)
        } catch (error: HttpException) {
            Result.failure(error)
        }
}
