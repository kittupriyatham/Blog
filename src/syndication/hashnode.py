"""Hashnode GraphQL API syndicator adapter.

Publishes blog articles directly to Hashnode using their GraphQL API.
Requires HASHNODE_ACCESS_TOKEN and HASHNODE_PUBLICATION_ID environment variables.
Documentation: https://apidocs.hashnode.com
"""
import json
import os
import urllib.error
import urllib.request

from .base import CheckResult, SyndicationError, SyndicationResult, Syndicator
from .normalize import build_article_markdown, to_absolute_url


HASHNODE_GQL_ENDPOINT = "https://gql-beta.hashnode.com"


class HashnodeSyndicator(Syndicator):
    id = "hashnode"
    label = "Hashnode"

    def _token(self) -> str:
        return os.environ.get("HASHNODE_ACCESS_TOKEN", "").strip()

    def _publication_id(self) -> str:
        return os.environ.get("HASHNODE_PUBLICATION_ID", "").strip()

    def is_configured(self) -> bool:
        return bool(self._token() and self._publication_id())

    def text_limit(self) -> int | None:
        return None

    def check(self) -> CheckResult:
        token = self._token()
        pub_id = self._publication_id()
        if not token:
            return {"ok": False, "detail": "HASHNODE_ACCESS_TOKEN is not set."}
        if not pub_id:
            return {"ok": False, "detail": "HASHNODE_PUBLICATION_ID is not set."}

        query = """
        query GetPublication($id: ObjectId!) {
            publication(id: $id) {
                title
                url
            }
        }
        """
        payload = json.dumps({"query": query, "variables": {"id": pub_id}}).encode("utf-8")
        req = urllib.request.Request(
            HASHNODE_GQL_ENDPOINT,
            data=payload,
            headers={
                "Authorization": token,
                "Content-Type": "application/json",
                "User-Agent": "MyBlog-Syndicator/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                pub = (data.get("data") or {}).get("publication")
                if pub:
                    return {"ok": True, "detail": f"Connected to publication: {pub.get('title')}"}
                errors = data.get("errors") or []
                msg = errors[0].get("message") if errors else "Publication not found"
                return {"ok": False, "detail": f"Hashnode check failed: {msg}"}
        except Exception as e:
            return {"ok": False, "detail": f"Hashnode check failed: {e}"}

    def publish_detailed(
        self, text: str, url: str, media: list[str] | None = None, doc: dict | None = None
    ) -> SyndicationResult:
        token = self._token()
        pub_id = self._publication_id()
        if not token or not pub_id:
            raise SyndicationError("Hashnode is not configured (missing HASHNODE_ACCESS_TOKEN or HASHNODE_PUBLICATION_ID).")
        if not doc:
            raise SyndicationError("Hashnode syndication requires the full article document.")

        title = doc.get("title", "").strip() or "Untitled Article"
        base_url = os.environ.get("SITE_URL", "").strip().rstrip("/")
        markdown_body = build_article_markdown(doc, base_url, canonical_url=url)

        tags = []
        for t in (doc.get("tags") or [])[:5]:
            clean_tag = t.strip().lower().replace(" ", "-")
            if clean_tag:
                tags.append({"slug": clean_tag, "name": t.strip()})

        input_data: dict = {
            "title": title,
            "contentMarkdown": markdown_body,
            "publicationId": pub_id,
            "originalArticleURL": url,
        }

        if tags:
            input_data["tags"] = tags

        cover = doc.get("cover_image")
        if cover:
            input_data["coverImageOptions"] = {
                "coverImageURL": to_absolute_url(cover, base_url)
            }

        mutation = """
        mutation PublishPost($input: PublishPostInput!) {
            publishPost(input: $input) {
                post {
                    id
                    url
                    slug
                }
            }
        }
        """

        payload = json.dumps({"query": mutation, "variables": {"input": input_data}}).encode("utf-8")
        req = urllib.request.Request(
            HASHNODE_GQL_ENDPOINT,
            data=payload,
            headers={
                "Authorization": token,
                "Content-Type": "application/json",
                "User-Agent": "MyBlog-Syndicator/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                errors = res.get("errors")
                if errors:
                    raise SyndicationError(f"Hashnode GraphQL error: {errors[0].get('message', 'Unknown error')}")
                post_res = ((res.get("data") or {}).get("publishPost") or {}).get("post") or {}
                post_url = post_res.get("url")
                post_id = post_res.get("id")
                return {"url": post_url or url, "remote_id": post_id}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise SyndicationError(f"Hashnode publish failed ({e.code}): {err_body[:300]}")
        except Exception as e:
            if isinstance(e, SyndicationError):
                raise
            raise SyndicationError(f"Hashnode publish failed: {e}")
