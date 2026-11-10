package tech.potluri.blog.ui.components

import android.util.TypedValue
import android.widget.TextView
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.PictureAsPdf
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import coil.compose.AsyncImage
import coil.request.ImageRequest
import io.noties.markwon.Markwon
import tech.potluri.blog.data.model.BlockItem
import tech.potluri.blog.ui.theme.Slate800
import tech.potluri.blog.ui.theme.Slate900

internal fun setMarkdownContent(view: TextView, markwon: Markwon, content: String) {
    markwon.setMarkdown(view, content)
}

@Composable
fun BlockRenderer(
    block: BlockItem,
    modifier: Modifier = Modifier
) {
    when (block.type) {
        "text" -> {
            val content = block.content ?: ""
            if (content.isNotBlank()) {
                val context = LocalContext.current
                val markwon = remember(context) { Markwon.create(context) }
                val textColor = MaterialTheme.colorScheme.onBackground.toArgb()
                val fontSize = MaterialTheme.typography.bodyLarge.fontSize.value
                AndroidView(
                    factory = { TextView(it) },
                    modifier = modifier.padding(vertical = 6.dp),
                    update = { textView ->
                        textView.setTextColor(textColor)
                        textView.setTextSize(TypedValue.COMPLEX_UNIT_SP, fontSize)
                        setMarkdownContent(textView, markwon, content)
                    }
                )
            }
        }

        "code" -> {
            Column(
                modifier = modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(Slate900)
            ) {
                if (!block.language.isNullOrBlank()) {
                    Text(
                        text = block.language.uppercase(),
                        color = Color.LightGray,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                    )
                }
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(Slate800)
                        .horizontalScroll(rememberScrollState())
                        .padding(14.dp)
                ) {
                    Text(
                        text = block.content ?: "",
                        color = Color(0xFFE2E8F0),
                        fontSize = 13.sp,
                        fontFamily = FontFamily.Monospace,
                        lineHeight = 20.sp
                    )
                }
            }
        }

        "media" -> {
            val context = LocalContext.current
            block.media_paths.forEach { path ->
                val fullUrl = if (path.startsWith("http")) path else "https://blog.potluri-krishna-priyatham.tech$path"
                val ext = path.substringAfterLast(".", "").lowercase()
                val isImage = ext in listOf("png", "jpg", "jpeg", "gif", "webp")

                Column(modifier = modifier.padding(vertical = 8.dp)) {
                    if (isImage) {
                        AsyncImage(
                            model = ImageRequest.Builder(context)
                                .data(fullUrl)
                                .crossfade(true)
                                .build(),
                            contentDescription = block.caption,
                            contentScale = ContentScale.FillWidth,
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                        )
                    } else {
                        // Media file attachment card (Audio, Video, PDF, Docs)
                        androidx.compose.material3.Surface(
                            onClick = {
                                val intent = android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(fullUrl))
                                context.startActivity(intent)
                            },
                            shape = RoundedCornerShape(12.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Row(
                                modifier = Modifier.padding(14.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                androidx.compose.material3.Icon(
                                    imageVector = when (ext) {
                                        "mp4", "webm", "ogg", "mov", "avi", "mkv" -> androidx.compose.material.icons.Icons.Default.PlayArrow
                                        "mp3", "wav", "m4a", "aac", "flac" -> androidx.compose.material.icons.Icons.Default.VolumeUp
                                        "pdf" -> androidx.compose.material.icons.Icons.Default.PictureAsPdf
                                        else -> androidx.compose.material.icons.Icons.Default.AttachFile
                                    },
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.size(28.dp)
                                )
                                Spacer(modifier = Modifier.width(12.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = path.substringAfterLast("/"),
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                    Text(
                                        text = "Tap to open/download ${ext.uppercase()} file",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
                    }

                    if (!block.caption.isNullOrBlank()) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = block.caption,
                            style = MaterialTheme.typography.labelSmall,
                            fontStyle = FontStyle.Italic,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = 4.dp)
                        )
                    }
                }
            }
        }

        "quote" -> {
            Box(
                modifier = modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp)
                    .clip(RoundedCornerShape(4.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))
                    .padding(16.dp)
            ) {
                Text(
                    text = "“${block.content ?: ""}”",
                    style = MaterialTheme.typography.bodyLarge,
                    fontStyle = FontStyle.Italic,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    lineHeight = 24.sp
                )
            }
        }

        else -> {
            if (!block.content.isNullOrBlank()) {
                Text(
                    text = block.content,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = modifier.padding(vertical = 4.dp)
                )
            }
        }
    }
}
