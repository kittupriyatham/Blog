"""Rich-text rendering for post/article text blocks.

Turns the lightweight, line-oriented syntax the editors insert (see
static/js/blocks.js) into safe HTML. Nothing about the stored schema changes: a
block is still ``{"type": "text", "content": "..."}``.

The original behaviour is preserved verbatim - fenced ```` ```code``` ```` blocks,
auto-embedding of YouTube/Vimeo/Spotify/SoundCloud links and URL autolinking -
and extended with these insertable blocks:

    # Heading / ## … / ######                -> <h2>…<h6> (feeds :::toc)
    > quoted line(s)                        -> quote card
    --- / *** / ___ (on its own line)       -> divider
    :::quote … :::                          -> quote card
    :::callout{type=info|warn|success|danger|tip} … :::   callout box
    :::link https://… (body = description) :::           link-preview card
    :::table (pipe rows) … :::              -> table
    :::poll (question, then -options) … ::: -> static poll (no voting)
    :::gallery (one image URL per line) … :::-> carousel
    :::toggle Summary … :::                 -> accordion (<details>)
    :::cta https://… (body = label) … :::   -> button / call to action
    :::math (LaTeX) … :::                   -> block math
    $inline latex$                          -> inline math
    :::embed https://…                      -> provider iframe, else link card
    :::divider                              -> divider
    :::toc                                  -> table of contents
    text[^id]  +  a line "[^id]: note"      -> footnotes
    | a | b | / | --- | --- | / | 1 | 2 |   -> bare markdown pipe table

Security
--------
Every piece of user text is HTML-escaped before it reaches the output, and every
URL is passed through :func:`_safe_url` - which only accepts an ``http(s)://``
URL or a same-site ``/path`` - before it is placed in an attribute. A
``javascript:`` URL, a ``data:`` URL or an embedded ``<script>`` is therefore
neutralised and rendered as inert, escaped text. Only known-safe HTML is emitted.

Design choices
--------------
* **Link-preview cards perform no network request.** The card is built purely
  from the URL (host + path + optional description the author writes). That
  avoids an SSRF surface (the URL is user-supplied), a fetch timeout, a cache and
  sanitising fetched Open Graph tags - and it renders identically offline.
* **Math uses KaTeX from a CDN and degrades gracefully.** If the CDN is blocked
  the escaped LaTeX is still shown (styled monospace); nothing else breaks. No new
  Python dependency is added.
* **Table of contents** is derived from the headings this filter renders.
"""
import re
import urllib.parse

from markupsafe import Markup, escape

# Autolink/embed on already-escaped text. \x00 is excluded so a URL can never
# swallow one of our internal placeholder markers.
_URL_RE = re.compile(r"https?://[^\s<\x00]+")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_OPEN_RE = re.compile(r"^:::\s*([a-zA-Z][a-zA-Z0-9_-]*)\s*(.*)$")
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^([\w-]+)\]:\s*(.*)$")
_FOOTNOTE_REF_RE = re.compile(r"\[\^([\w-]+)\]")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$")
_SEP_CELL_RE = re.compile(r"^:?-{2,}:?$")
_HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_INLINE_MATH_RE = re.compile(r"\$(?!\s)([^$\n]+?)(?<!\s)\$")
_ATTR_RE = re.compile(r"\{([^}]*)\}")

# `:::` blocks that are a single line and take no `:::` terminator.
_SELF_CONTAINED = {"divider", "toc", "embed"}

# The placeholder-control bytes we use internally, stripped from user input so
# user text can never forge one.
_CTRL = ("\x00", "\x01", "\x02")

_CALLOUT_STYLES = {
    "info": ("border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-950/40 text-sky-800 dark:text-sky-200", "\u2139\ufe0f"),
    "tip": ("border-brand-200 dark:border-brand-800 bg-brand-50 dark:bg-brand-950/40 text-brand-800 dark:text-brand-200", "\U0001f4a1"),
    "success": ("border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200", "\u2705"),
    "warn": ("border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-200", "\u26a0\ufe0f"),
    "danger": ("border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-200", "\u26d4"),
}

