"""The `local` backend: the filesystem + a local mongod.

Both defaults reproduce the app's pre-provider behaviour exactly:

* media is written to `media/` and referenced as `/media/<name>` (served by the
  `serve_media` route in app.py);
* the database is a local mongod at `mongodb://127.0.0.1:27017/blog_db` - or
  `MONGO_URI` when one is set (a set MONGO_URI always wins, as before).
"""
import os

from mongoengine import connect

from src.config import MEDIA_FOLDER, MONGO_URI

from .base import DatabaseProvider, MediaProvider, DEFAULT_DB, ensure_model_indexes, uri_with_db

# Where a local mongod is expected when MONGO_URI is unset.
LOCAL_MONGO_URI = "mongodb://127.0.0.1:27017/" + DEFAULT_DB


def _bare_name(ref) -> str:
    """The stored filename behind a reference (`/media/x.png` -> `x.png`)."""
    return str(ref or "").replace("/media/", "").lstrip("/")


def _local_url(name) -> str:
    return "/media/" + _bare_name(name)


class LocalMediaProvider(MediaProvider):
    """Media on disk under MEDIA_FOLDER, referenced as `/media/<name>`."""

    name = "local"

    def __init__(self):
        self.folder = MEDIA_FOLDER
        os.makedirs(self.folder, exist_ok=True)

    def save(self, file, stem, taken) -> str:
        # Naming is provider-agnostic, so it stays in src/media/uploads.py and is
        # imported lazily here (that module imports this package).
        from src.media.uploads import _ext_of, _unique_name

        saved_name = _unique_name(stem, _ext_of(file.filename), taken)
        file.save(os.path.join(self.folder, saved_name))
        return _local_url(saved_name)

    def url(self, ref) -> str:
        if not ref:
            return ref
        text = str(ref)
        if text.startswith("http://") or text.startswith("https://"):
            return text
        return _local_url(text)

    def exists(self, name) -> bool:
        return os.path.isfile(os.path.join(self.folder, _bare_name(name)))

    def delete(self, name) -> None:
        try:
            os.remove(os.path.join(self.folder, _bare_name(name)))
        except FileNotFoundError:
            pass

    def health(self) -> bool:
        return os.path.isdir(self.folder)


class LocalDatabaseProvider(DatabaseProvider):
    """MongoEngine against a local mongod (or MONGO_URI when set)."""

    name = "local"

    def __init__(self):
        self._uri = None

    def connect(self) -> str:
        if self._uri:  # idempotent: app startup and any other importer may call
            return self._uri
        uri = (MONGO_URI or "").strip()
        if uri:
            uri = uri_with_db(uri)
        else:
            uri = LOCAL_MONGO_URI
            print("[startup] No MONGO_URI set - using local mongod at %s. "
                  "Start one with `docker run -d -p 27017:27017 mongo`, or set MONGO_URI."
                  % uri)
        connect(host=uri)
        self._uri = uri
        return uri

    def ensure_schema(self) -> None:
        ensure_model_indexes()

    def health(self) -> bool:
        # Cheap: a local mongod needs no credentials, so having a target is the
        # only thing we can assert without opening a socket.
        return bool(self._uri or (MONGO_URI or "").strip() or LOCAL_MONGO_URI)


__all__ = ["LocalMediaProvider", "LocalDatabaseProvider", "LOCAL_MONGO_URI"]
