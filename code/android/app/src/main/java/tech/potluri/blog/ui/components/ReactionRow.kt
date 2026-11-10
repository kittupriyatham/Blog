package tech.potluri.blog.ui.components

import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import tech.potluri.blog.data.model.ReactionCounts

@Composable
fun ReactionRow(
    reactions: ReactionCounts,
    onReact: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        ReactionButton("👍", reactions.like) { onReact("like") }
        ReactionButton("❤️", reactions.heart) { onReact("heart") }
        ReactionButton("🔥", reactions.fire) { onReact("fire") }
        ReactionButton("👏", reactions.clap) { onReact("clap") }
        ReactionButton("💡", reactions.insightful) { onReact("insightful") }
    }
}

@Composable
private fun ReactionButton(
    emoji: String,
    count: Int,
    onClick: () -> Unit
) {
    var isClicked by remember { mutableStateOf(false) }
    val scale by animateFloatAsState(
        targetValue = if (isClicked) 1.22f else 1.0f,
        animationSpec = spring(
            dampingRatio = Spring.DampingRatioMediumBouncy,
            stiffness = Spring.StiffnessLow
        ),
        label = "reaction_scale"
    )
    val active = count > 0 || isClicked

    Surface(
        shape = RoundedCornerShape(50),
        color = if (active)
            MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f)
        else
            MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
        border = BorderStroke(
            width = 0.75.dp,
            color = if (active)
                MaterialTheme.colorScheme.primary.copy(alpha = 0.45f)
            else
                MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f)
        ),
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .clickable {
                isClicked = true
                onClick()
            }
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 9.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = emoji,
                fontSize = 14.sp,
                modifier = Modifier.scale(scale)
            )
            if (count > 0) {
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = count.toString(),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = if (active)
                        MaterialTheme.colorScheme.primary
                    else
                        MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
