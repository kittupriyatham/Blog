"""Content package: rich text, shared helpers, canonical URLs.

`register(app)` / `register_urls(app)` are the two wiring points app.py calls
once, at startup - everything else is re-exported for callers that want
`content.now_str()`, `content.canonical(...)`, `content.post_text_and_media(...)`.
"""
from .helpers import now_str, post_text_and_media
from .rich_text import rich_text
from .urls import canonical, syndication_link_reserve, template_urls


def register(app):
    """Install the content template filters on `app` (rich_text)."""
    app.add_template_filter(rich_text, "rich_text")


def register_urls(app):
    """Install the canonical/site_url context processor on `app`."""
    app.context_processor(template_urls)


__all__ = [
    "register",
    "register_urls",
    "rich_text",
    "now_str",
    "post_text_and_media",
    "canonical",
    "syndication_link_reserve",
    "template_urls",
]
