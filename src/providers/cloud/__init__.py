"""The `cloud` backend (layer 2): HTTP-upload media + any Mongo-compatible DB.

Re-exported so `from src.providers.cloud import CloudMediaProvider` works without
reaching into the individual modules (the app never imports this package - the
registry does).
"""
from .media import (CloudMediaProvider, GenericHttpUploadAdapter, UploadAdapter,
                    get_adapter, register_adapter)
from .mongo import CloudDatabaseProvider

__all__ = [
    "CloudMediaProvider",
    "CloudDatabaseProvider",
    "UploadAdapter",
    "GenericHttpUploadAdapter",
    "register_adapter",
    "get_adapter",
]