# KaTeX (CDN) + a one-shot renderer. If the CDN is unavailable the `.rt-math`
# fallback text remains visible. `__rtMathInit` keeps it idempotent when a page
# has several text blocks that each contain math.
_KATEX_SNIPPET = (
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" crossorigin="anonymous">'
    '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" crossorigin="anonymous"></script>'
    '<script>(function(){if(window.__rtMathInit)return;window.__rtMathInit=true;'
    'function r(){if(!window.katex)return;document.querySelectorAll(".rt-math[data-tex]").forEach(function(el){'
    'try{window.katex.render(el.getAttribute("data-tex"),el,{throwOnError:false,displayMode:el.classList.contains("rt-math-block")});}catch(e){}});}'
    'if(document.readyState!=="loading"){r();}else{document.addEventListener("DOMContentLoaded",r);}})();</script>'
)

# Delegated prev/next for every `:::gallery` carousel on the page. Idempotent.
_GALLERY_SNIPPET = (
    '<script>(function(){if(window.__rtGalleryInit)return;window.__rtGalleryInit=true;'
    'document.addEventListener("click",function(e){'
    'var b=e.target.closest(".rt-gal-prev, .rt-gal-next");if(!b)return;e.preventDefault();'
    'var wrap=b.closest(".rt-gallery-wrap");var track=wrap&&wrap.querySelector(".rt-gallery");if(!track)return;'
    'var next=b.classList.contains("rt-gal-next");'
    'track.scrollBy({left:(next?1:-1)*track.clientWidth,behavior:"smooth"});});})();</script>'
)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------
def _esc(s):
    """HTML-escape ``s`` (returns a plain str of already-safe text)."""
    return str(escape(s))


def _safe_url(raw):
    """Return ``raw`` if it is an http(s) URL or a same-site ``/path``, else None.

    This is the single gate every URL passes through before it is written into an
    attribute, which is what neutralises ``javascript:``, ``data:``, ``vbscript:``
    and anything containing characters that could break out of the attribute.
    """
    u = (raw or "").strip()
    if not u or len(u) > 2000:
        return None
    # Reject anything that could escape an attribute or smuggle a scheme.
    if any(c in u for c in ("\x00", "\x01", "\x02", "<", ">", '"', "'", "`",
                            " ", "\n", "\r", "\t", "\\")):
        return None
    if u.lower().startswith(("http://", "https://")):
        return u
    if u.startswith("/") and not u.startswith("//"):
        return u
    return None


def _host_path(url):
    """Split a URL into (host, path+query) for a link-preview card."""
    if url.startswith("/"):
        return "", url
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url, ""
    path = parts.path + (("?" + parts.query) if parts.query else "")
    return parts.netloc, path


def _math_span(escaped_tex, display=False):
    """A KaTeX target whose fallback text is the escaped LaTeX itself."""
    cls = "rt-math" + (" rt-math-block" if display else "")
    return '<span class="%s" data-tex="%s">%s</span>' % (cls, escaped_tex, escaped_tex)


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


def _autolink(m):
    url = m.group(0)
    return _embed_html(url) or ('<a href="%s" target="_blank" rel="noopener" class="text-brand-600 dark:text-brand-400 hover:underline break-all">%s</a>' % (url, url))


def _inline(text):
    """Escape raw text and add autolinks/embeds + inline math.

    (Footnote references are handled in the main body only, where the set of
    defined footnotes is known.)
    """
    out = _esc(text)
    out = _URL_RE.sub(_autolink, out)
    out = _INLINE_MATH_RE.sub(lambda m: _math_span(m.group(1)), out)
    return out


def _parse_attrs(rest):
    """Split a fence's trailing text into (clean_text, {attr: value})."""
    attrs = {}
    for group in _ATTR_RE.findall(rest or ""):
        for pair in re.split(r"[\s,]+", group.strip()):
            if not pair:
                continue
            if "=" in pair:
                k, v = pair.split("=", 1)
                attrs[k.strip().lower()] = v.strip().strip('"').strip("'")
            else:
                attrs[pair.strip().lower()] = "true"
    clean = _ATTR_RE.sub("", rest or "").strip()
    return clean, attrs


def _slug(text, headings):
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"
    seen = {h[2] for h in headings}
    slug, k = base, 2
    while slug in seen:
        slug = "%s-%d" % (base, k)
        k += 1
    return slug


