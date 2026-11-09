package tech.potluri.blog.ui.components

import android.text.Spanned
import android.widget.TextView
import io.noties.markwon.Markwon
import io.noties.markwon.core.spans.LinkSpan
import io.noties.markwon.core.spans.StrongEmphasisSpan
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28])
class MarkdownContentTest {
    @Test
    fun rendersMarkdownAndUpdatesExistingView() {
        val context = RuntimeEnvironment.getApplication()
        val view = TextView(context)
        val markwon = Markwon.create(context)
        setMarkdownContent(view, markwon, "Hello **bold** and [link](https://example.com)")

        val styled = view.text as Spanned
        assertEquals("Hello bold and link", styled.toString())
        val bold = styled.getSpans(0, styled.length, StrongEmphasisSpan::class.java).single()
        assertEquals("bold", styled.subSequence(styled.getSpanStart(bold), styled.getSpanEnd(bold)).toString())
        assertEquals(1, styled.getSpans(0, styled.length, LinkSpan::class.java).size)

        setMarkdownContent(view, markwon, "Plain \\*text\\*")
        assertEquals("Plain *text*", view.text.toString())
        val updated = view.text as Spanned
        assertTrue(updated.getSpans(0, updated.length, StrongEmphasisSpan::class.java).isEmpty())
        assertTrue(updated.getSpans(0, updated.length, LinkSpan::class.java).isEmpty())
    }
}
