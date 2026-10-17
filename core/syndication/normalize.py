"""Asset and HTML/Markdown normalization utilities for multi-platform POSSE syndication.

Prepares blog content for syndication to platforms such as Medium, Dev.to, and Hashnode.
Rewrites relative image URLs, hyperlinks, and media paths into fully qualified absolute URLs
using the production domain or configured base URL, and provides markdown/HTML conversions
with attribution links for canonical SEO syndication.
"""
import os
import re
from urllib.parse import urljoin, urlparse

from markupsafe import escape


_IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc=["\'])([^"\']+)(["\'])', re.IGNORECASE)
_A_HREF_RE = re.compile(r'(<a\b[^>]*?\bhref=["\'])([^"\']+)(["\'])', re.IGNORECASE)
_VIDEO_SRC_RE = re.compile(r'(<(?:video|source)\b[^>]*?\bsrc=["\'])([^"\']+)(["\'])', re.IGNORECASE)

_MD_IMG_RE = re.compile(r'(!\[.*?\]\()([^\s\)]+)(\))')
_MD_LINK_RE = re.compile(r'(\[.*?\]\()([^\s\)]+)(\))')


def to_absolute_url(url: str, base_url: str) -> str:
    """Convert a relative or root-relative URL to an absolute URL using base_url.

    Leaves absolute http://, https://, mailto:, and anchor # links untouched.
    """
    if not url:
        return ""
    clean = url.strip()
    if clean.startswith(("http://", "https://", "mailto:", "tel:", "#", "data:")):
        return clean
    if not base_url:
        return clean
    return urljoin(base_url.rstrip("/") + "/", clean.lstrip("/"))


def normalize_html_assets(html_content: str, base_url: str) -> str:
    """Rewrite relative <img> src, <video>/<source> src, and <a> href attributes to absolute URLs."""
    if not html_content or not base_url:
        return html_content or ""

    def _replace_src(match):
        prefix, src, suffix = match.groups()
        return f"{prefix}{to_absolute_url(src, base_url)}{suffix}"

    def _replace_href(match):
        prefix, href, suffix = match.groups()
        return f"{prefix}{to_absolute_url(href, base_url)}{suffix}"

    res = _IMG_SRC_RE.sub(_replace_src, html_content)
    res = _VIDEO_SRC_RE.sub(_replace_src, res)
    res = _A_HREF_RE.sub(_replace_href, res)
    return res


def normalize_markdown_assets(markdown_content: str, base_url: str) -> str:
    """Rewrite relative Markdown images ![alt](/path) and links [text](/path) to absolute URLs."""
    if not markdown_content or not base_url:
        return markdown_content or ""

    def _replace_md_img(match):
        prefix, src, suffix = match.groups()
        return f"{prefix}{to_absolute_url(src, base_url)}{suffix}"

    def _replace_md_link(match):
        prefix, href, suffix = match.groups()
        return f"{prefix}{to_absolute_url(href, base_url)}{suffix}"

    res = _MD_IMG_RE.sub(_replace_md_img, markdown_content)
    res = _MD_LINK_RE.sub(_replace_md_link, res)
    return res


def build_article_html(doc: dict, base_url: str, canonical_url: str = "") -> str:
    """Build complete, cleaned HTML representation for long-form article syndication.

    All relative images and media are rewritten to absolute URLs.
    Includes an optional bottom canonical attribution link.
    """
    title = (doc or {}).get("title", "").strip() or "Untitled"
    body_parts = []

    # If there is a cover image, include it as leading figure
    cover = (doc or {}).get("cover_image")
    if cover:
        abs_cover = to_absolute_url(cover, base_url)
        body_parts.append(f'<figure><img src="{escape(abs_cover)}" alt="{escape(title)}"></figure>')

    for block in (doc or {}).get("blocks", []) or []:
        btype = block.get("type")
        if btype == "text":
            content = block.get("content", "")
            # Split into paragraphs or preserve markdown lines
            paras = content.split("\n\n")
            for p in paras:
                p_clean = p.strip()
                if not p_clean:
                    continue
                # If block has markdown headers or code fences, format accordingly
                if p_clean.startswith("```"):
                    body_parts.append(f"<pre><code>{escape(p_clean.strip('`'))}</code></pre>")
                elif p_clean.startswith("#"):
                    m = re.match(r"^(#{1,6})\s+(.*)$", p_clean)
                    if m:
                        level = len(m.group(1))
                        body_parts.append(f"<h{level}>{escape(m.group(2))}</h{level}>")
                    else:
                        body_parts.append(f"<p>{escape(p_clean)}</p>")
                elif p_clean.startswith(">"):
                    quote_text = p_clean.lstrip("> ").strip()
                    body_parts.append(f"<blockquote><p>{escape(quote_text)}</p></blockquote>")
                else:
                    body_parts.append(f"<p>{escape(p_clean)}</p>")
        elif btype == "media":
            for path in block.get("media_paths", []) or []:
                abs_path = to_absolute_url(path, base_url)
                ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
                if ext in {"png", "jpg", "jpeg", "gif", "webp", "bmp", "avif", "svg"}:
                    body_parts.append(f'<figure><img src="{escape(abs_path)}" alt=""></figure>')
                elif ext in {"mp4", "webm", "ogg", "mov", "avi", "mkv"}:
                    body_parts.append(f'<figure><video controls src="{escape(abs_path)}"></video></figure>')
                else:
                    body_parts.append(f'<p><a href="{escape(abs_path)}">Download attachment ({escape(ext.upper())})</a></p>')

    if canonical_url:
        body_parts.append(
            f'<hr><p><em>Originally published at <a href="{escape(canonical_url)}" target="_blank" rel="noopener noreferrer">{escape(canonical_url)}</a></em></p>'
        )

    html = "\n".join(body_parts)
    return normalize_html_assets(html, base_url)


def build_article_markdown(doc: dict, base_url: str, canonical_url: str = "") -> str:
    """Build clean Markdown representation of the article with absolute asset links."""
    title = (doc or {}).get("title", "").strip() or "Untitled"
    md_parts = [f"# {title}\n"]

    cover = (doc or {}).get("cover_image")
    if cover:
        abs_cover = to_absolute_url(cover, base_url)
        md_parts.append(f"![{title}]({abs_cover})\n")

    for block in (doc or {}).get("blocks", []) or []:
        btype = block.get("type")
        if btype == "text":
            content = block.get("content", "")
            if content.strip():
                md_parts.append(normalize_markdown_assets(content, base_url) + "\n")
        elif btype == "media":
            for path in block.get("media_paths", []) or []:
                abs_path = to_absolute_url(path, base_url)
                ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
                if ext in {"png", "jpg", "jpeg", "gif", "webp", "bmp", "avif", "svg"}:
                    md_parts.append(f"![]({abs_path})\n")
                else:
                    md_parts.append(f"[{path}]({abs_path})\n")

    if canonical_url:
        md_parts.append(f"\n---\n*Originally published at [{canonical_url}]({canonical_url})*")

    return "\n\n".join(md_parts)