# ---------------------------------------------------------------------------
# Block renderers (each returns trusted HTML built from escaped pieces)
# ---------------------------------------------------------------------------
def _render_quote(body):
    return ('<blockquote class="border-l-4 border-brand-500 dark:border-brand-400 bg-slate-50 dark:bg-slate-800/60 '
            'rounded-r-xl px-4 py-3 my-4 italic text-slate-700 dark:text-slate-300">%s</blockquote>' % _inline(body))


def _render_callout(kind, body):
    style, icon = _CALLOUT_STYLES.get((kind or "info").lower(), _CALLOUT_STYLES["info"])
    return ('<div class="border rounded-xl px-4 py-3 my-4 text-sm leading-relaxed %s">'
            '<span class="mr-2" aria-hidden="true">%s</span>%s</div>' % (style, icon, _inline(body)))


def _render_link(url, body):
    safe = _safe_url(url)
    if not safe:
        return ('<div class="border border-amber-200 dark:border-amber-800 rounded-xl px-4 py-3 my-4 text-sm '
                'bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300">'
                'Link preview disabled: only http(s) URLs are allowed (%s).</div>'
                % _esc(" ".join((url or "").split())[:200]))
    host, path = _host_path(safe)
    label = host or "This site"
    title = path or safe
    desc = body.strip()
    desc_html = ('<p class="text-sm text-slate-600 dark:text-slate-300 mt-2">%s</p>' % _inline(desc)) if desc else ""
    return (
        '<a href="%s" target="_blank" rel="noopener nofollow" '
        'class="block border border-slate-200 dark:border-slate-700 rounded-xl p-4 my-4 bg-white dark:bg-slate-900 '
        'hover:border-brand-300 dark:hover:border-brand-700 hover:shadow-sm transition group">'
        '<div class="flex items-center gap-3">'
        '<div class="w-10 h-10 rounded-lg bg-gradient-to-br from-brand-500 to-blue-600 flex items-center justify-center flex-shrink-0 text-white">'
        '<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101"/><path stroke-linecap="round" stroke-linejoin="round" d="M10.172 13.828a4 4 0 005.656 0l4-4a4 4 0 10-5.656-5.656l-1.102 1.101"/></svg>'
        '</div><div class="min-w-0">'
        '<p class="text-xs uppercase tracking-wide text-brand-600 dark:text-brand-400 font-semibold truncate">%s</p>'
        '<p class="text-sm font-medium text-slate-800 dark:text-slate-100 truncate group-hover:text-brand-700 dark:group-hover:text-brand-300">%s</p>'
        '</div></div>%s</a>' % (safe, _esc(label), _esc(title), desc_html)
    )


def _is_sep_cell(cell):
    return bool(cell) and bool(_SEP_CELL_RE.match(cell))


def _split_table(rows):
    """Split pipe rows into a list of cell lists, dropping a separator row."""
    parsed = []
    for row in rows:
        row = row.strip()
        if not row:
            continue
        if row.startswith("|"):
            row = row[1:]
        if row.endswith("|"):
            row = row[:-1]
        parsed.append([c.strip() for c in row.split("|")])
    if len(parsed) >= 2 and all(_is_sep_cell(c) for c in parsed[1]):
        parsed = [parsed[0]] + parsed[2:]
    return parsed


def _render_table(rows):
    if not rows:
        return ""
    head = "".join('<th class="px-3 py-2 text-left font-semibold whitespace-nowrap">%s</th>' % _inline(c) for c in rows[0])
    body = ""
    for row in rows[1:]:
        cells = "".join('<td class="px-3 py-2 align-top">%s</td>' % _inline(c) for c in row)
        body += '<tr class="border-t border-slate-100 dark:border-slate-800">%s</tr>' % cells
    return ('<div class="my-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 whitespace-normal">'
            '<table class="w-full text-sm border-collapse text-slate-700 dark:text-slate-300">'
            '<thead class="bg-slate-50 dark:bg-slate-800/60">'
            '<tr class="text-slate-700 dark:text-slate-200">%s</tr></thead><tbody>%s</tbody></table></div>' % (head, body))


