package tech.potluri.blog.ui.components

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.Public
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import tech.potluri.blog.data.model.Syndication

data class PlatformMeta(
    val name: String,
    val brandColor: Color,
    val symbol: String
)

fun getPlatformMeta(platformKey: String?): PlatformMeta {
    return when (platformKey?.lowercase()?.trim()) {
        "linkedin" -> PlatformMeta("LinkedIn", Color(0xFF0A66C2), "in")
        "twitter", "x" -> PlatformMeta("X (Twitter)", Color(0xFF1D9BF0), "𝕏")
        "medium" -> PlatformMeta("Medium", Color(0xFF00AB6C), "M")
        "youtube" -> PlatformMeta("YouTube", Color(0xFFFF0000), "▶")
        "facebook" -> PlatformMeta("Facebook", Color(0xFF1877F2), "f")
        "instagram" -> PlatformMeta("Instagram", Color(0xFFE4405F), "📷")
        "bluesky" -> PlatformMeta("Bluesky", Color(0xFF0285FF), "🦋")
        "pinterest" -> PlatformMeta("Pinterest", Color(0xFFBD081C), "P")
        else -> PlatformMeta(
            platformKey?.replaceFirstChar { it.uppercase() } ?: "External",
            Color(0xFF6366F1),
            "🔗"
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SyndicationSection(
    syndications: List<Syndication>,
    modifier: Modifier = Modifier
) {
    val postedList = syndications.filter {
        !it.url.isNullOrBlank() && (it.status == null || it.status == "posted")
    }
    if (postedList.isEmpty()) return

    val context = LocalContext.current

    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f)
        ),
        border = BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Public,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(16.dp)
                )
                Text(
                    text = "Also published on",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }
            Spacer(modifier = Modifier.height(12.dp))

            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                postedList.forEach { syn ->
                    val meta = getPlatformMeta(syn.platform)
                    Surface(
                        modifier = Modifier.clickable {
                            syn.url?.let { targetUrl ->
                                try {
                                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(targetUrl))
                                    context.startActivity(intent)
                                } catch (_: Exception) {}
                            }
                        },
                        shape = RoundedCornerShape(50),
                        color = MaterialTheme.colorScheme.surface,
                        border = BorderStroke(1.dp, meta.brandColor.copy(alpha = 0.45f)),
                        shadowElevation = 1.dp
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            Surface(
                                shape = CircleShape,
                                color = meta.brandColor.copy(alpha = 0.15f)
                            ) {
                                Text(
                                    text = meta.symbol,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Black,
                                    color = meta.brandColor,
                                    modifier = Modifier.padding(horizontal = 5.dp, vertical = 1.dp)
                                )
                            }
                            Text(
                                text = meta.name,
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.OpenInNew,
                                contentDescription = "Open in ${meta.name}",
                                tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                                modifier = Modifier.size(12.dp)
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SyndicationPills(
    syndications: List<Syndication>,
    modifier: Modifier = Modifier
) {
    val postedList = syndications.filter {
        !it.url.isNullOrBlank() && (it.status == null || it.status == "posted")
    }
    if (postedList.isEmpty()) return

    val context = LocalContext.current

    Row(
        modifier = modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Text(
            text = "Also on:",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f),
            fontWeight = FontWeight.Medium,
            fontSize = 11.sp
        )
        postedList.forEach { syn ->
            val meta = getPlatformMeta(syn.platform)
            Surface(
                modifier = Modifier.clickable {
                    syn.url?.let { targetUrl ->
                        try {
                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(targetUrl))
                            context.startActivity(intent)
                        } catch (_: Exception) {}
                    }
                },
                shape = RoundedCornerShape(50),
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                border = BorderStroke(0.5.dp, meta.brandColor.copy(alpha = 0.35f))
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text(
                        text = meta.symbol,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        color = meta.brandColor
                    )
                    Text(
                        text = meta.name,
                        style = MaterialTheme.typography.labelSmall,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }
        }
    }
}
