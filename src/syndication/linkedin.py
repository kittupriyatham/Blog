"""LinkedIn adapter. Uses the versioned /rest/posts endpoint (stdlib urllib only).

LinkedIn sunsets API versions over time, so rather than hardcoding one we try a
recent version, fall back through the last several months on HTTP 426
(NONEXISTENT_VERSION), and remember whichever version the API accepts.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .base import CheckResult, Syndicator, SyndicationError


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
        return bool(os.environ.get("LINKEDIN_ACCESS_TOKEN") and os.environ.get("LINKEDIN_AUTHOR_URN"))

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

    def publish(self, text: str, url: str, media: list[str] | None = None,
                doc: dict | None = None) -> str:
        """Publish a member post, attaching the first image when one is attached.

        LinkedIn member posts carry a single image, so only the first is used.
        """
        token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
        author = os.environ.get("LINKEDIN_AUTHOR_URN")
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
                return ("https://www.linkedin.com/feed/update/" + urn) if urn else "https://www.linkedin.com/feed/"
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:500]
                if e.code == 426:  # NONEXISTENT_VERSION -> try the next candidate
                    last_error = "LinkedIn HTTP 426 (version %s): %s" % (version, body)
                    continue
                raise SyndicationError("LinkedIn HTTP %s: %s" % (e.code, body))
            except Exception as e:
                raise SyndicationError("LinkedIn request failed: %s" % e)
        raise SyndicationError(last_error or "LinkedIn: no active API version accepted.")

    def delete(self, url: str) -> None:
        """Delete a post this app created (author-only). Raises on failure."""
        token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
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
        token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
        author = os.environ.get("LINKEDIN_AUTHOR_URN")
        if not token:
            return CheckResult(ok=False, detail="No LINKEDIN_ACCESS_TOKEN set.")
        if not author:
            return CheckResult(ok=False, detail="No LINKEDIN_AUTHOR_URN set.")
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