def _render_poll(body):
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    if not lines:
        return ""
    question, options = lines[0], lines[1:]
    opts = ""
    for opt in options:
        opt = re.sub(r"^[-*]\s+", "", opt)
        opts += ('<div class="flex items-center gap-3 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 my-1.5 bg-white dark:bg-slate-900">'
                 '<span class="w-4 h-4 rounded-full border-2 border-brand-500 flex-shrink-0" aria-hidden="true"></span>'
                 '<span class="text-sm text-slate-700 dark:text-slate-200">%s</span></div>' % _inline(opt))
    return ('<div class="border border-slate-200 dark:border-slate-700 rounded-xl p-4 my-4 bg-slate-50 dark:bg-slate-800/40 whitespace-normal">'
            '<p class="font-semibold text-slate-800 dark:text-slate-100 mb-3">%s'
            '<span class="ml-2 text-[10px] font-bold uppercase tracking-wide text-slate-400 dark:text-slate-500">Poll</span></p>%s'
            '<p class="text-[11px] text-slate-400 dark:text-slate-500 mt-2">Static poll - voting is not enabled.</p></div>'
            % (_inline(question), opts))


def _render_gallery(body):
    urls = [ln.strip() for ln in body.split("\n") if ln.strip()]
    imgs, count = "", 0
    for u in urls:
        safe = _safe_url(u)
        if not safe:
            continue
        count += 1
        imgs += ('<img src="%s" alt="Gallery image %d" loading="lazy" '
                 'class="h-64 w-full flex-shrink-0 snap-center object-cover rounded-xl bg-slate-100 dark:bg-slate-800 '
                 'border border-slate-200 dark:border-slate-700" />' % (safe, count))
    if not imgs:
        return ('<div class="border border-amber-200 dark:border-amber-800 rounded-xl px-4 py-3 my-4 text-sm '
                'bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300">'
                'Gallery needs at least one http(s) image URL.</div>')
    return ('<div class="my-4 rt-gallery-wrap whitespace-normal">'
            '<div class="rt-gallery flex gap-3 overflow-x-auto snap-x snap-mandatory scroll-smooth pb-2">%s</div>'
            '<div class="flex items-center justify-center gap-3 mt-2">'
            '<button type="button" class="rt-gal-prev w-8 h-8 rounded-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-500 dark:text-slate-300 hover:text-brand-600 dark:hover:text-brand-400 flex items-center justify-center" aria-label="Previous image">&#8249;</button>'
            '<span class="text-xs text-slate-400 dark:text-slate-500">%d image%s</span>'
            '<button type="button" class="rt-gal-next w-8 h-8 rounded-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-500 dark:text-slate-300 hover:text-brand-600 dark:hover:text-brand-400 flex items-center justify-center" aria-label="Next image">&#8250;</button>'
            '</div></div>' % (imgs, count, "" if count == 1 else "s"))


def _render_toggle(summary, body):
    label = _inline(summary.strip()) if summary.strip() else "Details"
    return ('<details class="group border border-slate-200 dark:border-slate-700 rounded-xl my-4 bg-white dark:bg-slate-900">'
            '<summary class="cursor-pointer list-none px-4 py-3 font-medium text-slate-800 dark:text-slate-100 flex items-center justify-between gap-3 whitespace-normal">'
            '<span>%s</span>'
            '<svg class="w-4 h-4 text-slate-400 flex-shrink-0 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>'
            '</summary>'
            '<div class="px-4 pb-4 pt-0 text-slate-600 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">%s</div></details>'
            % (label, _inline(body)))


def _render_cta(url, label):
    safe = _safe_url(url)
    text = label.strip() or (safe or "").strip() or "Learn more"
    arrow = ('<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">'
             '<path stroke-linecap="round" stroke-linejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>')
    if not safe:
        return ('<div class="my-4"><span class="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold '
                'bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-300 cursor-not-allowed">%s %s</span>'
                '<span class="ml-2 text-xs text-slate-400 dark:text-slate-500">(link disabled - only http(s) URLs are allowed)</span></div>'
                % (_inline(text), arrow))
    return ('<div class="my-4"><a href="%s" target="_blank" rel="noopener nofollow" '
            'class="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold text-white '
            'bg-gradient-to-r from-brand-600 to-blue-600 hover:from-brand-700 hover:to-blue-700 shadow-sm hover:shadow-md transition">%s %s</a></div>'
            % (safe, _inline(text), arrow))


