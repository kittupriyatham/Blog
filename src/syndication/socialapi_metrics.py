"""Read-only SocialAPI engagement metrics - per post, per platform.

The analytics dashboard shows each social platform's *own* numbers (likes /
comments / views) next to the blog's first-party traffic. Those live behind
SocialAPI, keyed by the ids the publisher already recorded on
`doc["syndications"]` (`platform`, `remote_id`, `url`), so this module reads them
and nothing else: no publish, no edit, no delete.

Auth is NOT re-implemented. `_MetricsReader` subclasses the adapter in
`socialapi.py` and therefore inherits its `_key()`, `_request()` (base URL, Bearer
header, User-Agent) and `_account_id()` (the `SOCIALAPI_ACCOUNT_<PLATFORM>`
override, then `GET /accounts`). A change to auth there cannot leave this path
behind, and no key/token/header is duplicated here.

Two read paths, in order (`GET` only):

  1. `GET /v1/posts/{id}/metrics`  - one call per syndication that has a
     `remote_id`. The endpoint accepts either the SocialAPI post id or the
     platform's own post id, so this is an exact lookup: no scanning, no
     guessing. (api-reference/posts/get-post-metrics)
  2. `GET /v1/posts?platform=&account_ids=&sort=created_desc&cursor=` - for a
     syndication that only has a permalink. Targets are matched by
     `platform_post_id` / `permalink` (see `match_targets`).
     (api-reference/posts/list-all-posts)

Everything degrades. No `SOCIALAPI_KEY`, a platform SocialAPI does not own, a
missing remote id, an HTTP error or an unreachable network all yield
partial/empty data - `platform_metrics()` never raises and always returns a dict
the caller can cache and render.

LinkedIn metrics ARE read, but not through SocialAPI: LinkedIn is a native
adapter, so `platform_metrics()` routes a `linkedin` syndication to
`linkedin_metrics.read_metrics()`, which reads LinkedIn's own
`organizationalEntityShareStatistics` (the Organization/Company Page's share
statistics). That reader never raises - a missing org URN or an org-scoped token
comes back as an "unavailable" entry with a human-readable reason (see
src/analytics/reports.py, which renders it as a neutral hint). Other native
adapters (e.g. `medium`) still get the "published natively - SocialAPI has no
metrics for it" placeholder.
"""
import os
import urllib.parse
from datetime import datetime, timezone

from . import linkedin_metrics
from .base import SyndicationError
from .socialapi import SocialApiSyndicator, build_platforms

#: Metric fields the dashboard surfaces. `views` only exists on platforms that
#: publish one (YouTube); `shares`/`saves` exist only where the platform reports
#: them, so every field is read defensively (and may come back as 0).
METRIC_KEYS = ("likes", "comments", "views", "shares", "saves")

#: `GET /v1/posts` caps `limit` at 100 (api-reference/posts/list-all-posts).
DEFAULT_LIMIT = 100
#: Cursor pages to walk when a syndication has no remote id to look up directly.
MAX_PAGES = 3
#: Seconds per SocialAPI request. The dashboard route is synchronous, so this
#: stays well under a browser's patience even with several platforms.
DEFAULT_TIMEOUT = 20

#: Reserved top-level key in the cached dict. A leading underscore keeps it
#: from ever colliding with a platform slug.
META_KEY = "_meta"


def _socialapi_key_configured() -> bool:
    """True when SOCIALAPI_KEY is set, so SocialAPI reads can be made."""
    return bool(os.environ.get("SOCIALAPI_KEY", "").strip())


#: Platforms that POST natively (our own official-API adapters, so no SocialAPI
#: post credit is spent) but whose METRICS are read from SocialAPI. LinkedIn is the
#: case this exists for: its member engagement is only reachable through
#: SocialAPI's `linkedin_page` beta (`connection_type: "personal"`). Add
#: "linkedin" here once that beta is enabled on the account - until then this set
#: is empty and every platform keeps its current reader.
SOCIALAPI_METRIC_PLATFORMS: set = set()  # {"linkedin"} once the beta lands


