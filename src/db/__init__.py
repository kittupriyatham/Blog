"""MongoEngine connection + schema bootstrap, delegated to the database provider.

`connect_db()` and `ensure_schema()` are the same functions app.py has always
called; they now ask the selected database provider (src/providers) to do the
work - a local mongod at mongodb://127.0.0.1:27017/blog_db by default, or any
MongoDB-compatible URL (`MONGO_URI`) when `DB_BACKEND=cloud`.

Any mongod works - local, Docker, Atlas, DocumentDB, Cosmos-Mongo. No cloud
service is required.

The provider imports live *inside* the functions: importing this package must
never connect, and must never cycle with src.providers (which reaches back here
only lazily, to bootstrap the models' indexes).
"""
from src.providers.base import DEFAULT_DB  # re-exported (the default database name)


def connect_db():
    """Connect MongoEngine to MongoDB. Returns the URI in use.

    Idempotent: a 2nd call in the same process returns the existing connection
    (app startup and any other importer may both call it).
    """
    from src.providers import ProviderKind, get

    return get(ProviderKind.DATABASE).connect()


def ensure_schema():
    """Create collections + indexes (idempotent - replaces dbinit.py).

    The models own the schema; the provider re-runs `ensure_indexes()` for each
    of them. Any externally-managed index that differs from the model is left in
    place (the conflict is caught and skipped) rather than dropping production
    data.
    """
    from src.providers import ProviderKind, get

    get(ProviderKind.DATABASE).ensure_schema()


from .models import AnalyticsEvent, Comment, Post  # re-export for app.py

__all__ = ["connect_db", "ensure_schema", "DEFAULT_DB", "Post", "Comment", "AnalyticsEvent"]
