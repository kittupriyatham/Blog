"""Social syndication (POSSE: Publish Own Site, Syndicate Elsewhere).

Pluggable platform adapters. Add a platform by dropping a module in this
package and registering it below.

Public surface used by app.py:
    available_platforms(), label_for(), get(),
    publish_to(), compose_text(), is_public_url()
"""
import ipaddress
import re
from urllib.parse import urlparse

from .base import SyndicationError, Syndicator, register, get, all_syndicators
from .linkedin import LinkedinSyndicator
from .medium import MediumSyndicator
from .socialapi import (SocialApiSyndicator, build_platforms, TEXT_CARD_PLATFORMS,
                        twitter_has_subscription)
from . import textcard
from . import rewrite

register(LinkedinSyndicator())
# Medium: no write API, and its importer cannot reach localhost, so this drives
# the editor in a browser instead (see medium.py).
register(MediumSyndicator())
# SocialAPI covers Facebook/Instagram/Threads/YouTube (and more) through one key,
# using the provider's pre-approved platform apps.
for _syndicator in build_platforms():
    register(_syndicator)


# Platforms that only make sense for long-form articles, not short posts.
# Medium imports a whole story, so it suits an article - not a one-paragraph post.
ARTICLE_ONLY = {"medium"}

# Platforms that can only take long-form content when a paid tier is present.
# X Articles are a Premium feature, so without a subscription X is not offered
# for articles at all - though it stays available for short posts.
ARTICLE_NEEDS_SUBSCRIPTION = {"twitter"}


def available_platforms(kind=None):
    """Registered platforms, optionally filtered by what is being published.

    kind="post"    drops the article-only platforms (Medium).
    kind="article" drops platforms that cannot take long-form without a paid
                   tier (X, unless TWITTER_SUBSCRIPTION is enabled).
    """
    out = []
    for s in all_syndicators():
        if kind == "post" and s.id in ARTICLE_ONLY:
            continue
        if (kind == "article" and s.id in ARTICLE_NEEDS_SUBSCRIPTION
                and not twitter_has_subscription()):
            continue
        out.append({"id": s.id, "label": s.label, "configured": s.is_configured(),
                    "limit": s.text_limit()})
    return out


def label_for(platform_id):
    s = get(platform_id)
    return s.label if s else platform_id


def publish_to(platform_id, text, url, media=None, doc=None):
    return publish_detailed_to(platform_id, text, url, media, doc)["url"]


def publish_detailed_to(platform_id, text, url, media=None, doc=None):
    s = get(platform_id)
    if not s:
        raise SyndicationError("Unknown platform: %s" % platform_id)
    if not s.is_configured():
        raise SyndicationError("%s is not configured." % s.label)
    return s.publish_detailed(text, url, media, doc)


def media_for(doc):
    """Media attached to a doc - local or remote.

    Local `/media/...` paths are included on purpose. The SocialAPI adapter
    uploads them to the media library and publishes by `media_id`, so media no
    longer has to be publicly reachable. Filtering to public URLs here used to
    mean an attached image was silently dropped, which then caused a text card
    to be generated even though the post already had a picture.

    The cover image counts too: it is a real image upload, and Instagram and
    Pinterest require at least one image to publish at all.
    """
    out = []
    for block in (doc or {}).get("blocks", []):
        if block.get("type") != "media":
            continue
        for path in block.get("media_paths", []) or []:
            if path and path not in out:
                out.append(path)
    cover = (doc or {}).get("cover_image")
    if isinstance(cover, str) and cover and cover not in out:
        out.append(cover)
    return out


def is_public_url(url):
    """True only when the URL host is a real domain - not localhost or a bare IP."""
    if not url:
        return False
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return False
    if not host or host == "localhost" or host.endswith(".local"):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return "." in host


def text_limit_for(platforms):
    """Smallest declared text limit across `platforms`; None when unbounded."""
    limits = []
    for pid in platforms or []:
        s = get(pid)
        if not s:
            continue
        lim = s.text_limit()
        if isinstance(lim, int) and lim > 0:
            limits.append(lim)
    return min(limits) if limits else None


# A sentence end is punctuation followed by whitespace or the end of the string.
# Requiring the trailing space (rather than just the punctuation) keeps "3.5" and
# "app.social-api.ai" from reading as sentence boundaries.
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")


def truncate_on_boundary(text, limit, boundary_share=0.6):
    """Cut `text` to fit `limit` without splitting a word or stranding a fragment.

    The last sentence ending inside the window wins whenever it keeps at least
    `boundary_share` of the available room; otherwise the trim falls back to the
    last line break, then the last space, so a sentence-less run-on still keeps as
    much text as possible. An ellipsis signals that the text continues.

    Sentence ends are matched on punctuation followed by whitespace, not on the
    literal ". ". Posts are written with blank lines between paragraphs, so a
    sentence ending in ".\\n" is the common case - matching only ". " skipped
    those boundaries and cut far earlier than the limit allowed.
    """
    text = text or ""
    if limit is None or len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    window = text[: limit - 1]  # leave room for the ellipsis
    floor = max(1, int((limit - 1) * boundary_share))

    # Latest sentence end at or past the floor - the most readable place to stop.
    ends = [m.end() for m in _SENTENCE_END.finditer(window) if m.end() >= floor]
    if ends:
        return window[: max(ends)].rstrip() + "\u2026"

    # No usable sentence break: keep as much as possible, on a line or word edge.
    for sep in ("\n", " "):
        idx = window.rfind(sep)
        if idx >= floor:
            return window[:idx].rstrip() + "\u2026"
    return window.rstrip() + "\u2026"


def compose_text(doc, url, platforms=None):
    """Social text = the body, plus the canonical link when the domain is public.

    Call this once per platform: the body is truncated to *that* platform's own
    limit, so a roomy platform is never cut short to satisfy a tight one. Passing
    several platforms deliberately clamps to the smallest of them, and passing
    none keeps the 3000-character default.
    """
    if doc.get("type") == "article":
        body = (doc.get("title") or "New article").strip()
    else:
        parts = [b.get("content", "").strip() for b in doc.get("blocks", []) if b.get("type") == "text"]
        body = "\n\n".join(p for p in parts if p) or "New post"

    # Textareas submit CRLF, which platforms render as a stray control character.
    body = body.replace("\r\n", "\n").replace("\r", "\n")

    suffix = ("\n\n" + url) if (url and is_public_url(url)) else ""
    limit = text_limit_for(platforms) if platforms else 3000
    if limit is None:
        return body + suffix
    room = limit - len(suffix)
    if room < 1:
        return suffix[:limit]
    if len(body) <= room:
        return body + suffix
    # Too long for this platform: rewrite the whole post down to size instead of
    # cutting it off. `room` already excludes the link, so the result fits the
    # limit including the link. Falls back to trimming when no model is available,
    # so publishing never depends on the rewrite.
    rewritten = rewrite.condense(body, room)
    if rewritten:
        return rewritten + suffix
    return truncate_on_boundary(body, room) + suffix
