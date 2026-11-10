package tech.potluri.blog.data.remote

import tech.potluri.blog.data.model.ArticlesResponse
import tech.potluri.blog.data.model.AuthorResponse
import tech.potluri.blog.data.model.AuthResponse
import tech.potluri.blog.data.model.CreatePostRequest
import tech.potluri.blog.data.model.CreatePostResponse
import tech.potluri.blog.data.model.LoginRequest
import tech.potluri.blog.data.model.CommentResponse
import tech.potluri.blog.data.model.CommentsResponse
import tech.potluri.blog.data.model.MediaUploadResponse
import tech.potluri.blog.data.model.PostResponse
import tech.potluri.blog.data.model.PostsResponse
import tech.potluri.blog.data.model.ReactionResponse
import tech.potluri.blog.data.model.RecordViewResponse
import tech.potluri.blog.data.model.ShareResponse
import tech.potluri.blog.data.model.SyndicationPlatformsResponse
import tech.potluri.blog.data.model.TagsResponse
import okhttp3.MultipartBody
import retrofit2.http.Field
import retrofit2.http.Body
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.Response

interface BlogApiService {
    @POST("api/v1/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<AuthResponse>

    @POST("api/v1/auth/logout")
    suspend fun logout(): Response<AuthResponse>

    @GET("api/v1/auth/me")
    suspend fun currentUser(): Response<AuthResponse>

    @POST("api/v1/posts")
    suspend fun createPost(@Body request: CreatePostRequest): Response<CreatePostResponse>

    @Multipart
    @POST("api/v1/media")
    suspend fun uploadMedia(@Part file: MultipartBody.Part): Response<MediaUploadResponse>

    @GET("api/v1/syndication/platforms")
    suspend fun getSyndicationPlatforms(@Query("kind") kind: String = "post"): SyndicationPlatformsResponse

    @GET("api/v1/articles")
    suspend fun getArticles(): ArticlesResponse

    @GET("api/v1/posts")
    suspend fun getPosts(
        @Query("page") page: Int,
        @Query("limit") limit: Int,
        @Query("type") type: String?,
        @Query("tag") tag: String?,
        @Query("q") query: String?
    ): PostsResponse

    @GET("api/v1/posts/{postId}")
    suspend fun getPost(@Path("postId") postId: String): PostResponse

    @GET("api/v1/posts/{postId}/comments")
    suspend fun getComments(@Path("postId") postId: String): CommentsResponse

    @FormUrlEncoded
    @POST("api/v1/posts/{postId}/comments")
    suspend fun addComment(
        @Path("postId") postId: String,
        @Field("name") name: String,
        @Field("body") body: String
    ): CommentResponse

    @FormUrlEncoded
    @POST("api/v1/posts/{postId}/react")
    suspend fun react(
        @Path("postId") postId: String,
        @Field("type") type: String
    ): ReactionResponse

    @FormUrlEncoded
    @POST("api/v1/posts/{postId}/share")
    suspend fun share(
        @Path("postId") postId: String,
        @Field("platform") platform: String = "android"
    ): ShareResponse

    @POST("api/v1/posts/{postId}/view")
    suspend fun recordView(@Path("postId") postId: String): RecordViewResponse

    @GET("api/v1/tags")
    suspend fun getTags(): TagsResponse

    @GET("api/v1/author")
    suspend fun getAuthor(): AuthorResponse
}