def metrics_configured() -> bool:
    """True when *any* social metrics can be refreshed.

    Two independent switches: SOCIALAPI_KEY enables the SocialAPI platforms, and
    LinkedIn is read natively (the org URN plus a token, see
    `linkedin_metrics.configured()`). Either one alone lets the refresh run - a
    platform whose own switch is missing just comes back "unavailable".
    """
    return _socialapi_key_configured() or linkedin_metrics.configured()


def syndication_platform_ids() -> set:
    """The platform ids SocialAPI owns, as configured for this app.

    This is the same registry the publisher uses, so `linkedin`/`medium` (native
    adapters with no SocialAPI metrics) are correctly absent.
    """
    return {s.id for s in build_platforms()}


class _MetricsReader(SocialApiSyndicator):
    """A SocialAPI client used only for reads.

    Inherits the adapter's auth and account lookup (see the module docstring).
    `bind()` re-points one instance at another platform, and `_accounts()` caches
    its account list per instance - so refreshing several platforms in one pass
    still costs a single `GET /accounts`.
    """

    def __init__(self):
        super().__init__("_metrics", "Metrics")

    def bind(self, platform, label=None):
        self.id = platform
        self.label = label or str(platform or "").replace("_", " ").title()
        return self

    def account_id(self):
        """This platform's connected account id, or '' when it cannot be resolved.

        A missing account is not fatal: `GET /v1/posts` also filters by platform
        alone, so the list path just runs unscoped instead of failing.
        """
        try:
            return self._account_id()
        except Exception:
            return ""


