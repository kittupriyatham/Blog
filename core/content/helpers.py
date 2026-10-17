"""Small shared helpers used by the route bodies.

Moved here from app.py: `now_str()` (was `_now_str`) and `post_text_and_media()`.
"""
from datetime import datetime, timezone


def now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def post_text_and_media(post):
    if not post:
        return "", []
    blocks = post.get("blocks", [])
    text = "\n\n".join(b.get("content", "").strip() for b in blocks if b.get("type") == "text")
    media = [p for b in blocks if b.get("type") == "media" for p in b.get("media_paths", [])]
    return text, media
