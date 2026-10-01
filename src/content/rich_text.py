"""Rich-text rendering: fenced code blocks, provider embeds, autolinks.

Moved verbatim from app.py. `rich_text` used to be installed with
`@app.template_filter("rich_text")`; it is now a plain function that
`src.content.register(app)` installs as the `rich_text` template filter.
"""
import re
import urllib.parse

from markupsafe import Markup, escape

_FENCE_RE = re.compile(r"```([\w+-]*)\n(.*?)```", re.S)
_URL_RE = re.compile(r"https?://[^\s<]+")


def _embed_html(url):
    """Return an iframe embed for known media providers, else None."""
    yt = re.match(r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([\w-]{6,})", url)
    if yt:
        return '<iframe class="w-full aspect-video rounded-xl border border-slate-200 dark:border-slate-700 my-4" src="https://www.youtube.com/embed/%s" allowfullscreen loading="lazy"></iframe>' % yt.group(1)
    vm = re.match(r"https?://(?:www\.)?vimeo\.com/(\d+)", url)
    if vm:
        return '<iframe class="w-full aspect-video rounded-xl border border-slate-200 dark:border-slate-700 my-4" src="https://player.vimeo.com/video/%s" allowfullscreen loading="lazy"></iframe>' % vm.group(1)
    sp = re.match(r"https?://open\.spotify\.com/(track|album|playlist|episode|show|artist)/([\w]+)", url)
    if sp:
        return '<iframe class="w-full rounded-xl border border-slate-200 dark:border-slate-700 my-4" height="152" src="https://open.spotify.com/embed/%s/%s" loading="lazy"></iframe>' % (sp.group(1), sp.group(2))
    sc = re.match(r"https?://(?:www\.)?soundcloud\.com/[\w-]+/[\w-]+", url)
    if sc:
        return '<iframe class="w-full rounded-xl border border-slate-200 dark:border-slate-700 my-4" height="166" scrolling="no" src="https://w.soundcloud.com/player/?url=%s" loading="lazy"></iframe>' % urllib.parse.quote(url, safe="")


def rich_text(text):
    """Render post/article text: fenced code blocks, provider embeds, autolinks."""
    if not text:
        return Markup("")
    escaped = str(escape(text))
    blocks = []

    def _fence(m):
        lang, code = m.group(1), m.group(2)
        cls = (' class="language-%s"' % lang) if lang else ""
        blocks.append('<pre class="bg-slate-900 text-slate-100 rounded-xl p-4 overflow-x-auto my-4 text-sm"><code%s>%s</code></pre>' % (cls, code))
        return "\x00%d\x00" % (len(blocks) - 1)

    escaped = _FENCE_RE.sub(_fence, escaped)

    def _url(m):
        url = m.group(0)
        return _embed_html(url) or '<a href="%s" target="_blank" rel="noopener" class="text-brand-600 dark:text-brand-400 hover:underline break-all">%s</a>' % (url, url)

    escaped = _URL_RE.sub(_url, escaped)
    escaped = re.sub(r"\x00(\d+)\x00", lambda m: blocks[int(m.group(1))], escaped)
    return Markup(escaped)