def _get(reader, path, timeout=DEFAULT_TIMEOUT):
    """(status, body) for `GET path`; (0, {}) when the call could not be made.

    `_request()` already turns an HTTP error into its (code, parsed body); a
    missing key or a network failure raises, and that is swallowed here so no
    caller has to guard the network.
    """
    try:
        return reader._request("GET", path, timeout=timeout)
    except SyndicationError:
        return 0, {}
    except Exception:
        return 0, {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _norm_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm_url(value) -> str:
    """A comparable form of a permalink: scheme/host lowercased, no trailing /.

    Query strings are kept (some permalinks carry one) but the fragment is not,
    since it is never part of a post's identity.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        parts = urllib.parse.urlsplit(text)
        text = urllib.parse.urlunsplit(
            (parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))
    return text.rstrip("/")


def parse_metrics(target: dict) -> dict:
    """Normalize one SocialAPI `target` into the shape the dashboard caches.

    `metrics_synced_at` sits on the *target* (a sibling of `metrics`), not inside
    it, per the API reference - both spellings are read so a provider change in
    either direction cannot blank the timestamp. `views` is not in the documented
    metric set (it is YouTube-only) and can arrive under `metrics.extra`, so the
    top level is preferred and `extra` is the fallback.
    """
    target = target or {}
    raw = target.get("metrics") if isinstance(target.get("metrics"), dict) else {}
    extra = raw.get("extra") if isinstance(raw.get("extra"), dict) else {}
    out = {key: (_int(raw.get(key)) or _int(extra.get(key))) for key in METRIC_KEYS}
    out["synced_at"] = target.get("metrics_synced_at") or raw.get("metrics_synced_at")
    out["permalink"] = target.get("permalink")
    out["platform_post_id"] = _norm_id(target.get("platform_post_id")) or None
    out["status"] = target.get("status") or None
    return out


def _empty(syn: dict, error=None, available=False) -> dict:
    """A placeholder entry: the platform is known, its metrics are not.

    Counters are `None` (not 0) on purpose - "we could not read a like count" and
    "this post has zero likes" are different things, and the dashboard prints an
    em dash for the first.
    """
    syn = syn or {}
    return {
        "platform": (syn.get("platform") or "").strip().lower(),
        "likes": None, "comments": None, "views": None, "shares": None, "saves": None,
        "permalink": syn.get("url"),
        "synced_at": None,
        "platform_post_id": None,
        "remote_id": _norm_id(syn.get("remote_id")) or None,
        "status": syn.get("status") or None,
        "available": bool(available),
        "error": error,
    }


def _first_syn(syndications, platform) -> dict:
    for syn in syndications:
        if (syn.get("platform") or "").strip().lower() == platform:
            return syn
    return {}


def match_targets(syndications, posts) -> dict:
    """Match SocialAPI posts to a doc's syndications. Pure - no I/O.

    `syndications` are the blog records `{platform, remote_id, url, ...}` and
    `posts` are the API's list items `{id, targets: [{platform,
    platform_post_id, permalink, metrics, ...}]}`.

    A target matches a syndication when, for the same platform:
      * its `platform_post_id` equals the record's `remote_id`, or
      * the post's own `id` equals the record's `remote_id`, or
      * its `permalink` equals the record's `url`.

    The middle rule is the one that usually fires: `remote_id` is what the
    publisher stored, and `socialapi.py` sets it to the SocialAPI post id. The
    `platform_post_id` rule is what the API reference documents, so both are
    honoured rather than betting on one.
    """
    by_id: dict = {}
    by_url: dict = {}
    for post in posts or []:
        if not isinstance(post, dict):
            continue
        post_id = _norm_id(post.get("id"))
        for target in post.get("targets") or []:
            if not isinstance(target, dict):
                continue
            platform = (target.get("platform") or "").strip().lower()
            info = dict(target)
            info["_post_id"] = post_id
            for key in (_norm_id(target.get("platform_post_id")), post_id):
                if key:
                    by_id.setdefault((platform, key), info)
            url = _norm_url(target.get("permalink"))
            if url:
                by_url.setdefault((platform, url), info)

    found: dict = {}
    for syn in syndications or []:
        if not isinstance(syn, dict):
            continue
        platform = (syn.get("platform") or "").strip().lower()
        if not platform or platform in found:
            continue
        remote_id = _norm_id(syn.get("remote_id"))
        target = (by_id.get((platform, remote_id)) if remote_id else None) \
            or by_url.get((platform, _norm_url(syn.get("url"))))
        if target:
            found[platform] = parse_metrics(target)
    return found


def _fetch_direct(reader, remote_id, timeout=DEFAULT_TIMEOUT):
    """`GET /v1/posts/{id}/metrics` -> the target list, or [] on any failure."""
    status, body = _get(reader, "/posts/%s/metrics"
                        % urllib.parse.quote(_norm_id(remote_id), safe=""), timeout)
    if status != 200 or not isinstance(body, dict):
        return []
    data = body.get("data")
    targets = data.get("targets") if isinstance(data, dict) else None
    return [t for t in (targets or []) if isinstance(t, dict)]


def _fetch_list(reader, limit=DEFAULT_LIMIT, timeout=DEFAULT_TIMEOUT):
    """`GET /v1/posts` for the bound platform, newest first. None when it fails.

    `sort=created_desc` matters: the endpoint's default is `scheduled_asc`
    (oldest first), which would put a just-published post beyond the first page.
    """
    account_id = reader.account_id()
    collected: list = []
    cursor = None
    for _ in range(MAX_PAGES):
        params = {"platform": reader.id, "limit": limit, "sort": "created_desc"}
        if account_id:
            params["account_ids"] = account_id
        if cursor:
            params["cursor"] = cursor
        status, body = _get(reader, "/posts?" + urllib.parse.urlencode(params), timeout)
        if status != 200 or not isinstance(body, dict):
            return None if not collected else collected
        collected.extend(p for p in (body.get("data") or []) if isinstance(p, dict))
        page = body.get("pagination") if isinstance(body.get("pagination"), dict) else {}
        cursor = page.get("next_cursor")
        if not page.get("has_more") or not cursor:
            break
    return collected


def _pick_target(targets, platform):
    """Our target out of a metrics/lookup response (or the only one there is)."""
    for target in targets or []:
        if (target.get("platform") or "").strip().lower() == platform:
            return target
    return targets[0] if len(targets) == 1 else None


def _entry_for(reader, syn, timeout, errors) -> dict:
    """One platform's entry: exact id lookup first, then a filtered list scan."""
    platform = reader.id
    remote_id = _norm_id(syn.get("remote_id"))

    if remote_id:
        target = _pick_target(_fetch_direct(reader, remote_id, timeout), platform)
        if target:
            entry = parse_metrics(target)
            entry["permalink"] = entry.get("permalink") or syn.get("url")
            entry["remote_id"] = remote_id
            entry["available"] = True
            entry["error"] = None
            return entry

    posts = _fetch_list(reader, timeout=timeout)
    if posts is None:
        errors.append("%s: SocialAPI could not be reached." % (syn.get("label") or platform))
        return _empty(syn, error="SocialAPI request failed - see the server log.")
    matched = match_targets([syn], posts).get(platform)
    if matched:
        matched["permalink"] = matched.get("permalink") or syn.get("url")
        matched["remote_id"] = remote_id or None
        matched["available"] = True
        matched["error"] = None
        return matched

    if syn.get("status") and syn.get("status") != "posted":
        reason = "never published to %s (status: %s)" % (syn.get("label") or platform, syn.get("status"))
    elif not remote_id and not syn.get("url"):
        reason = "this syndication has no remote id or URL yet"
    else:
        reason = "no SocialAPI post matched this syndication"
    return _empty(syn, error="Metrics not found - %s." % reason)


def platform_metrics(doc, timeout=DEFAULT_TIMEOUT) -> dict:
    """Per-platform social metrics for one blog doc.

    Returns `{platform: {likes, comments, views, shares, saves, permalink,
    synced_at, platform_post_id, remote_id, status, available, error}}` plus a
    `_meta` entry `{fetched_at, errors}`. Never raises: every failure becomes a
    partial result with `available: False` and a human-readable `error`, so the
    caller can cache it as-is.
    """
    result: dict = {}
    errors: list = []
    raw = doc.get("syndications") if hasattr(doc, "get") else None
    syndications = [s for s in (raw or []) if isinstance(s, dict)]
    owned = syndication_platform_ids()

    wanted: list = []   # SocialAPI-owned platforms, read through SocialAPI
    seen: set = set()
    for syn in syndications:
        platform = (syn.get("platform") or "").strip().lower()
        if not platform or platform in seen:
            continue
        seen.add(platform)
        # The native reader is skipped for any platform SocialAPI owns the metrics
        # for (e.g. LinkedIn once its beta lands - see SOCIALAPI_METRIC_PLATFORMS).
        # The set is empty today, so this stays the native path for LinkedIn.
        if (platform in linkedin_metrics.PLATFORMS
                and platform not in owned
                and platform not in SOCIALAPI_METRIC_PLATFORMS):
            # LinkedIn is read natively (Organization share statistics), not via
            # SocialAPI. The reader degrades to an "unavailable" entry with a
            # reason instead of raising - see linkedin_metrics.read_metrics.
            try:
                result[platform] = linkedin_metrics.read_metrics(syn, timeout=timeout)
            except Exception as exc:  # a bug here must not 500 the dashboard
                errors.append("%s: %s" % (platform, exc))
                result[platform] = _empty(syn, error="Metrics lookup failed: %s" % exc)
            continue
        if platform in owned or platform in SOCIALAPI_METRIC_PLATFORMS:
            wanted.append(platform)
        else:
            # Another native adapter (medium) or an unknown one. SocialAPI has no
            # numbers for it, so record that as the platform's state instead of
            # dropping the row - the dashboard then shows the platform with why.
            result[platform] = _empty(
                syn, error="%s is published natively - SocialAPI has no metrics for it."
                           % (syn.get("label") or platform.capitalize()))

    if wanted and _socialapi_key_configured():
        reader = _MetricsReader()
        for platform in wanted:
            syn = _first_syn(syndications, platform)
            reader.bind(platform, syn.get("label"))
            try:
                result[platform] = _entry_for(reader, syn, timeout, errors)
            except Exception as exc:  # a bug here must not 500 the dashboard
                errors.append("%s: %s" % (platform, exc))
                result[platform] = _empty(syn, error="Metrics lookup failed: %s" % exc)
    elif wanted:
        # No SocialAPI key: record that as each SocialAPI platform's state.
        # (LinkedIn is skipped above, so it is never placeholdered here.)
        for platform in wanted:
            entry = _empty(_first_syn(syndications, platform),
                           error="SOCIALAPI_KEY is not set - metrics are unavailable.")
            entry["platform"] = platform
            result[platform] = entry

    return {**result, META_KEY: {"fetched_at": _now_iso(), "errors": errors}}
