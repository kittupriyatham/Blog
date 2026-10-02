"""LinkedIn adapter. Uses the versioned /rest/posts endpoint (stdlib urllib only).

LinkedIn sunsets API versions over time, so rather than hardcoding one we try a
recent version, fall back through the last several months on HTTP 426
(NONEXISTENT_VERSION), and remember whichever version the API accepts.

Posts go out as the author returned by `author_urn()`: the signed-in user's
Organization (Company Page) when `LINKEDIN_ORGANIZATION_URN` is set, otherwise
the person `LINKEDIN_AUTHOR_URN`. Publishing as the Page is what makes the
`organizationalEntityShareStatistics` read in linkedin_metrics.py possible (that
scope - `r_organization_social` - must be granted at OAuth time; see
linkedin_token.SCOPE).
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .base import CheckResult, Syndicator, SyndicationError
from . import linkedin_token


def organization_urn() -> str:
    """The configured Organization (Company Page) URN, or "" when unset.

    Read from the environment at call time (not import time) so a runtime change
    - or a test - is honoured.
    """
    return os.environ.get("LINKEDIN_ORGANIZATION_URN", "").strip()


def author_urn() -> str:
    """The single LinkedIn author URN used for posts and image uploads.

    The Organization (Company Page) URN wins when `LINKEDIN_ORGANIZATION_URN` is
    set, so the blog publishes as the Page; otherwise it falls back to the person
    `LINKEDIN_AUTHOR_URN`. "" when neither is set (`is_configured()` is then
    False). `delete()` is author-agnostic - it deletes by URN - so it is not
    affected.
    """
    return organization_urn() or os.environ.get("LINKEDIN_AUTHOR_URN", "").strip()


def _recent_versions(count: int = 12) -> list[str]:
    """Recent LinkedIn API versions as 'YYYYMM', newest first."""
    now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    out: list[str] = []
    for _ in range(count):
        out.append("%04d%02d" % (year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return out


class LinkedinSyndicator(Syndicator):
    id = "linkedin"
    label = "LinkedIn"
    API = "https://api.linkedin.com/rest/posts"
    DEFAULT_VERSION = "202609"

    _working_version: str | None = None  # remembered once discovered (per process)

    def is_configured(self) -> bool:
        # A token *and* an author (Organization URN preferred, person fallback).
        return bool(linkedin_token.has_credentials() and author_urn())

    def text_limit(self) -> int | None:
        """LinkedIn member posts accept 3000 characters (the commentary cap)."""
        return 3000

    def _version_candidates(self) -> list[str]:
        order: list[str] = []
        for v in ([self._working_version,
                   os.environ.get("LINKEDIN_VERSION"),
                   self.DEFAULT_VERSION] + _recent_versions()):
            if v and v not in order:
                order.append(v)
        return order

    def _upload_image(self, token: str, author: str, path: str) -> str | None:
        """Upload a local image and return its LinkedIn image URN.

        Two steps: initializeUpload hands back a signed URL plus the URN the post
        must reference, then the bytes are PUT to that URL. Returns None when the
        file is missing or not an image, so a text-only post still goes out.
        """
        from . import imageprep
        if not path or not os.path.isfile(path) or not imageprep.is_image(path):
            return None
        prepared = imageprep.prepare_image(path)

        init_body = json.dumps({"initializeUploadRequest": {"owner": author}}).encode("utf-8")
        last_error: str | None = None
        for version in self._version_candidates():
            req = urllib.request.Request(
                "https://api.linkedin.com/rest/images?action=initializeUpload",
                data=init_body,
                headers={
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0",
                    "LinkedIn-Version": version,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    value = (json.loads(resp.read().decode("utf-8")) or {}).get("value") or {}
                upload_url = value.get("uploadUrl")
                image_urn = value.get("image")
                if not upload_url or not image_urn:
                    raise SyndicationError("LinkedIn initializeUpload returned no uploadUrl/image.")
                with open(prepared, "rb") as fh:
                    put = urllib.request.Request(
                        upload_url, data=fh.read(),
                        headers={"Authorization": "Bearer " + token,
                                 "Content-Type": "application/jpeg"},
                        method="PUT")
                    with urllib.request.urlopen(put, timeout=120) as put_resp:
                        if put_resp.status not in (200, 201):
                            raise SyndicationError("LinkedIn image upload returned HTTP %s" % put_resp.status)
                return str(image_urn)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:300]
                if e.code == 426:  # NONEXISTENT_VERSION -> try the next candidate
                    last_error = "LinkedIn HTTP 426 (version %s): %s" % (version, body)
                    continue
                raise SyndicationError("LinkedIn image upload failed - HTTP %s: %s" % (e.code, body))
            except SyndicationError:
                raise
            except Exception as e:
                raise SyndicationError("LinkedIn image upload failed: %s" % e)
        raise SyndicationError(last_error or "LinkedIn: no active API version accepted images.")

    def _create_post(self, text: str, url: str, media: list[str] | None,
                     doc: dict | None) -> tuple[str, str | None]:
        """Create a post as `author_urn()`; return (permalink, post URN).

        The author is the Organization (Company Page) URN when configured, else
        the person URN - see `author_urn()`. The URN (`x-restli-id`) is the id
        LinkedIn's own share-statistics API keys on, so it is returned alongside
        the permalink and persisted as `remote_id` by `publish_detailed` (read
        back by linkedin_metrics.py).
        """
        token = linkedin_token.access_token()
        author = author_urn()
        if not token or not author:
            raise SyndicationError("LinkedIn is not configured (missing token or author URN).")
        payload = {
            "author": author,
            "commentary": text[:3000],
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED",
                             "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        first_image = next((m for m in (media or []) if m), None)
        image_urn = self._upload_image(token, author, first_image) if first_image else None
        if image_urn:
            payload["content"] = {"media": {"id": image_urn}}
        data = json.dumps(payload).encode("utf-8")
        last_error: str | None = None
        for version in self._version_candidates():
            req = urllib.request.Request(
                self.API,
                data=data,
                headers={
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0",
                    "LinkedIn-Version": version,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    urn = resp.headers.get("x-restli-id")
                LinkedinSyndicator._working_version = version
                permalink = ("https://www.linkedin.com/feed/update/" + urn) if urn else "https://www.linkedin.com/feed/"
                return permalink, (urn or None)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:500]
                if e.code == 426:  # NONEXISTENT_VERSION -> try the next candidate
                    last_error = "LinkedIn HTTP 426 (version %s): %s" % (version, body)
                    continue
                raise SyndicationError("LinkedIn HTTP %s: %s" % (e.code, body))
            except Exception as e:
                raise SyndicationError("LinkedIn request failed: %s" % e)
        raise SyndicationError(last_error or "LinkedIn: no active API version accepted.")

    def publish(self, text: str, url: str, media: list[str] | None = None,
                doc: dict | None = None) -> str:
        """Publish a post, attaching the first image when one is attached.

        The post is authored by `author_urn()` (Organization when configured).
        LinkedIn posts carry a single image, so only the first is used.
        """
        permalink, _urn = self._create_post(text, url, media, doc)
        return permalink

    def publish_detailed(self, text: str, url: str, media: list[str] | None = None,
                         doc: dict | None = None):
        """Publish and also persist the post URN as `remote_id`.

        The URN is what linkedin_metrics.py reads likes/comments with, so the
        syndication record carries it instead of only the web permalink.
        """
        permalink, urn = self._create_post(text, url, media, doc)
        return {"url": permalink, "remote_id": urn}

    def delete(self, url: str) -> None:
        """Delete a post this app created (author-only). Raises on failure."""
        token = linkedin_token.access_token()
        if not token:
            raise SyndicationError("LinkedIn is not configured (missing token).")
        urn = url.rstrip("/").split("/")[-1]
        endpoint = "https://api.linkedin.com/rest/posts/" + urllib.parse.quote(urn, safe="")
        last_error: str | None = None
        for version in self._version_candidates():
            req = urllib.request.Request(
                endpoint,
                headers={
                    "Authorization": "Bearer " + token,
                    "X-Restli-Protocol-Version": "2.0.0",
                    "LinkedIn-Version": version,
                },
                method="DELETE",
            )
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status in (200, 204):
                        return
                raise SyndicationError("LinkedIn delete returned an unexpected status")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:300]
                if e.code == 426:  # NONEXISTENT_VERSION -> try the next candidate
                    last_error = "LinkedIn HTTP 426 (version %s): %s" % (version, body)
                    continue
                raise SyndicationError("LinkedIn HTTP %s: %s" % (e.code, body))
            except Exception as e:
                raise SyndicationError("LinkedIn delete failed: %s" % e)
        raise SyndicationError(last_error or "LinkedIn: no active API version accepted.")

    def check(self) -> CheckResult:
        """Read-only token validation - does NOT post anything."""
        token = linkedin_token.access_token()
        author = author_urn()
        if not token:
            return CheckResult(ok=False, detail="No LinkedIn token available (set LINKEDIN_ACCESS_TOKEN, or run the OAuth setup).")
        if not author:
            return CheckResult(ok=False, detail="No LinkedIn author set - configure LINKEDIN_ORGANIZATION_URN (Page) or LINKEDIN_AUTHOR_URN (person).")
        req = urllib.request.Request("https://api.linkedin.com/v2/userinfo",
                                     headers={"Authorization": "Bearer " + token})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return CheckResult(ok=True, detail="Authenticated as %s" % (data.get("name") or data.get("sub")))
        except urllib.error.HTTPError as e:
            return CheckResult(ok=False, detail="HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))
        except Exception as e:
            return CheckResult(ok=False, detail=str(e))
