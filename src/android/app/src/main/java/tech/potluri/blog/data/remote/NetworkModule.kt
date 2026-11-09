package tech.potluri.blog.data.remote

import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import tech.potluri.blog.BuildConfig

object NetworkModule {
    private val sessionCookieJar = object : CookieJar {
        private val cookies = mutableListOf<Cookie>()

        @Synchronized
        override fun saveFromResponse(url: HttpUrl, responseCookies: List<Cookie>) {
            cookies.removeAll { existing ->
                responseCookies.any { it.name == existing.name && it.domain == existing.domain && it.path == existing.path }
            }
            cookies.addAll(responseCookies)
        }

        @Synchronized
        override fun loadForRequest(url: HttpUrl): List<Cookie> {
            cookies.removeAll { it.expiresAt < System.currentTimeMillis() }
            return cookies.filter { it.matches(url) }
        }
    }

    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
    }

    val api: BlogApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(OkHttpClient.Builder().cookieJar(sessionCookieJar).build())
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(BlogApiService::class.java)
    }
}
