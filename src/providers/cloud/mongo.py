"""The `cloud` backend's database provider: any MongoDB-compatible URL.

Atlas, DocumentDB, Cosmos-Mongo, a self-hosted replica set - they all speak the
Mongo wire protocol, so this is `mongoengine.connect(host=MONGO_URI)`. pymongo /
mongoengine are protocol clients, not cloud SDKs: no vendor library is involved,
and the same code works with every Mongo-compatible host.
"""
from mongoengine import connect

from src.config import MONGO_URI

from ..base import DatabaseProvider, ProviderError, ensure_model_indexes, uri_with_db


class CloudDatabaseProvider(DatabaseProvider):
    """A MongoDB-compatible database reached by URL (`MONGO_URI`)."""

    name = "cloud"

    def __init__(self):
        self._uri = None

    def connect(self) -> str:
        if self._uri:  # idempotent
            return self._uri
        uri = (MONGO_URI or "").strip()
        if not uri:
            raise ProviderError("DB_BACKEND=cloud needs MONGO_URI - a MongoDB-compatible "
                               "URL (e.g. mongodb+srv://user:pass@cluster/db).")
        uri = uri_with_db(uri)
        connect(host=uri)
        self._uri = uri
        return uri

    def ensure_schema(self) -> None:
        ensure_model_indexes()

    def health(self) -> bool:
        return bool((MONGO_URI or "").strip())


__all__ = ["CloudDatabaseProvider"]
