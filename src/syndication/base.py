"""Base adapter + registry for social syndication (POSSE).

Each platform is a small adapter exposing:
    id, label            -- identity
    is_configured()      -- are credentials present?
    publish(text, url)   -- post it; return the public URL of the created post
    check()              -- safe, read-only credential check (no posting)

Adapters register themselves so `app.py` can reach them by id.
"""
from typing import TypedDict


class CheckResult(TypedDict):
    ok: bool
    detail: str


class SyndicationResult(TypedDict, total=False):
    """Outcome of a publish. `url` is the public permalink; `remote_id` is the
    provider's own post id, kept so the post can be deleted/updated later."""
    url: str
    remote_id: str | None


class SyndicationError(Exception):
    pass


class Syndicator:
    """Interface for a social platform adapter."""

    id: str = ""
    label: str = ""

    def is_configured(self) -> bool:
        """Must be cheap and offline - this runs on every page render."""
        raise NotImplementedError

    def text_limit(self) -> int | None:
        """Characters this platform accepts, or None when effectively unbounded.

        Used to truncate once, to the smallest limit across the selected
        platforms, so the same text is published everywhere and no platform
        cuts it mid-sentence.
        """
        return None

    def publish(self, text: str, url: str, media: list[str] | None = None, doc: dict | None = None) -> str:
        """Post it. `media` is a list of publicly fetchable URLs; adapters that
        take text only ignore it. `doc` is the underlying document, for adapters
        that need the whole article rather than the shortened social text.
        Returns the public permalink."""
        raise NotImplementedError

    def publish_detailed(self, text: str, url: str, media: list[str] | None = None,
                         doc: dict | None = None) -> SyndicationResult:
        """Override when the provider returns an id worth persisting alongside the URL."""
        return {"url": self.publish(text, url, media, doc), "remote_id": None}

    def delete(self, identifier: str) -> None:
        raise NotImplementedError

    def check(self) -> CheckResult:
        return {"ok": self.is_configured(), "detail": ""}


_REGISTRY: dict[str, Syndicator] = {}


def register(syndicator: Syndicator) -> Syndicator:
    _REGISTRY[syndicator.id] = syndicator
    return syndicator


def get(platform_id: str) -> Syndicator | None:
    return _REGISTRY.get(platform_id)


def all_syndicators() -> list[Syndicator]:
    return list(_REGISTRY.values())
