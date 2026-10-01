"""Media package: uploads + media paths.

Public API is re-exported here so callers use `media.upload_to_server(...)`,
`media.generate_post_id()`, etc. Implementation lives in uploads.py / paths.py.
Storage is delegated to the selected provider (see src/providers); this package
only owns naming, authorisation, and post-id generation.
"""
from .paths import generate_post_id, normalize_media_path
from .uploads import (
    allowed_file,
    media_stem,
    upload_authorized,
    upload_to_server,
)

__all__ = [
    "allowed_file",
    "media_stem",
    "upload_authorized",
    "upload_to_server",
    "generate_post_id",
    "normalize_media_path",
]
