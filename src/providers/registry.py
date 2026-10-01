"""Backend registration + config-driven selection + instance cache.

Layer 1 of the provider layer: `get(kind)` answers "which backend serves this
kind right now?". Selection for kind K, in order:

    1. the `<K>_BACKEND` env var   (MEDIA_BACKEND / DB_BACKEND)
    2. `DEFAULT_BACKEND`           (src/config; default "local")
    3. "local"

Two backends exist per kind - `local` and `cloud` - and each is registered as a
factory, so a backend module is only imported when the layer loads, never by the
app. `get()` caches the built instance per (kind, name); `reset()` clears the
cache (tests, or deliberately switching backend inside one process).
"""
import os

from .base import ProviderError, ProviderKind, Provider

# kind -> {backend name: zero-arg factory}
_FACTORIES: dict = {}
# (kind, name) -> built provider instance
_INSTANCES: dict = {}

# The per-kind override variable. MEDIA_BACKEND / DB_BACKEND.
_ENV_BACKEND = {
    ProviderKind.MEDIA: "MEDIA_BACKEND",
    ProviderKind.DATABASE: "DB_BACKEND",
}

_FALLBACK_BACKEND = "local"


def as_kind(kind):
    """Coerce `kind` (a ProviderKind or its string value) to a ProviderKind."""
    if isinstance(kind, ProviderKind):
        return kind
    try:
        return ProviderKind(str(kind).strip().lower())
    except ValueError:
        raise ProviderError("Unknown provider kind %r (expected one of: %s)"
                            % (kind, ", ".join(k.value for k in ProviderKind)))


def register(kind, name, factory):
    """Register `factory` (zero-arg callable) as backend `name` for `kind`."""
    kind = as_kind(kind)
    name = (name or "").strip().lower()
    if not name:
        raise ProviderError("A backend needs a name.")
    if not callable(factory):
        raise ProviderError("A backend factory must be callable (got %r)." % (factory,))
    _FACTORIES.setdefault(kind, {})[name] = factory
    _INSTANCES.pop((kind, name), None)
    return factory


def available(kind):
    """Registered backend names for `kind`, sorted."""
    return sorted(_FACTORIES.get(as_kind(kind), {}))


def selected_name(kind, override=None):
    """Resolve which backend name serves `kind` (see module docstring)."""
    kind = as_kind(kind)
    name = (override or "").strip() if override else ""
    if not name:
        name = os.environ.get(_ENV_BACKEND[kind], "").strip()
    if not name:
        from src.config import DEFAULT_BACKEND  # lazy: keep the import cycle-free
        name = (DEFAULT_BACKEND or "").strip() or _FALLBACK_BACKEND
    name = name.lower()
    if name not in _FACTORIES.get(kind, {}):
        raise ProviderError("Unknown %s backend %r (available: %s)"
                            % (kind.value, name, ", ".join(available(kind))))
    return name


def get(kind, override=None):
    """Return the provider serving `kind` (built once per kind+name).

    `override` forces a backend (an explicit "local"/"cloud") and bypasses env
    selection, which is handy in tests and in the admin tooling.
    """
    kind = as_kind(kind)
    name = selected_name(kind, override)
    instance = _INSTANCES.get((kind, name))
    if instance is None:
        instance = _FACTORIES[kind][name]()
        if not isinstance(instance, Provider):
            raise ProviderError("Backend %r for %s did not build a Provider (got %r)."
                                % (name, kind.value, instance))
        _INSTANCES[(kind, name)] = instance
    return instance


def reset():
    """Forget cached instances (the next `get()` rebuilds them)."""
    _INSTANCES.clear()


def _register_builtins():
    """Register the two backends per kind: local (filesystem/mongod) + cloud."""
    from .local import LocalDatabaseProvider, LocalMediaProvider
    from .cloud import CloudDatabaseProvider, CloudMediaProvider

    register(ProviderKind.MEDIA, "local", LocalMediaProvider)
    register(ProviderKind.MEDIA, "cloud", CloudMediaProvider)
    register(ProviderKind.DATABASE, "local", LocalDatabaseProvider)
    register(ProviderKind.DATABASE, "cloud", CloudDatabaseProvider)


_register_builtins()


__all__ = ["register", "get", "available", "selected_name", "as_kind", "reset"]
