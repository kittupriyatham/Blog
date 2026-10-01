"""Media uploads: naming + authorisation. Storing the file is the provider's job.

Moved here from app.py. `upload_to_server()` hands the file to the selected media
provider (`src.providers.get(ProviderKind.MEDIA)`) - the filesystem `local`
backend by default, or the config-driven HTTP-upload `cloud` backend. The concrete
storage backends live in `src/providers/`.

The naming helpers stay here because they are provider-agnostic - every backend
names a file the same way (`media_<hash of the post id>.<ext>`, suffixed when the
name is already taken). Both providers call `_ext_of` / `_unique_name`.
"""
import hashlib
import os

from flask import request, session
from werkzeug.utils import secure_filename

from src.config import ALLOWED_EXTENSIONS, MEDIA_FOLDER, UPLOAD_TOKEN
from src.providers import ProviderKind, get


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_authorized() -> bool:
    """Authorise an upload: a logged-in admin, or the shared upload token.

    The token path exists so a script can POST to /upload_media without a
    browser session. Leave UPLOAD_TOKEN unset to disable it entirely.
    """
    if session.get("logged_in"):
        return True
    token = UPLOAD_TOKEN
    return bool(token) and request.headers.get("X-Upload-Token", "") == token


def media_stem(post_id: str) -> str:
    """Filename stem for a post's media: media_<hash of the post id>.

    Hashing keeps the name stable per post and independent of the id's own
    characters or length, while staying unique across posts.
    """
    return "media_" + hashlib.sha1(str(post_id).encode("utf-8")).hexdigest()[:16]


def _ext_of(filename: str) -> str:
    return os.path.splitext(secure_filename(filename or ""))[1].lower()


def _unique_name(stem: str, ext: str, taken: set, check_disk: bool = True) -> str:
    """`stem+ext`, or `stem_1+ext`, `stem_2+ext`... when that name is taken.

    Checks this request's uploads via `taken` and (for local storage) what is
    already on disk, so adding a second image to an existing post cannot
    silently overwrite the first.
    """
    n = 0
    while True:
        name = (stem if n == 0 else "%s_%d" % (stem, n)) + ext
        if name not in taken and not (check_disk and os.path.exists(os.path.join(MEDIA_FOLDER, name))):
            taken.add(name)
            return name
        n += 1


def upload_to_server(file, stem, taken):
    """Store an uploaded file with the selected media provider.

    Returns a reference (a `/media/<name>` path locally, a URL on a platform).
    """
    return get(ProviderKind.MEDIA).save(file, stem, taken)