def _render_math_block(body):
    return '<div class="my-4 text-center overflow-x-auto whitespace-normal">%s</div>' % _math_span(_esc(body.strip()), display=True)


def _render_embed(url, body):
    safe = _safe_url(url)
    if not safe:
        return _render_callout("warn", "Embed URL rejected - only http(s) URLs are allowed: %s" % (url or "").strip())
    return _embed_html(safe) or _render_link(safe, body)


def _render_toc(headings):
    if not headings:
        return ('<nav class="my-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 p-4">'
                '<p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Contents</p>'
                '<p class="text-sm text-slate-400 dark:text-slate-500 mt-1">Add headings (lines starting with #) to build the table of contents.</p></nav>')
    items = ""
    for level, text, slug in headings:
        pad = "" if level <= 1 else " style=\"padding-left:%drem\"" % ((level - 1) * 1)
        items += ('<li%s><a href="#%s" class="text-brand-600 dark:text-brand-400 hover:underline">%s</a></li>'
                  % (pad, slug, _inline(text)))
    return ('<nav class="my-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 p-4 whitespace-normal" aria-label="Table of contents">'
            '<p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">Contents</p>'
            '<ul class="space-y-1 text-sm">%s</ul></nav>' % items)


def _render_footnotes(footnotes):
    items = ""
    for fid, content in footnotes:
        items += ('<li id="fn-%s" class="text-sm text-slate-600 dark:text-slate-300">%s '
                  '<a href="#fnref-%s" class="text-brand-600 dark:text-brand-400 hover:underline" aria-label="Back to reference">&#8617;</a></li>'
                  % (fid, _inline(content), fid))
    return ('<section class="mt-6 pt-4 border-t border-slate-200 dark:border-slate-700 whitespace-normal">'
            '<p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">Footnotes</p>'
            '<ol class="space-y-1 list-decimal list-inside">%s</ol></section>' % items)


def _render_block(name, clean, attrs, body_lines):
    """Dispatch one ``:::name`` block. ``body_lines`` is its raw content lines."""
    body = "\n".join(body_lines).strip("\n")
    if name in ("quote", "blockquote"):
        return _render_quote(body or clean)
    if name in ("callout", "note"):
        return _render_callout(attrs.get("type", "info"), body)
    if name in ("link", "preview", "link-preview"):
        return _render_link(clean, body)
    if name == "table":
        return _render_table(_split_table([ln for ln in body_lines if ln.strip()]))
    if name == "poll":
        return _render_poll(body)
    if name in ("gallery", "carousel"):
        return _render_gallery(body)
    if name in ("toggle", "accordion"):
        return _render_toggle(clean, body)
    if name in ("cta", "button"):
        return _render_cta(clean, body)
    if name in ("math", "latex"):
        return _render_math_block(body)
    if name == "embed":
        return _render_embed(clean, body)
    if name in ("divider", "hr"):
        return '<hr class="border-slate-200 dark:border-slate-700 my-6">'
    # Unknown block name: render as a neutral callout rather than raw input.
    return _render_callout("info", (clean + "\n" + body).strip())


