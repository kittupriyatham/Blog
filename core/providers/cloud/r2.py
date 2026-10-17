"""Cloudflare R2 media adapter - S3-compatible uploads, signed with the stdlib.

R2 is reached through its S3-compatible API, which requires every request to be
signed with AWS Signature Version 4. This adapter does that signing with the
standard library (`hashlib`/`hmac`/`urllib`) - the project rule is no cloud SDK,
so `boto3` is deliberately not used.

It is a *bespoke* adapter (see `media.py::UploadAdapter`), not the generic config
driven one, because the generic adapter only knows how to send a bare bearer
token or an already signed pre-signed URL; S3 needs a per-request signature over
the exact bytes being sent, which is what lives here.

Config (env, all required unless noted):
  R2_ACCOUNT_ID         the Cloudflare account id (the bucket's owner)
  R2_ACCESS_KEY_ID      the R2 API token's access key id
  R2_SECRET_ACCESS_KEY  the R2 API token's secret
  R2_BUCKET             the bucket name
  R2_PUBLIC_BASE        the public base the files are served from - the bucket's
                        "Public Development URL" (https://pub-<id>.r2.dev) or a
                        custom domain bound to the bucket. No trailing slash.

The public URL is what the app hands to the browser; the signed endpoint is only
used to write/read/delete the object, so the two need not share a host.
"""
import hashlib
import hmac
import os
from datetime import datetime, timezone
from urllib.parse import quote

from core.config import (
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_PUBLIC_BASE,
    R2_BUCKET,
    R2_SECRET_ACCESS_KEY,
)

from ..base import ProviderError
from . import http
from .media import UploadAdapter, register_adapter

#: R2 accepts "auto" as the region and routes to the bucket's own region.
REGION = "auto"
SERVICE = "s3"
ALGORITHM = "AWS4-HMAC-SHA256"


def _configured() -> bool:
    return all(str(v or "").strip() for v in
               (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET))


def _endpoint() -> str:
    """The signed S3 endpoint for this account (`https://<id>.r2.cloudflarestorage.com`)."""
    return "https://%s.r2.cloudflarestorage.com" % R2_ACCOUNT_ID.strip()


def _payload_hash(data: bytes) -> str:
    return hashlib.sha256(data or b"").hexdigest()


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str) -> bytes:
    """Derive the SigV4 signing key (date -> region -> service -> request chain)."""
    k_date = _sign(("AWS4" + secret).encode("utf-8"), datestamp)
    k_region = _sign(k_date, REGION)
    k_service = _sign(k_region, SERVICE)
    return _sign(k_service, "aws4_request")


def _headers(method: str, path: str, data: bytes, now=None) -> dict:
    """Fully signed request headers for `method <endpoint><path>` carrying `data`.

    `path` is the raw object path (already URI encoded for the wire). The signed
    headers are host + x-amz-content-sha256 + x-amz-date, so nothing else needs to
    be pinned by the caller.
    """
    if not _configured():
        raise ProviderError("R2 needs R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
                            "R2_SECRET_ACCESS_KEY and R2_BUCKET set.")
    now = now or datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    payload_hash = _payload_hash(data)

    host = _endpoint().split("//", 1)[1]
    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    signed_headers = ";".join(sorted(headers))
    canonical_headers = "".join("%s:%s\n" % (k, headers[k]) for k in sorted(headers))

    canonical_request = "\n".join([
        method.upper(),
        path,
        "",  # query string - none for these object operations
        canonical_headers,
        signed_headers,
        payload_hash,
    ])
    scope = "%s/%s/%s/aws4_request" % (datestamp, REGION, SERVICE)
    string_to_sign = "\n".join([
        ALGORITHM,
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signature = hmac.new(
        _signing_key(R2_SECRET_ACCESS_KEY.strip(), datestamp),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    headers["Authorization"] = (
        "%s Credential=%s/%s, SignedHeaders=%s, Signature=%s"
        % (ALGORITHM, R2_ACCESS_KEY_ID.strip(), scope, signed_headers, signature)
    )
    return headers


def _object_path(name: str) -> str:
    """The wire path for a bucket object: `/bucket/key`, URI-encoded per segment.

    S3 keeps `/` as the path separator (it is NOT encoded), but every other
    reserved character in the key must be percent-encoded, or the signature will
    not match the URL the server sees.
    """
    key = str(name or "").lstrip("/")
    encoded = quote(key, safe="/")
    return "/%s/%s" % (R2_BUCKET.strip(), encoded)


def _request(method: str, name: str, data: bytes = None, timeout=30):
    """Sign and send one object request. Returns (status, headers, body)."""
    path = _object_path(name)
    headers = _headers(method, path, data)
    body = data if method.upper() in ("PUT", "POST") else None
    return http.request(method, _endpoint() + path, body,
                        {k: v for k, v in headers.items() if k != "host"}, timeout)


class R2UploadAdapter(UploadAdapter):
    """Upload to a Cloudflare R2 bucket over its S3 API, signed with SigV4."""

    name = "r2"

    @staticmethod
    def _content(file):
        """A FileStorage's bytes from the start (same contract as the generic adapter)."""
        try:
            file.stream.seek(0)
        except Exception:
            pass
        data = file.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
        return data or b""

    def upload(self, file, name) -> str:
        data = self._content(file)
        _request("PUT", name, data)
        # The signed endpoint's response carries no public URL, so the reference is
        # always the configured public base joined with the object name.
        return self.url(name)

    def url(self, ref) -> str:
        if not ref:
            return ref
        text = str(ref)
        if text.startswith(("http://", "https://")):
            return text
        base = (R2_PUBLIC_BASE or "").strip().rstrip("/")
        bare = str(text).replace("/media/", "").lstrip("/")
        return base + "/" + bare if base else "/media/" + bare

    def exists(self, name) -> bool:
        try:
            status, _, _ = _request("HEAD", name)
            return 200 <= status < 300
        except Exception:
            return False

    def delete(self, name) -> None:
        try:
            _request("DELETE", name)
        except Exception:
            # Deleting a missing object is a no-op, not an error worth raising.
            pass

    def health(self) -> bool:
        return _configured() and bool((R2_PUBLIC_BASE or "").strip())


register_adapter("r2", R2UploadAdapter)

__all__ = ["R2UploadAdapter", "REGION", "SERVICE"]
