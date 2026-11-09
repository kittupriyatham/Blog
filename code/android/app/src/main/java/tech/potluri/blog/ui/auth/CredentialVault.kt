package tech.potluri.blog.ui.auth

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

@Serializable
data class SavedCredentialEntry(
    val username: String,
    val password: String
)

object CredentialVault {
    private const val PREF_FILE = "blog_secure_credentials"
    private const val KEY_ACCOUNTS = "saved_accounts_json"

    private val json = Json { ignoreUnknownKeys = true }

    private fun getPrefs(context: Context): SharedPreferences {
        return try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            EncryptedSharedPreferences.create(
                context,
                PREF_FILE,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) {
            context.getSharedPreferences(PREF_FILE, Context.MODE_PRIVATE)
        }
    }

    fun getSavedCredentials(context: Context): List<SavedCredentialEntry> {
        return try {
            val raw = getPrefs(context).getString(KEY_ACCOUNTS, null) ?: return emptyList()
            json.decodeFromString<List<SavedCredentialEntry>>(raw)
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun saveCredential(context: Context, username: String, password: String) {
        val cleanUser = username.trim()
        if (cleanUser.isBlank() || password.isBlank() || cleanUser.equals("demo", ignoreCase = true)) {
            return
        }
        try {
            val existing = getSavedCredentials(context).filterNot {
                it.username.equals(cleanUser, ignoreCase = true)
            }
            val updated = listOf(SavedCredentialEntry(cleanUser, password)) + existing
            getPrefs(context).edit()
                .putString(KEY_ACCOUNTS, json.encodeToString(updated))
                .apply()
        } catch (e: Exception) {
            // Ignore storage errors
        }
    }

    fun removeCredential(context: Context, username: String) {
        try {
            val updated = getSavedCredentials(context).filterNot {
                it.username.equals(username.trim(), ignoreCase = true)
            }
            getPrefs(context).edit()
                .putString(KEY_ACCOUNTS, json.encodeToString(updated))
                .apply()
        } catch (e: Exception) {
            // Ignore
        }
    }
}
