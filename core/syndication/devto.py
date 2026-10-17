"""Dev.to (Forem) API syndicator adapter.

Publishes blog articles directly to Dev.to using their REST API v1.
Requires DEVTO_API_KEY environment variable.
Documentation: https://developers.forem.com/api/v1#tag/articles/operation/createArticle
"""
import json
import os
import urllib.error
import urllib.request

from .base import CheckResult, SyndicationError, SyndicationResult, Syndicator
from .normalize import build_article_markdown


class DevtoSyndicator(Syndicator):
    id = "devto"
    label = "Dev.to"

    def _api_key(self) -> str:
        return os.environ.get("DEVTO_API_KEY", "").strip()

    def is_configured(self) -> bool:
        return bool(self._api_key())

    def text_limit(self) -> int | None:
        return None

    def check(self) -> CheckResult:
        key = self._api_key()
        if not key:
            return {"ok": False, "detail": "DEVTO_API_KEY is not set."}
        req = urllib.request.Request(
            "https://dev.to/api/users/me",
            headers={"api-key": key, "User-Agent": "MyBlog-Syndicator/1.0"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                username = data.get("username", "user")
                return {"ok": True, "detail": f"Connected as @{username}."}
        except Exception as e:
            return {"ok": False, "detail": f"Dev.to check failed: {e}"}

    def publish_detailed(
        self, text: str, url: str, media: list[str] | None = None, doc: dict | None = None
    ) -> SyndicationResult:
        key = self._api_key()
        if not key:
            raise SyndicationError("Dev.to is not configured (missing DEVTO_API_KEY).")
        if not doc:
            raise SyndicationError("Dev.to syndication requires the full article document.")

        title = doc.get("title", "").strip() or "Untitled Article"
        base_url = os.environ.get("SITE_URL", "").strip().rstrip("/")
        markdown_body = build_article_markdown(doc, base_url, canonical_url=url)

        tags = [t.lower().replace(" ", "") for t in (doc.get("tags") or [])][:4]
        # Dev.to tags cannot contain special chars
        tags = [t for t in tags if t.isalnum()]

        payload = {
            "article": {
                "title": title,
                "body_markdown": markdown_body,
                "published": True,
                "canonical_url": url,
                "tags": tags,
            }
        }
        cover = doc.get("cover_image")
        if cover:
            from .normalize import to_absolute_url
            payload["article"]["main_image"] = to_absolute_url(cover, base_url)

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://dev.to/api/articles",
            data=data,
            headers={
                "api-key": key,
                "Content-Type": "application/json",
                "User-Agent": "MyBlog-Syndicator/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                published_url = res.get("url") or res.get("canonical_url")
                remote_id = str(res.get("id")) if res.get("id") else None
                return {"url": published_url, "remote_id": remote_id}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise SyndicationError(f"Dev.to publish failed ({e.code}): {err_body[:300]}")
        except Exception as e:
            raise SyndicationError(f"Dev.to publish failed: {e}")
