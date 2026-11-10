package tech.potluri.blog.ui.theme

import android.app.Activity
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// 1. Light Mode: Editorial Alabaster & Crisp Indigo
private val LightColorScheme = lightColorScheme(
    primary = Brand600,
    onPrimary = Color.White,
    primaryContainer = Brand100,
    onPrimaryContainer = Brand800,
    secondary = AccentViolet,
    onSecondary = Color.White,
    secondaryContainer = Brand50,
    onSecondaryContainer = Brand700,
    tertiary = AccentCyan,
    background = Slate50,
    surface = Color.White,
    surfaceVariant = Slate100,
    onBackground = Slate900,
    onSurface = Slate900,
    onSurfaceVariant = Slate600,
    outline = Slate200,
    outlineVariant = Slate200
)

// 2. Dark Mode: Deep Obsidian Slate (slate-950 / slate-900 / slate-800)
private val DarkColorScheme = darkColorScheme(
    primary = Brand400,
    onPrimary = Color.White,
    primaryContainer = Brand700,
    onPrimaryContainer = Color.White,
    secondary = AccentViolet,
    onSecondary = Color.White,
    secondaryContainer = Slate800,
    onSecondaryContainer = Slate100,
    tertiary = AccentCyan,
    background = Slate950,
    surface = Slate900,
    surfaceVariant = Slate800,
    onBackground = Slate50,
    onSurface = Slate50,
    onSurfaceVariant = Slate300,
    outline = Slate700,
    outlineVariant = Slate800
)

// 3. Night Mode: Pure OLED/AMOLED Pitch Black (#000000 background & high-contrast icons/borders)
private val NightColorScheme = darkColorScheme(
    primary = Brand400,
    onPrimary = Color.White,
    primaryContainer = Brand700,
    onPrimaryContainer = Color.White,
    secondary = AccentViolet,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFF1E293B),
    onSecondaryContainer = Color(0xFFF1F5F9),
    tertiary = AccentCyan,
    background = Color(0xFF000000),
    surface = Color(0xFF0A0A0C),
    surfaceVariant = Color(0xFF1E293B),
    onBackground = Color(0xFFF8FAFC),
    onSurface = Color(0xFFF8FAFC),
    onSurfaceVariant = Color(0xFFE2E8F0),
    outline = Color(0xFF334155),
    outlineVariant = Color(0xFF1E293B)
)

@Composable
fun BlogTheme(
    themeMode: AppThemeMode = AppThemeMode.DARK,
    content: @Composable () -> Unit
) {
    val colorScheme: ColorScheme = when (themeMode) {
        AppThemeMode.LIGHT -> LightColorScheme
        AppThemeMode.DARK -> DarkColorScheme
        AppThemeMode.NIGHT -> NightColorScheme
    }

    val view = LocalView.current
    if (!view.isInEditMode) {
        val isLight = themeMode == AppThemeMode.LIGHT
        SideEffect {
            val context = view.context
            if (context is Activity) {
                val window = context.window
                window.statusBarColor = colorScheme.background.toArgb()
                window.navigationBarColor = colorScheme.surface.toArgb()
                val controller = WindowCompat.getInsetsController(window, view)
                controller.isAppearanceLightStatusBars = isLight
                controller.isAppearanceLightNavigationBars = isLight
            }
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