# ---------------------------------------------------------------------------
# The filter
# ---------------------------------------------------------------------------
def rich_text(text):
    """Render post/article text: code fences, embeds, autolinks and blocks."""
    if not text:
        return Markup("")

    raw = str(text).replace("\r\n", "\n").replace("\r", "\n")
    for c in _CTRL:
        raw = raw.replace(c, "")

    blocks = []          # stashed HTML, referenced by \x00N\x00 markers
    headings = []        # (level, text, slug) for :::toc
    footnotes = []       # (id, raw_content)
    footnote_seen = {}
    toc_marker = "\x02TOC\x02"

    def stash(html):
        blocks.append(html)
        return "\x00%d\x00" % (len(blocks) - 1)

    lines = raw.split("\n")
    out = []
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()

        # --- close of a stray fence: ignore it ---------------------------------
        if s == ":::":
            i += 1
            continue

        # --- fenced code ``` ---------------------------------------------------
        if s.startswith("```"):
            lang = s[3:].strip()
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip the closing fence (or step past EOF)
            cls = (' class="language-%s"' % _esc(lang)) if lang else ""
            out.append(stash('<pre class="bg-slate-900 text-slate-100 rounded-xl p-4 overflow-x-auto my-4 text-sm"><code%s>%s</code></pre>'
                             % (cls, _esc("\n".join(code_lines)))))
            continue

        # --- ::: block ---------------------------------------------------------
        m = _FENCE_OPEN_RE.match(s)
        if m:
            name = m.group(1).lower()
            clean, attrs = _parse_attrs(m.group(2).strip())
            if name == "toc":
                out.append(toc_marker)
                i += 1
                continue
            if name in _SELF_CONTAINED:
                out.append(stash(_render_block(name, clean, attrs, [])))
                i += 1
                continue
            body_lines = []
            i += 1
            while i < n and lines[i].strip() != ":::":
                body_lines.append(lines[i])
                i += 1
            i += 1  # skip the closing :::
            out.append(stash(_render_block(name, clean, attrs, body_lines)))
            continue

        # --- heading -----------------------------------------------------------
        hm = _HEADING_RE.match(s)
        if hm:
            level = min(len(hm.group(1)), 6)
            text_h = hm.group(2).strip()
            slug = _slug(text_h, headings)
            headings.append((level, text_h, slug))
            tag = "h%d" % min(level + 1, 6)  # body headings start at h2 (the title is the h1)
            size = {2: "text-2xl", 3: "text-xl", 4: "text-lg", 5: "text-base", 6: "text-sm"}[min(level + 1, 6)]
            out.append(stash('<%s id="%s" class="%s font-bold text-slate-900 dark:text-white mt-6 mb-2 scroll-mt-20 whitespace-normal">%s</%s>'
                             % (tag, slug, size, _inline(text_h), tag)))
            i += 1
            continue

        # --- footnote definition ----------------------------------------------
        fm = _FOOTNOTE_DEF_RE.match(s)
        if fm:
            fid = fm.group(1)
            if fid not in footnote_seen:
                footnote_seen[fid] = True
                footnotes.append((fid, fm.group(2)))
            i += 1
            continue

        # --- horizontal rule ---------------------------------------------------
        if _HR_RE.match(s):
            out.append(stash('<hr class="border-slate-200 dark:border-slate-700 my-6">'))
            i += 1
            continue

        # --- blockquote run (> ...) -------------------------------------------
        if s.startswith(">"):
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].lstrip(" "))
                i += 1
            out.append(stash(_render_quote("\n".join(quote))))
            continue

        # --- bare markdown pipe table -----------------------------------------
        if "|" in lines[i] and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1].strip()):
            rows = [lines[i]]
            j = i + 2
            while j < n and "|" in lines[j] and lines[j].strip():
                rows.append(lines[j])
                j += 1
            out.append(stash(_render_table(_split_table(rows))))
            i = j
            continue

        out.append(lines[i])
        i += 1

    joined = "\n".join(out)
    if toc_marker in joined:
        joined = joined.replace(toc_marker, stash(_render_toc(headings)))

    result = _esc(joined)
    result = _URL_RE.sub(_autolink, result)
    result = _INLINE_MATH_RE.sub(lambda m: _math_span(m.group(1)), result)

    def _fnref(mm):
        fid = mm.group(1)
        if fid not in footnote_seen:
            return mm.group(0)  # no such footnote: leave the literal text
        return ('<sup id="fnref-%s" class="text-brand-600 dark:text-brand-400"><a href="#fn-%s" class="hover:underline">%s</a></sup>'
                % (fid, fid, fid))

    result = _FOOTNOTE_REF_RE.sub(_fnref, result)
    result = re.sub(r"\x00(\d+)\x00", lambda mm: blocks[int(mm.group(1))], result)

    if footnotes:
        result += _render_footnotes(footnotes)
    if 'class="rt-math' in result:
        result += _KATEX_SNIPPET
    if 'class="rt-gallery' in result:
        result += _GALLERY_SNIPPET
    return Markup(result)


__all__ = ["rich_text", "_embed_html", "_safe_url"]
