package tech.potluri.blog.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ReactionCounts(
    val like: Int = 0,
    val heart: Int = 0,
    val fire: Int = 0,
    val clap: Int = 0,
    val insightful: Int = 0
)

@Serializable
data class BlockItem(
    val type: String = "",
    val content: String? = null,
    val language: String? = null,
    val media_paths: List<String> = emptyList(),
    val caption: String? = null
)

@Serializable
data class Syndication(
    val platform: String? = null,
    val status: String? = null,
    val url: String? = null,
    val error: String? = null,
    val synced_at: String? = null
)

@Serializable
data class EmbeddedArticle(
    val post_id: String = "",
    val type: String = "article",
    val title: String = "",
    val content: String = "",
    val cover_image: String = "",
    val timestamp: String = ""
)

@Serializable
data class Post(
    val post_id: String = "",
    val type: String = "post",
    val title: String = "",
    val content: String = "",
    val cover_image: String = "",
    val timestamp: String = "",
    val tags: List<String> = emptyList(),
    val likes: Int = 0,
    val views: Int = 0,
    val shares: Int = 0,
    val reactions: ReactionCounts = ReactionCounts(),
    val blocks: List<BlockItem> = emptyList(),
    val media_paths: List<String> = emptyList(),
    val syndications: List<Syndication> = emptyList(),
    val embedded_article: EmbeddedArticle? = null
)

@Serializable
data class Comment(
    val id: String = "",
    val post_id: String = "",
    val name: String = "Anonymous",
    val body: String = "",
    val timestamp: String = ""
)

@Serializable
data class TagItem(
    val tag: String = "",
    val count: Int = 0
)

@Serializable
data class AuthorUrls(
    val portfolio: String? = null,
    val blog: String? = null,
    val youtube: String? = null,
    val github: String? = null,
    val linkedin: String? = null
)

@Serializable
data class ScholarlyProfiles(
    val orcid_url: String? = null,
    val google_scholar: String? = null
)

@Serializable
data class AuthorInfo(
    val name: String = "",
    val role: String? = null,
    val organization: String? = null,
    val research_field: String? = null,
    val domains: List<String> = emptyList(),
    val bio_short: String? = null,
    val bio_full: String? = null,
    val urls: AuthorUrls = AuthorUrls(),
    val scholarly: ScholarlyProfiles = ScholarlyProfiles()
)

@Serializable
data class PostsResponse(
    val posts: List<Post> = emptyList(),
    val page: Int = 1,
    val per_page: Int = 10,
    val total: Int = 0,
    val total_pages: Int = 1,
    val has_next: Boolean = false,
    val has_prev: Boolean = false
)

@Serializable
data class ArticlesResponse(
    val status: String = "",
    val count: Int = 0,
    val articles: List<Post> = emptyList()
)

@Serializable
data class SyndicationPlatform(
    val id: String = "",
    val label: String = "",
    val configured: Boolean = false,
    val limit: Int? = null
)

@Serializable
data class SyndicationPlatformsResponse(
    val status: String = "",
    val kind: String = "post",
    val platforms: List<SyndicationPlatform> = emptyList()
)

@Serializable
data class MediaUploadResponse(
    val status: String = "",
    val post_id: String = "",
    val url: String = "",
    val name: String = "",
    val message: String? = null
)

@Serializable
data class PostResponse(val post: Post)

@Serializable
data class CommentsResponse(val comments: List<Comment> = emptyList())

@Serializable
data class TagsResponse(val tags: List<TagItem> = emptyList())

@Serializable
data class AuthorResponse(val author: AuthorInfo)

@Serializable
data class ReactionResponse(
    val likes: Int = 0,
    val reactions: ReactionCounts = ReactionCounts()
)

@Serializable
data class CommentResponse(val comment: Comment)

@Serializable
data class ShareResponse(val shares: Int = 0)

@Serializable
data class RecordViewResponse(
    val status: String = "",
    val post_id: String = "",
    val views: Int = 0
)

@Serializable
data class LoginRequest(
    val username: String,
    val password: String
)

@Serializable
data class AuthUser(
    val username: String = "",
    val is_demo: Boolean = false,
    val is_admin: Boolean = false
)

@Serializable
data class AuthResponse(
    val status: String = "",
    val user: AuthUser? = null,
    val message: String? = null
)

@Serializable
data class CreatePostRequest(
    val content: String,
    val title: String? = null,
    val type: String = "post",
    val tags: List<String> = emptyList(),
    val status: String = "published",
    val media_paths: List<String> = emptyList(),
    val platforms: List<String> = emptyList()
)

@Serializable
data class CreatePostResponse(
    val status: String = "",
    val message: String? = null,
    val post: Post? = null
)


