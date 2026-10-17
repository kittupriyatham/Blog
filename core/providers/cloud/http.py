"""Raw HTTP used by the cloud media adapters - stdlib `urllib`, no vendor SDK.

Platform APIs are reached with plain HTTP: a token in a header, bytes in the
body. When an endpoint needs signing or an odd handshake, that lives in a bespoke
adapter (see `media.py`), not here.

Every call raises `ProviderError` on failure, so the layer reports one error type.
"""
import json
import mimetypes
import urllib.error
import urllib.request
import uuid

from ..base import ProviderError

DEFAULT_TIMEOUT = 30


def request(method, url, data=None, headers=None, timeout=DEFAULT_TIMEOUT):
    """Perform one HTTP request. Returns (status, headers, body-bytes).

    Raises ProviderError for transport failures and non-2xx responses.
    """
    if not url:
        raise ProviderError("No URL configured for the HTTP request.")
    method = (method or "GET").upper()
    try:
        req = urllib.request.Request(url, data=data, headers=dict(headers or {}), method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read()
        except Exception:
            pass
        raise ProviderError("HTTP %s %s failed: %s %s"
                            % (method, url, e.code, body[:200].decode("utf-8", "replace"))) from e
    except urllib.error.URLError as e:
        raise ProviderError("HTTP %s %s failed: %s" % (method, url, e.reason)) from e
    except ValueError as e:
        # e.g. a non-absolute URL (no scheme) - keep the one-error-type contract.
        raise ProviderError("Invalid URL for HTTP %s: %r (%s)" % (method, url, e)) from e


def put(url, data, headers=None, timeout=DEFAULT_TIMEOUT):
    return request("PUT", url, data, headers, timeout)


def post(url, data, headers=None, timeout=DEFAULT_TIMEOUT):
    return request("POST", url, data, headers, timeout)


def head(url, headers=None, timeout=DEFAULT_TIMEOUT):
    return request("HEAD", url, None, headers, timeout)


def delete(url, headers=None, timeout=DEFAULT_TIMEOUT):
    return request("DELETE", url, None, headers, timeout)


def exists(url, headers=None, timeout=DEFAULT_TIMEOUT) -> bool:
    """True when a HEAD (falling back to a ranged GET) reports the object."""
    try:
        status, _, _ = head(url, headers, timeout)
        return 200 <= status < 300
    except ProviderError:
        pass
    try:  # some servers answer 405/501 to HEAD - fall back to a ranged GET
        get_headers = dict(headers or {})
        get_headers.setdefault("Range", "bytes=0-0")
        status, _, _ = request("GET", url, None, get_headers, timeout)
        return 200 <= status < 300
    except ProviderError:
        return False


def multipart_body(field_name, filename, content, content_type=None, boundary=None):
    """Encode one file as `multipart/form-data`. Returns (body, content-type).

    Used when the platform's upload API takes a form field rather than raw bytes.
    """
    boundary = boundary or ("----blog" + uuid.uuid4().hex)
    content_type = content_type or mimetypes.guess_type(filename or "")[0] or "application/octet-stream"
    head = (
        "--%s\r\n"
        'Content-Disposition: form-data; name="%s"; filename="%s"\r\n'
        "Content-Type: %s\r\n\r\n" % (boundary, field_name, filename, content_type)
    ).encode("utf-8")
    tail = ("\r\n--%s--\r\n" % boundary).encode("utf-8")
    return head + (content or b"") + tail, "multipart/form-data; boundary=%s" % boundary


def url_from_response(body):
    """Pull a stored URL out of an upload response (JSON `url`/`location`/..., named request).

    Returns None when the response carries no usable URL - the caller then falls
    back to its configured public base.
    """
    if not body:
        return None
    if isinstance(body, (bytes, bytearray)):
        text = body.decode("utf-8", "replace").strip()
    else:
        text = str(body).strip()
    if not text:
        return None
    if text.startswith(("http://", "https://")) and "\n" not in text:
        return text
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return _dig_url(data)


_URL_KEYS = ("url", "public_url", "publicUrl", "secure_url", "location", "href", "link")


def _dig_url(data, depth=0):
    if depth > 3:
        return None
    if isinstance(data, str):
        return data if data.startswith(("http://", "https://")) else None
    if isinstance(data, dict):
        for key in _URL_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        for value in data.values():
            found = _dig_url(value, depth + 1)
            if found:
                return found
    if isinstance(data, list):
        for value in data:
            found = _dig_url(value, depth + 1)
            if found:
                return found
    return None


__all__ = ["DEFAULT_TIMEOUT", "request", "put", "post", "head", "delete", "exists",
           "multipart_body", "url_from_response"]
