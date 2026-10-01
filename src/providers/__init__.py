"""Provider layer: one stable interface per data kind, one backend behind it.

    from src.providers import get, ProviderKind

    media = get(ProviderKind.MEDIA)       # local | cloud   (MEDIA_BACKEND)
    db    = get(ProviderKind.DATABASE)    # local | cloud   (DB_BACKEND)

Selection is config-only (see registry.py): `<KIND>_BACKEND` env var, else
`DEFAULT_BACKEND`, else "local". `get(kind, override)` forces a backend.

The app imports this module and nothing else here; platforms plug in behind the
interfaces in base.py, so adding one never touches app.py or a route.
"""
from .base import (
    DatabaseProvider,
    MediaProvider,
    Provider,
    ProviderError,
    ProviderKind,
)
from .cloud.media import GenericHttpUploadAdapter, get_adapter, register_adapter
from .registry import available, get, register, reset, selected_name

__all__ = [
    "get",
    "ProviderKind",
    "Provider",
    "MediaProvider",
    "DatabaseProvider",
    "ProviderError",
    "register_adapter",
    "get_adapter",
    "GenericHttpUploadAdapter",
    "register",
    "available",
    "selected_name",
    "reset",
]
