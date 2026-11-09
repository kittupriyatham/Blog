# Potluri Blog — Native Android App

Native Android client for [blog.potluri-krishna-priyatham.tech](https://blog.potluri-krishna-priyatham.tech) built using **Kotlin**, **Jetpack Compose (Material 3)**, and clean **MVVM architecture**.

Powered by the Flask REST API Blueprint (`/api/v1/posts` and `/api/v1/auth/*`) on the same backend and MongoDB Atlas database.

---

## 📱 Features

* **Feed & Articles:**
  * Toggle between **All Posts**, **Short Posts**, and **Long-form Articles**.
  * Filter posts instantly by topic tags (`#quantum`, `#algorithms`, `#posse`, etc.).
  * Real-time search by title and post content.
  * Pull-to-refresh & pagination ("Load More").
* **Rich Article & Post Reader:**
  * Dynamic block renderer supporting text paragraphs, code blocks (syntax-highlighted monospace styling), quotes, and media attachments.
  * Image loading with cross-fade animation and disk caching via **Coil** (compatible with Cloudflare R2 and CDN URLs).
* **Interactive Reactions:**
  * Animated reaction bar: 👍 Like, ❤️ Heart, 🔥 Fire, 👏 Clap, 💡 Insightful.
  * Live engagement counter updates communicating with `POST /api/v1/posts/<post_id>/react`.
* **Comments:**
  * Bottom sheet displaying post comments.
  * Submit new comments directly from the app.
* **Native Sharing:**
  * Share posts and articles to other apps via the Android native system share sheet.
* **Author Profile:**
  * Research biography, quantum computing & distributed systems domains, and one-tap external links to Google Scholar, ORCID, GitHub, and LinkedIn.
* **Adaptive Theme:**
  * Material 3 Dark / Light modes matching the website's Tailwind Indigo & Slate palette.
* **Admin access:**
  * Open the **Admin** tab to sign in with `BLOG_ADMIN_USERNAME` / `BLOG_ADMIN_PASSWORD`.
  * Use **Explore demo (demo / demo)** for the publisher demo account.
  * The app keeps the authenticated Flask session for subsequent API requests.

---

## 🛠 Tech Stack & Architecture

* **UI Toolkit:** Jetpack Compose + Material 3 (`androidx.compose.material3`)
* **Navigation:** Navigation Compose (`androidx.navigation:navigation-compose`)
* **Architecture:** Clean MVVM (`ViewModel`, `StateFlow`, Kotlin Coroutines)
* **Networking:** Retrofit 2 + OkHttp 4
* **Serialization:** Kotlinx Serialization (`kotlinx-serialization-json`)
* **Image Loading:** Coil Compose (`io.coil-kt:coil-compose`)

---

## 📂 Project Structure

```
src/android/
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       └── java/tech/potluri/blog/
│           ├── MainActivity.kt               # Root Activity with Edge-to-Edge Compose NavHost
│           ├── BlogApplication.kt           # Application class
│           ├── data/
│           │   ├── model/                   # Kotlinx Serializable models (Post, Comment, Block, Author)
│           │   ├── remote/                  # Retrofit interface (BlogApiService) & NetworkModule
│           │   └── repository/              # BlogRepository (data fetching & coroutines)
│           └── ui/
│               ├── theme/                   # Material 3 Color, Type, and Theme
│               ├── components/              # PostCard, ReactionRow, BlockRenderer, CommentSheet, TagChipRow
│               ├── navigation/              # Screen definitions
│               ├── feed/                    # FeedScreen & FeedViewModel
│               ├── detail/                  # DetailScreen & DetailViewModel
│               └── author/                  # AuthorScreen & AuthorViewModel
├── build.gradle.kts
├── settings.gradle.kts
└── gradlew
```

---

## 🚀 Getting Started

### 1. Open in Android Studio
1. Launch **Android Studio** (Hedgehog or newer recommended).
2. Choose **Open** and select the `src/android` directory.
3. Allow Gradle to sync dependencies.

### 2. Configure Backend URL
By default, the app is configured to communicate with the live production backend:
```kotlin
// app/build.gradle.kts
buildConfigField("String", "BASE_URL", "\"https://blog.potluri-krishna-priyatham.tech/\"")
```

If you are running the backend locally on your computer:
* Android Emulator loopback: `http://10.0.2.2:5000/`
* Physical device on same Wi-Fi: `http://<your-lan-ip>:5000/`

### 3. Run the App
Select an Android Virtual Device (API 24+) or connect a physical device via USB, then click **Run 'app'** (`Shift + F10`).
