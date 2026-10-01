"""Media path helpers + post-id generation.

Moved here from app.py. `generate_post_id()` reads the posts collection, so the
DB handle is resolved *inside* the function: connect_db() runs in app.py, and
importing this module must never open a connection.

`normalize_media_path()` asks the selected media provider for a browser-usable
URL, so a `/media/...` reference stays local while a platform URL is already
absolute (both backends return remote URLs untouched).
"""
import random
import string

from src.db import Post
from src.providers import ProviderKind, get


def generate_post_id(length=8):
    posts_collection = Post._get_collection()
    while True:
        new_id = "".join(random.choices(string.ascii_letters + string.digits, k=length))
        if not posts_collection.find_one({"post_id": new_id}):
            return new_id


def normalize_media_path(ref):
    """Return a browser-usable URL for a stored media reference."""
    return get(ProviderKind.MEDIA).url(ref)
