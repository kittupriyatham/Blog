"""Read-only LinkedIn Organization (Company Page) share statistics.

The analytics dashboard shows each social platform's *own* engagement next to the
blog's first-party traffic. LinkedIn is a *native* adapter (it posts through the
official `/rest/posts` endpoint - see linkedin.py), so it has no SocialAPI
numbers; this module reads LinkedIn's own numbers instead and returns them in the
same shape the dashboard's other platforms use, so the page renders them side by
side.

What is read
------------

    GET https://api.linkedin.com/rest/organizationalEntityShareStatistics
        ?q=organizationalEntity
        &organizationalEntity=<orgUrn>
        &shares[0]=<postUrn>

`shares[0]` is the LinkedIn post URN this blog published (the `x-restli-id`
linkedin.py persists as `remote_id`, or the id embedded in the web permalink).
The response's `elements[0].totalShareStatistics` carries the counters, which map
onto the dashboard's fields as:

    likes    = likeCount
    comments = commentCount
    views    = impressionCount   (fallback: uniqueImpressionsCount)
    shares   = shareCount
    clicks   = clickCount

Requirements
------------

The token must carry `r_organization_social`, the post must have been published
as the Organization (`w_organization_social`), and `LINKEDIN_ORGANIZATION_URN`
must hold the Page's URN. See linkedin_token.py for the OAuth scope and the
re-authorization step; a member-only token - or a missing org URN - is reported
as the platform's state, never fabricated.

Everything degrades: no token, no org URN, no post URN, an HTTP error or an
unreachable network all yield a placeholder with `available: False` and a
human-readable `error`. Nothing here raises, and auth is not re-implemented - the
token comes from `linkedin_token.access_token()` and the API-version negotiation
from `linkedin.py`.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from . import linkedin_token
from .linkedin import LinkedinSyndicator, organization_urn

#: Platform slugs this reader owns. Kept as a set so socialapi_metrics.py can ask
#: "is this platform read natively here?" without hardcoding a single string.
PLATFORMS = {"linkedin"}

#: The Organization share-statistics endpoint (Rest.li).
STATS_API = "https://api.linkedin.com/rest/organizationalEntityShareStatistics"

#: Seconds per LinkedIn request. The dashboard route is synchronous, so this
#: stays well under a browser's patience.
DEFAULT_TIMEOUT = 20


def configured() -> bool:
    """True when LinkedIn metrics could be read: an org URN *and* a token exist.

    Cheap and offline (no refresh) - this runs on every analytics page render,
    so it must not perform a token refresh over the network.
    """
    return bool(organization_urn() and linkedin_token.has_credentials())


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _placeholder(syn: dict, error=None) -> dict:
    """A LinkedIn entry with the platform known and its numbers unknown."""
    syn = syn or {}
    return {
        "platform": "linkedin",
        "likes": None, "comments": None, "views": None,
        "shares": None, "saves": None, "clicks": None,
        "permalink": syn.get("url"),
        "synced_at": None,
        "platform_post_id": None,
        "remote_id": syn.get("remote_id") or None,
        "status": syn.get("status") or None,
        "available": False,
        "error": error,
    }


def urn_from_syn(syn: dict) -> str:
    """The LinkedIn post URN for a syndication record, or "" when there is none.

    Prefers the stored `remote_id` (the `x-restli-id` linkedin.py persists);
    falls back to the id embedded in the web permalink the adapter builds
    (`https://www.linkedin.com/feed/update/<urn>`), so records published before
    the URN was persisted still resolve.
    """
    syn = syn or {}
    remote = str(syn.get("remote_id") or "").strip()
    if remote.startswith("urn:li:"):
        return remote
    url = str(syn.get("url") or "").strip()
    tail = urllib.parse.unquote(url.rstrip("/").rsplit("/", 1)[-1])
    if tail.startswith("urn:li:"):
        return tail
    return ""


def statistics_url(org_urn: str, share_urn: str) -> str:
    """The full request URL for one share's statistics.

    `shares[0]` is written with literal brackets (as the API documents it) and
    only the URN values are percent-encoded, so `urn:li:...` arrives intact.
    """
    query = "q=organizationalEntity&organizationalEntity=%s&shares[0]=%s" % (
        urllib.parse.quote(org_urn, safe=""), urllib.parse.quote(share_urn, safe=""))
    return STATS_API + "?" + query


def _stat(stats, key):
    """An integer counter from `totalShareStatistics`, else None.

    LinkedIn omits a counter with no activity, so a missing key means "none yet"
    and the caller turns it into 0.
    """
    value = stats.get(key) if isinstance(stats, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _get_statistics(url: str, token: str, timeout: int):
    """`GET <url>` -> (status, body); (0, {...}) when the request cannot be made.

    Walks LinkedIn's recent API versions, remembering whichever one works - the
    same negotiation linkedin.py uses (HTTP 426 = NONEXISTENT_VERSION).
    """
    last = (0, {})
    for version in LinkedinSyndicator()._version_candidates():
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": version,
        }, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8") or "{}")
            LinkedinSyndicator._working_version = version
            return resp.status, (body if isinstance(body, dict) else {})
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")[:300]
            if e.code == 426:  # NONEXISTENT_VERSION -> try the next candidate
                last = (e.code, {"raw": raw, "version": version})
                continue
            return e.code, {"raw": raw, "version": version}
        except Exception as e:
            return 0, {"raw": str(e)[:200]}
    return last


def _first_statistics(body):
    """The first `totalShareStatistics` object in an elements list, or None.

    `None` means LinkedIn returned no counter block at all - the share is not
    (yet) visible to the Page - which the caller reports as "unavailable" rather
    than inventing zeros.
    """
    elements = body.get("elements") if isinstance(body, dict) else None
    if not isinstance(elements, list):
        return None
    for element in elements:
        if isinstance(element, dict) and isinstance(element.get("totalShareStatistics"), dict):
            return element["totalShareStatistics"]
    return None


def read_metrics(syn: dict, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """LinkedIn Page metrics for one syndication, in the dashboard's shape.

    Never raises: any failure returns a placeholder with `available: False` and
    an `error` that says exactly why (no org URN, no token, no post URN, HTTP
    status, ...), so the caller can cache the result as-is.
    """
    entry = _placeholder(syn)

    org = organization_urn()
    if not org:
        entry["error"] = ("LinkedIn posts publish as your personal profile, and LinkedIn's API "
                          "does not expose a member's own post engagement to an app like this one "
                          "(that endpoint is partner-gated). Only Page posts expose metrics.")
        return entry

    token = linkedin_token.access_token()
    if not token:
        entry["error"] = "LinkedIn is not configured - no access token is available."
        return entry

    urn = urn_from_syn(syn)
    if not urn:
        entry["error"] = ("This LinkedIn syndication has no post URN or permalink recorded, "
                          "so its metrics cannot be looked up.")
        return entry

    status, body = _get_statistics(statistics_url(org, urn), token, timeout)
    if status == 200:
        stats = _first_statistics(body)
        if stats is None:
            entry["error"] = ("LinkedIn returned no share statistics for this post - it may "
                              "not belong to %s, or the Page's numbers are not populated yet." % org)
            return entry
        likes = _stat(stats, "likeCount")
        comments = _stat(stats, "commentCount")
        views = _stat(stats, "impressionCount")
        if views is None:
            views = _stat(stats, "uniqueImpressionsCount")
        entry.update(
            likes=likes if likes is not None else 0,
            comments=comments if comments is not None else 0,
            views=views if views is not None else 0,
            shares=_stat(stats, "shareCount") or 0,
            clicks=_stat(stats, "clickCount") or 0,
            synced_at=_now_iso(),
            remote_id=urn,
            available=True,
            error=None,
        )
        return entry

    if status in (401, 403):
        entry["error"] = ("LinkedIn organization metrics need the r_organization_social scope "
                          "and a token re-authenticated for the Page (HTTP %s). Re-run "
                          "`python -m src.syndication.linkedin_token` with the organization "
                          "scopes. %s" % (status, str(body.get("raw") or "")[:160]))
    elif status == 404:
        entry["error"] = "No LinkedIn share statistics found for this syndication (HTTP 404)."
    elif status == 0:
        entry["error"] = "LinkedIn metrics request failed: %s" % (body.get("raw") or "network error")
    else:
        entry["error"] = ("LinkedIn metrics request failed - HTTP %s: %s"
                          % (status, str(body.get("raw") or body)[:200]))
    return entry
