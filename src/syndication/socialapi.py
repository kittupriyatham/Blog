"""SocialAPI.ai adapter - one unified API behind the Syndicator interface.

SocialAPI posts through *its own* pre-approved Meta/Google/X apps, so we avoid
Meta business verification and the retired Medium-style integrations entirely.
A single API key covers every platform, so one class serves many: instantiate
it per platform and register each instance.

Behaviour that bites people (from the provider's own reliability guide):
  * `201` means *accepted*, not delivered - delivery is async, so we poll
    `GET /v1/posts/{id}` until the target reaches a terminal status.
  * `207` = some targets published, `422` = every target failed.
  * Media must be `{"source": ..., "source_type": "url"|"media_id", "type": ...}`.
    A `media_url` key is silently dropped and publishes without the media.
  * All ids are opaque strings - persist them as text.

Config (env):
  SOCIALAPI_KEY               required; the Bearer token
  SOCIALAPI_BRAND_ID          optional; restrict account lookup to one brand
  SOCIALAPI_PLATFORMS         optional CSV; defaults to facebook,instagram,youtube,twitter
  SOCIALAPI_ACCOUNT_<PLAT>    optional; pin the account id for a platform
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from . import imageprep
from .base import CheckResult, Syndicator, SyndicationError, SyndicationResult

BASE_URL = "https://api.social-api.ai/v1"

# Cloudflare fronts the API and rejects urllib's default "Python-urllib/3.x"
# signature with HTTP 403 "error code: 1010". Any explicit UA is accepted.
USER_AGENT = "KittuBlog-Syndicator/1.0"

DEFAULT_PLATFORMS = [
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("youtube", "YouTube"),
    # SocialAPI's platform slug for X is "twitter" (that is what /v1/accounts
    # reports); only the label is "X / Twitter". Using "x" here would never
    # resolve an account.
    ("twitter", "X / Twitter"),
    ("bluesky", "Bluesky"),
    # Pinterest is image-only; the local REQUIRES_MEDIA guard blocks text posts
    # before a post credit is spent.
    ("pinterest", "Pinterest"),
]

# Conservative per-platform text caps; the provider validates too and returns a
# per-target error, so these only avoid guaranteed failures.
TEXT_LIMITS = {"twitter": 280, "instagram": 2200, "facebook": 6000, "bluesky": 300}
DEFAULT_TEXT_LIMIT = 3000

TERMINAL = {"published", "failed", "cancelled", "partial"}

# Platforms that refuse a text-only post. Caught locally so we do not spend a
# post credit on a guaranteed failure.
REQUIRES_MEDIA = {"instagram", "youtube", "tiktok", "pinterest"}

# YouTube is video-only: an image satisfies REQUIRES_MEDIA but is rejected by
# the platform, so it is checked separately before a post credit is spent.
REQUIRES_VIDEO = {"youtube"}

# Platforms with no free-text post that we satisfy with a generated text card
# rather than asking the author for an image. YouTube is NOT here - it needs a
# real video, which cannot be synthesised from text.
TEXT_CARD_PLATFORMS = {"instagram", "pinterest"}

# X/Twitter needs two separate things, so they are two separate switches:
#   * API credit - X has no free tier (pay-per-use since Feb 2026). Without
#     credit the checkbox is greyed out rather than failing at publish time.
#   * a Premium subscription - X Articles are a Premium feature, so long-form
#     syndication to X is only offered when this is on.
def twitter_has_credit() -> bool:
    """False disables the X checkbox entirely (greyed out)."""
    return os.environ.get("TWITTER_API_CREDIT", "1").strip() != "0"


def twitter_has_subscription() -> bool:
    """True allows articles to be syndicated to X."""
    return os.environ.get("TWITTER_SUBSCRIPTION", "0").strip() == "1"


def _configured_platforms() -> list[tuple[str, str]]:
    override = os.environ.get("SOCIALAPI_PLATFORMS", "").strip()
    if not override:
        return list(DEFAULT_PLATFORMS)
    labels = dict(DEFAULT_PLATFORMS)
    out = []
    for raw in override.split(","):
        pid = raw.strip().lower()
        if pid:
            out.append((pid, labels.get(pid, pid.capitalize())))
    return out


class SocialApiSyndicator(Syndicator):
    def __init__(self, platform: str, label: str):
        self.id = platform
        self.label = label
        self._accounts_cache: tuple[float, list[dict]] | None = None

    # --- plumbing ---------------------------------------------------------
    @staticmethod
    def _key() -> str:
        return os.environ.get("SOCIALAPI_KEY", "").strip()

    def _request(self, method: str, path: str, payload: dict | None = None, timeout: int = 30):
        key = self._key()
        if not key:
            raise SyndicationError("SocialAPI is not configured (missing SOCIALAPI_KEY).")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            BASE_URL + path,
            data=data,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(body)
            except ValueError:
                parsed = {"raw": body[:400]}
            return e.code, parsed
        except Exception as e:
            raise SyndicationError("SocialAPI request failed: %s" % e)

    @staticmethod
    def _error_message(status: int, body: dict) -> str:
        """Surface as much of the provider's error as it gives us.

        For validation failures the actionable part lives in `error.details` /
        `issues`, so returning only `message` would reduce "post failed
        validation; fix the listed issues" to a message with no list.
        """
        err = body.get("error") if isinstance(body, dict) else None
        if not isinstance(err, dict):
            return "HTTP %s: %s" % (status, str(body)[:300])
        parts = [err.get("message")]
        for key in ("code", "details", "issues", "violations", "meta"):
            val = err.get(key)
            if val:
                parts.append("%s=%s" % (key, val if isinstance(val, str) else json.dumps(val)))
        detail = " | ".join(str(p) for p in parts if p)
        return "HTTP %s: %s" % (status, detail or str(body)[:300])

    # --- accounts ---------------------------------------------------------
    def _accounts(self, fresh: bool = False) -> list[dict]:
        """Connected accounts, cached briefly so a burst of publishes doesn't re-list."""
        now = time.time()
        # Declared up front so both branches give `accounts` the same type;
        # inferring it per-branch made checkers complain across lines 130-134.
        accounts: list[dict]
        if not fresh and self._accounts_cache and now - self._accounts_cache[0] < 300:
            accounts = self._accounts_cache[1]
        else:
            status, body = self._request("GET", "/accounts")
            if status != 200:
                raise SyndicationError("SocialAPI account list failed - " + self._error_message(status, body))
            accounts = body.get("data") or []
            self._accounts_cache = (now, accounts)
        brand = os.environ.get("SOCIALAPI_BRAND_ID", "").strip()
        if brand:
            accounts = [a for a in accounts if a.get("brand_id") == brand]
        return accounts

    def _account_id(self) -> str:
        override = os.environ.get("SOCIALAPI_ACCOUNT_" + self.id.upper(), "").strip()
        if override:
            return override
        for a in self._accounts():
            if a.get("platform") == self.id and a.get("status") == "active":
                return a["id"]
        raise SyndicationError(
            "No active %s account connected to SocialAPI. Connect one in the SocialAPI dashboard." % self.label)

    # --- interface --------------------------------------------------------
    def is_configured(self) -> bool:
        if not self._key():
            return False
        # X has no free tier, so with no credit the checkbox is greyed out
        # instead of failing at publish time.
        if self.id == "twitter":
            return twitter_has_credit()
        return True

    def text_limit(self) -> int | None:
        """This platform's own character cap (Twitter 280, Instagram 2200, ...)."""
        return TEXT_LIMITS.get(self.id, DEFAULT_TEXT_LIMIT)

    @staticmethod
    def _media_kind(src: str) -> str:
        """'video' or 'image', derived from the path extension."""
        ext = src.rsplit(".", 1)[-1].lower() if "." in src else ""
        return "video" if ext in {"mp4", "mov", "webm", "mkv", "avi", "wmv"} else "image"

    @staticmethod
    def _mime_for(src: str) -> str:
        ext = src.rsplit(".", 1)[-1].lower() if "." in src else ""
        return {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
                "svg": "image/svg+xml", "mp4": "video/mp4", "mov": "video/quicktime",
                "webm": "video/webm", "mkv": "video/x-matroska",
                "avi": "video/x-msvideo"}.get(ext, "application/octet-stream")

    def _upload_media(self, path: str) -> str:
        """Upload a local file to the SocialAPI media library; return its id.

        Publishing by `media_id` means the platform never fetches anything, so
        image-first platforms work from a local machine with no public URL and
        no tunnel. Uploading is free - only publishing spends a credit.
        """
        if not os.path.exists(path):
            raise SyndicationError("Media file not found: %s" % path)
        with open(path, "rb") as fh:
            blob = fh.read()

        boundary = "----KittuBlog" + hashlib.sha1(os.urandom(16)).hexdigest()[:16]
        filename = os.path.basename(path)
        body = b"".join([
            ("--%s\r\n" % boundary).encode("utf-8"),
            ('Content-Disposition: form-data; name="file"; filename="%s"\r\n' % filename).encode("utf-8"),
            ("Content-Type: %s\r\n\r\n" % self._mime_for(path)).encode("utf-8"),
            blob,
            ("\r\n--%s--\r\n" % boundary).encode("utf-8"),
        ])
        req = urllib.request.Request(
            BASE_URL + "/media/upload",
            data=body,
            headers={
                "Authorization": "Bearer " + self._key(),
                "Content-Type": "multipart/form-data; boundary=" + boundary,
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            raise SyndicationError("Media upload failed - HTTP %s: %s"
                                   % (e.code, e.read().decode("utf-8", "replace")[:200]))
        except Exception as e:
            raise SyndicationError("Media upload failed: %s" % e)

        media_id = payload.get("media_id")
        if not media_id:
            raise SyndicationError("Media upload returned no media_id: %s" % str(payload)[:200])
        return str(media_id)

    @staticmethod
    def _local_media_path(src: str) -> str | None:
        """Resolve a media reference to a file on disk, or None when remote.

        Stored media is a browser-relative "/media/<name>" path (see app.py) -
        that is what gets served, but the uploader needs the real file.
        """
        if src.startswith("http://") or src.startswith("https://"):
            return None
        if os.path.isfile(src):
            return src
        name = src.split("/media/", 1)[-1].lstrip("/").replace("/", os.sep)
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        base = os.environ.get("MEDIA_FOLDER", "").strip() or os.path.join(repo, "media")
        candidate = os.path.join(base, name)
        return candidate if os.path.isfile(candidate) else None

    # Instagram rejects any image outside 4:5 - 1.91:1, so its uploads are padded
    # into range rather than being sent as-is and refused at delivery.
    ASPECT_BOUNDS = {"instagram": imageprep.INSTAGRAM_ASPECT}

    def _media_payload(self, media: list[str] | None) -> list[dict]:
        """Local files are prepared and uploaded; public URLs are referenced as-is.

        Uploading means the platform never fetches anything, so media works from
        a local machine with no public URL - and an image the author attached is
        actually used rather than silently dropped.

        Every image is prepared, not only the ones a platform is known to be fussy
        about: sending the untouched original elsewhere is exactly what came back
        as nginx `413 Request Entity Too Large`.
        """
        bounds = self.ASPECT_BOUNDS.get(self.id)
        out = []
        for src in media or []:
            local = self._local_media_path(src)
            if local:
                local = imageprep.prepare_image(local, aspect=bounds)
                out.append({"source": self._upload_media(local), "source_type": "media_id",
                            "type": self._media_kind(local)})
            else:
                out.append({"source": src, "source_type": "url", "type": self._media_kind(src)})
        return out

    def validate(self, text: str, url: str, media: list[str] | None = None,
                 doc: dict | None = None) -> dict:
        """Dry-run this post against the platform's rules. Costs no credits.

        `POST /v1/posts/validate` applies the same validation the publish path
        does and returns errors/warnings instead of publishing, so a post can be
        checked as often as needed without spending the monthly allowance.
        """
        limit = TEXT_LIMITS.get(self.id, DEFAULT_TEXT_LIMIT)
        body: dict = {
            "text": text[:limit],
            "targets": [self._target(self._account_id())],
            "platforms": [self.id],
        }
        media_items = self._media_payload(media)
        if media_items:
            body["media"] = media_items
        platform_data = self._platform_data(media)
        if platform_data:
            body["platform_data"] = platform_data
        status, payload = self._request("POST", "/posts/validate", body)
        if status not in (200, 201):
            raise SyndicationError(self._error_message(status, payload))
        return payload

    def _pinterest_board(self) -> str:
        """Board id for a Pin. Pinterest has no default board, so this is required.

        SOCIALAPI_BOARD_PINTEREST pins it. Otherwise the account's first board is
        used, and one is created if the account has none - without a board every
        Pin is rejected before it reaches Pinterest.
        """
        override = os.environ.get("SOCIALAPI_BOARD_PINTEREST", "").strip()
        if override:
            return override
        account = self._account_id()
        status, body = self._request("GET", "/accounts/%s/boards" % account)
        rows = (body.get("data") if isinstance(body, dict) else None) or []
        if status == 200 and rows:
            return str(rows[0].get("board_id") or rows[0].get("id") or "")
        status, body = self._request("POST", "/accounts/%s/boards" % account,
                                     {"name": "Blog", "privacy": "PUBLIC"})
        if status in (200, 201) and isinstance(body, dict):
            resolved = body.get("board_id") or body.get("id")
            if resolved:
                return str(resolved)
        raise SyndicationError("Pinterest needs a board and none could be resolved - "
                               + self._error_message(status, body))

    def _platform_data(self, media: list[str] | None) -> dict | None:
        """Top-level `platform_data`, keyed by platform.

        Instagram requires `content_type` when publishing, and this belongs at the
        TOP LEVEL of the request body - not on the target. Nesting it on the
        target made the API ignore it and reject the post with "content_type is
        required for Instagram". Pinterest's `board_id` is the opposite: it must
        sit on the target (see _target).
        """
        if self.id != "instagram":
            return None
        count = len(media or [])
        kinds = {self._media_kind(m) for m in (media or [])}
        if count > 1:
            content_type = "carousel"
        elif kinds == {"video"}:
            content_type = "reel"
        else:
            content_type = "feed"
        return {"instagram": {"content_type": content_type}}

    def _target(self, account_id: str) -> dict:
        """Per-target fields.

        Pinterest requires `board_id` here; supplying it inside `platform_data`
        is rejected with `validation.use_board_id`.
        """
        target: dict = {"account_id": account_id}
        if self.id == "pinterest":
            target["board_id"] = self._pinterest_board()
        return target

    def publish(self, text: str, url: str, media: list[str] | None = None,
                doc: dict | None = None) -> str:
        return self.publish_detailed(text, url, media, doc)["url"]

    def publish_detailed(self, text: str, url: str, media: list[str] | None = None,
                         doc: dict | None = None) -> SyndicationResult:
        if self.id in REQUIRES_MEDIA and not media:
            raise SyndicationError(
                "%s needs an image or video, and this post has no public media to attach. "
                "Attach media on a public URL, or generate a text card." % self.label)
        if self.id in REQUIRES_VIDEO and not any(self._media_kind(m) == "video" for m in (media or [])):
            raise SyndicationError(
                "%s needs a video attachment, and this post has none. Attach a video file." % self.label)
        account_id = self._account_id()
        limit = TEXT_LIMITS.get(self.id, DEFAULT_TEXT_LIMIT)
        payload = {
            "text": text[:limit],
            "targets": [self._target(account_id)],
            "publish_now": True,
        }
        media_items = self._media_payload(media)
        if media_items:
            payload["media"] = media_items
        platform_data = self._platform_data(media)
        if platform_data:
            payload["platform_data"] = platform_data

        status, body = self._request("POST", "/posts", payload)
        if status not in (201, 207, 200):
            raise SyndicationError("SocialAPI create post failed - " + self._error_message(status, body))

        post_id = body.get("id")
        if not post_id:
            raise SyndicationError("SocialAPI returned no post id.")

        permalink = self._target_permalink(body, account_id)
        if permalink:
            return {"url": permalink, "remote_id": str(post_id)}

        return self._await_result(post_id, account_id, str(post_id))

    def _target_permalink(self, body: dict, account_id: str) -> str | None:
        """Read a permalink out of a create/get response for our target, if terminal."""
        for t in body.get("targets") or []:
            if t.get("account_id") != account_id:
                continue
            if t.get("status") == "failed":
                err = t.get("error") or {}
                raise SyndicationError("%s delivery failed: %s" % (self.label, err.get("message") or "unknown error"))
            if t.get("status") == "published" and t.get("permalink"):
                return t["permalink"]
        return None

    def _await_result(self, post_id: str, account_id: str, remote_id: str,
                      deadline_s: int = 120, interval: float = 3.0) -> SyndicationResult:
        """Delivery is async - poll until our target reaches a terminal status."""
        end = time.time() + deadline_s
        last: dict = {}
        while time.time() < end:
            time.sleep(interval)
            status, body = self._request("GET", "/posts/%s" % post_id)
            if status != 200:
                raise SyndicationError("SocialAPI post lookup failed - " + self._error_message(status, body))
            last = body
            permalink = self._target_permalink(body, account_id)
            if permalink:
                return {"url": permalink, "remote_id": remote_id}
            if body.get("status") in TERMINAL:
                break
        raise SyndicationError(
            "%s post did not reach a terminal state within %ss (post %s, status %s)."
            % (self.label, deadline_s, post_id, last.get("status", "unknown")))

    def delete(self, identifier: str) -> None:
        """`identifier` is the SocialAPI post id (preferred) or a permalink."""
        ident = (identifier or "").strip().rstrip("/")
        if not ident:
            raise SyndicationError("SocialAPI delete needs a post id.")
        key = ident.split("/")[-1] if ident.startswith("http") else ident
        status, body = self._request("DELETE", "/posts/%s" % key)
        if status not in (200, 204):
            raise SyndicationError("SocialAPI delete failed - " + self._error_message(status, body))

    def check(self) -> CheckResult:
        """Read-only: is the key valid and does it have an active account here?"""
        if not self._key():
            return CheckResult(ok=False, detail="No SOCIALAPI_KEY set.")
        try:
            accounts = self._accounts(fresh=True)
        except SyndicationError as e:
            return CheckResult(ok=False, detail=str(e))
        mine = [a for a in accounts if a.get("platform") == self.id]
        if not mine:
            return CheckResult(ok=False, detail="Key OK, but no %s account connected." % self.label)
        active = [a for a in mine if a.get("status") == "active"]
        if not active:
            return CheckResult(ok=False, detail="%s account needs reconnecting: %s"
                                      % (self.label, mine[0].get("reconnect_reason") or "status not active"))
        return CheckResult(ok=True, detail="%s account connected as %s"
                                          % (self.label, active[0].get("username") or active[0].get("name")))


def build_platforms() -> list[SocialApiSyndicator]:
    return [SocialApiSyndicator(pid, label) for pid, label in _configured_platforms()]
