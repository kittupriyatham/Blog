"""The `cloud` backend's media provider + the pluggable upload adapters.

`CloudMediaProvider.save()` does not talk to a platform itself: it names the file
the same way the local backend does and hands the bytes to the **selected
adapter** (`MEDIA_ADAPTER`, default `http`).

Adapters:
* `GenericHttpUploadAdapter` - config-driven, no code: it drives any token-auth
  upload endpoint (and the plain pre-signed-URL case) with a PUT or POST and
  records the returned/permanent URL. Everything it needs is environment config
  (MEDIA_UPLOAD_URL, MEDIA_UPLOAD_METHOD, MEDIA_AUTH_HEADER + MEDIA_TOKEN,
  MEDIA_FORM_FIELD for multipart APIs, MEDIA_PUBLIC_BASE for link building).
* bespoke adapters - `register_adapter("name", Class)` when an API needs signing
  (S3 SigV4, SAS, OAuth, ...). One class covers it; the app is never touched,
  and nothing is built until a platform actually needs it.
"""
from src.config import (
    MEDIA_ADAPTER,
    MEDIA_AUTH_HEADER,
    MEDIA_FORM_FIELD,
    MEDIA_PUBLIC_BASE,
    MEDIA_TOKEN,
    MEDIA_UPLOAD_METHOD,
    MEDIA_UPLOAD_URL,
)

from ..base import MediaProvider, ProviderError
from . import http


def _bare_name(ref) -> str:
    """The stored filename behind a reference (a URL or a bare name alike)."""
    text = str(ref or "")
    if text.startswith("http://") or text.startswith("https://"):
        text = text.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return text.replace("/media/", "").lstrip("/")


def _auth_headers():
    """The configured auth header, when both the header name and token are set."""
    headers = {}
    if MEDIA_AUTH_HEADER and MEDIA_TOKEN:
        headers[MEDIA_AUTH_HEADER] = MEDIA_TOKEN
    return headers


class UploadAdapter:
    """Base class for media-upload adapters (see `register_adapter`).

    Subclasses implement `upload()` and are expected to answer `url()` for the
    references they return. `exists()`/`delete()` are optional - the defaults say
    "cannot tell" / "nothing to do", so a write-only API still works.
    """

    name = ""

    def upload(self, file, name) -> str:
        raise NotImplementedError

    def url(self, ref) -> str:
        raise NotImplementedError

    def exists(self, name) -> bool:
        return False

    def delete(self, name) -> None:
        return None

    def health(self) -> bool:
        return False


class GenericHttpUploadAdapter(UploadAdapter):
    """Config-driven upload: PUT/POST the file's bytes to MEDIA_UPLOAD_URL.

    Covers a platform with a token-auth upload endpoint and a pre-signed URL to
    PUT to; set MEDIA_FORM_FIELD when the API wants multipart/form-data instead
    of raw bytes. The stored reference is the URL the API returns (JSON `url` /
    `location` / ... or a Location header), else MEDIA_PUBLIC_BASE joined with
    the name. No SDK.
    """

    name = "http"

    @staticmethod
    def _content(file):
        """The file's bytes, from the start (Flask's FileStorage stream)."""
        try:
            file.stream.seek(0)
        except Exception:
            pass
        data = file.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
        return data or b""

    def upload(self, file, name) -> str:
        url = (MEDIA_UPLOAD_URL or "").strip()
        if not url:
            raise ProviderError("MEDIA_BACKEND=cloud needs MEDIA_UPLOAD_URL "
                               "(the platform's upload endpoint, or a pre-signed URL).")
        data = self._content(file)
        headers = _auth_headers()
        if MEDIA_FORM_FIELD:
            body, content_type = http.multipart_body(MEDIA_FORM_FIELD, name, data)
            headers["Content-Type"] = content_type
            _, resp_headers, resp_body = http.post(url, body, headers)
        else:
            headers.setdefault("Content-Type", "application/octet-stream")
            _, resp_headers, resp_body = http.request(MEDIA_UPLOAD_METHOD or "PUT", url, data, headers)
        return self._reference(name, resp_headers, resp_body)

    def _reference(self, name, resp_headers, resp_body) -> str:
        for candidate in (http.url_from_response(resp_body),
                          (resp_headers or {}).get("Location")):
            if candidate and str(candidate).startswith(("http://", "https://")):
                return str(candidate)
        return self.url(name)

    def url(self, ref) -> str:
        if not ref:
            return ref
        text = str(ref)
        if text.startswith("http://") or text.startswith("https://"):
            return text
        base = (MEDIA_PUBLIC_BASE or "").strip().rstrip("/")
        bare = _bare_name(text)
        return base + "/" + bare if base else "/media/" + bare

    def exists(self, name) -> bool:
        return http.exists(self.url(name), _auth_headers())

    def delete(self, name) -> None:
        http.delete(self.url(name), _auth_headers())

    def health(self) -> bool:
        return bool((MEDIA_UPLOAD_URL or "").strip())


# --- the adapter registry (the hook for bespoke adapters) ---
_ADAPTERS = {}


def register_adapter(name, cls):
    """Register `cls` as the adapter called `name` (usable as `MEDIA_ADAPTER`)."""
    key = (name or "").strip().lower()
    if not key:
        raise ProviderError("An adapter needs a name.")
    if not (isinstance(cls, type) and issubclass(cls, UploadAdapter)):
        raise ProviderError("An adapter must subclass UploadAdapter (got %r)." % (cls,))
    _ADAPTERS[key] = cls
    return cls


def get_adapter(name=None) -> UploadAdapter:
    """Build the adapter called `name` (default: MEDIA_ADAPTER, else "http")."""
    key = (name or MEDIA_ADAPTER or "http").strip().lower()
    cls = _ADAPTERS.get(key)
    if cls is None:
        raise ProviderError("Unknown media adapter %r (registered: %s)"
                            % (key, ", ".join(sorted(_ADAPTERS))))
    return cls()


register_adapter("http", GenericHttpUploadAdapter)


class CloudMediaProvider(MediaProvider):
    """Media on a platform, reached through the selected upload adapter."""

    name = "cloud"

    def __init__(self):
        self._adapter = None

    @property
    def adapter(self) -> UploadAdapter:
        if self._adapter is None:
            self._adapter = get_adapter()
        return self._adapter

    def save(self, file, stem, taken) -> str:
        # Same provider-agnostic naming as the local backend (a second file in a
        # request still cannot collide); no disk check - the cloud namespace is
        # not the local filesystem.
        from src.media.uploads import _ext_of, _unique_name

        name = _unique_name(stem, _ext_of(file.filename), taken, check_disk=False)
        return self.adapter.upload(file, name)

    def url(self, ref) -> str:
        return self.adapter.url(ref)

    def exists(self, name) -> bool:
        return self.adapter.exists(name)

    def delete(self, name) -> None:
        return self.adapter.delete(name)

    def health(self) -> bool:
        return self.adapter.health()


__all__ = ["CloudMediaProvider", "UploadAdapter", "GenericHttpUploadAdapter",
           "register_adapter", "get_adapter"]
