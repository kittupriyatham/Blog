"""Canonical/site URLs and the template context processor.

Moved here from app.py: `canonical()` and `syndication_link_reserve()`, plus the
old `_template_urls` context processor (now `template_urls`, installed by
`src.content.register_urls(app)`).
"""
from flask import url_for

from src import syndication
from src.config import SITE_URL


def canonical(endpoint, **values):
    """Absolute URL of a blog page, honouring SITE_URL when set."""
    if SITE_URL:
        return SITE_URL + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


def syndication_link_reserve():
    """Characters the appended canonical link will occupy in a syndicated post.

    The editor's live counter reserves this so a post that fits only without its
    link is not reported as fitting. Ids are 8 characters (generate_post_id).
    """
    if not SITE_URL or not syndication.is_public_url(SITE_URL):
        return 0
    return len("\n\n" + SITE_URL + "/post/" + "x" * 8)


def template_urls():
    """Expose canonical()/SITE_URL so templates can emit <link rel=canonical>
    and Open Graph tags - importers (Medium) and link previews need absolute
    URLs, which url_for() alone cannot build behind a tunnel/proxy."""
    return {"canonical": canonical, "site_url": SITE_URL,
            "link_reserve": syndication_link_reserve(),
            # A text card is rendered locally and uploaded by the adapter, so
            # Pillow is the only requirement - no public URL is involved.
            "text_card_available": bool(syndication.textcard.available())}
