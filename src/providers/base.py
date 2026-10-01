"""The stable provider contracts.

The app talks to exactly one of these interfaces per data *kind* - `media` (file
storage) and `database` (a MongoDB document store) - so no call site ever knows
which platform, or which local fallback, is behind it. Concrete implementations
live in `local.py` (filesystem + local mongod) and `cloud/` (HTTP upload +
any MongoDB-compatible URL).

Adding a platform means adding an implementation, never touching the app.
"""
from abc import ABC, abstractmethod
from enum import Enum
from urllib.parse import urlparse


class ProviderError(RuntimeError):
    """A provider could not be selected, built, or used.

    One error type for the whole layer, so a route that ignores providers still
    sees a single, comprehensible failure instead of a vendor-specific one.
    """


class ProviderKind(str, Enum):
    """The data kinds the app asks a provider for."""

    MEDIA = "media"
    DATABASE = "database"


class Provider(ABC):
    """Common base: every provider declares its kind + name and can be probed."""

    kind: ProviderKind
    name: str = ""

    @abstractmethod
    def health(self) -> bool:
        """Cheap configuration/liveness check. Must never raise."""


class MediaProvider(Provider):
    """File storage: save a file, hand back a reference, resolve/remove it."""

    kind = ProviderKind.MEDIA

    @abstractmethod
    def save(self, file, stem, taken) -> str:
        """Store `file`, named after `stem` (+ a suffix when that name is taken).

        `taken` is the per-request set of names already handed out, so a second
        file in the same request cannot overwrite the first. Returns a reference
        (a storage name or a full URL) - `url()` turns it into a browser URL.
        """

    @abstractmethod
    def url(self, ref) -> str:
        """Browser-usable URL for a reference returned by `save()`."""

    @abstractmethod
    def exists(self, name) -> bool:
        """True when a stored object exists."""

    @abstractmethod
    def delete(self, name) -> None:
        """Remove a stored object (a no-op when it is already gone)."""


class DatabaseProvider(Provider):
    """A MongoDB document store - local mongod or any Mongo-compatible URL."""

    kind = ProviderKind.DATABASE

    @abstractmethod
    def connect(self) -> str:
        """Open the connection (idempotent) and return the target in use."""

    @abstractmethod
    def ensure_schema(self) -> None:
        """Create collections + indexes (idempotent)."""


# ---------------------------------------------------------------------------
# Shared MongoDB helpers
#
# Both database providers normalise their URI and bootstrap the schema the same
# way, so those two things live here rather than being duplicated per backend.
# ---------------------------------------------------------------------------

DEFAULT_DB = "blog_db"


def uri_with_db(uri, default_db=DEFAULT_DB):
    """Make sure a MongoDB URI carries a database name (default `blog_db`).

    Atlas/DocumentDB URLs often point at a cluster without naming the database;
    MongoEngine would then default to `test`, so the name is filled in here.
    """
    if not uri:
        return uri
    parsed = urlparse(uri)
    if not parsed.path or parsed.path == "/":
        uri = uri.rstrip("/") + "/" + default_db
    return uri


def ensure_model_indexes():
    """Create the app's collections + indexes (idempotent) - the models own the schema.

    Imported lazily: `src.db.models` must not be pulled in while the provider
    layer is still initialising, and importing it must never open a connection.
    An index conflict (an externally managed index that differs from the model)
    is caught and skipped rather than dropped - production data is never touched.
    """
    from src.db.models import AnalyticsEvent, Comment, Post
    for model in (Post, Comment, AnalyticsEvent):
        try:
            model.ensure_indexes()
        except Exception as e:  # idempotent: ignore conflicts with existing indexes
            print("[startup] ensure_indexes(%s) skipped: %s" % (model.__name__, e))


__all__ = [
    "ProviderError",
    "ProviderKind",
    "Provider",
    "MediaProvider",
    "DatabaseProvider",
    "DEFAULT_DB",
    "uri_with_db",
    "ensure_model_indexes",
]
