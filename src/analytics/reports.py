"""Analytics read path: raw events + dashboard aggregates.

Moved here from app.py. Reads from whichever store ANALYTICS_STORE selects
(file or mongo) - the collection handle is resolved inside the function, never
at import.

`social_metrics_summary` is the other half of the dashboard: it joins the
*cached* per-platform metrics (written by the refresh route) onto each post's
`syndications`. The cache holds SocialAPI platforms, and LinkedIn is a native
adapter whose numbers are read through its own reader
(src/syndication/linkedin_metrics.py). A LinkedIn row shows those metrics when
they are available; when they are not (never refreshed, no org URN, or an
org-scoped token missing) it still keeps the permalink visible with a neutral,
human-readable hint and never an amber API error. It performs no network I/O, so
the page renders with no SocialAPI key and no cache - just an empty state.
"""
import json
import os

from src.config import ANALYTICS_LOG_FILE, ANALYTICS_STORE
from src.db import AnalyticsEvent


def analytics_events(limit=2000):
    """Most recent analytics events (newest first) from the active store."""
    if ANALYTICS_STORE == "mongo":
        return list(AnalyticsEvent._get_collection().find({}, {"_id": 0}).sort("_id", -1).limit(limit))
    collected = []
    if os.path.exists(ANALYTICS_LOG_FILE):
        with open(ANALYTICS_LOG_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    collected.append(json.loads(line))
                except Exception:
                    continue
    return list(reversed(collected[-limit:]))


def analytics_aggregates(events):
    """Roll raw events into dashboard-friendly aggregates."""
    per_post = {}
    daily = {}
    by_method = {}
    by_platform = {}
    by_country = {}   # country -> set(ip_hash): distinct visitors
    by_region = {}    # "region, country" -> set(ip_hash): distinct visitors
    totals = {"view": 0, "reach_in": 0, "post_opened": 0, "shares": 0, "click_out": 0,
              "likes": 0, "comments": 0, "time_spent_ms": 0, "time_on_blog_ms": 0}

    def row(pid, ptype=None):
        r = per_post.get(pid)
        if r is None:
            r = {"post_id": pid, "type": ptype, "view": 0, "reach_in": 0, "post_opened": 0,
                 "shares": 0, "click_out": 0, "likes": 0, "comments": 0, "time_spent_ms": 0}
            per_post[pid] = r
        if ptype and not r["type"]:
            r["type"] = ptype
        return r

    count_events = {"view", "reach_in", "post_opened", "likes", "comments"}
    for e in events:
        ev = e.get("event")
        if ev not in ("view", "reach_in", "post_opened", "likes", "comments",
                      "shares", "click_out", "time_spent", "time_on_blog"):
            continue
        pid = e.get("post_id")
        ptype = e.get("type")
        day = (e.get("ts") or "")[:10]
        ms = int(e.get("milliseconds", 0) or 0)

        # Geo: attribute this visitor (hashed IP) to country / state. Every page
        # view emits a "view" event, so distinct visitors are captured here.
        ip = e.get("ip_hash")
        country = e.get("country")
        region = e.get("region")
        if country and ip:
            by_country.setdefault(country, set()).add(ip)
        if region and ip:
            label = "%s, %s" % (region, country) if country else region
            by_region.setdefault(label, set()).add(ip)

        if ev in count_events:
            totals[ev] += 1
            if pid:
                row(pid, ptype)[ev] += 1
        elif ev == "shares":
            totals["shares"] += 1
            m = e.get("method") or "unknown"
            by_method[m] = by_method.get(m, 0) + 1
            if pid:
                row(pid, ptype)["shares"] += 1
        elif ev == "click_out":
            totals["click_out"] += 1
            pl = e.get("platform") or "external"
            by_platform[pl] = by_platform.get(pl, 0) + 1
            if pid:
                row(pid, ptype)["click_out"] += 1
        elif ev == "time_spent":
            totals["time_spent_ms"] += ms
            if pid:
                row(pid, ptype)["time_spent_ms"] += ms
        elif ev == "time_on_blog":
            totals["time_on_blog_ms"] += ms

        if day:
            d = daily.setdefault(day, {"view": 0, "reach_in": 0, "post_opened": 0, "shares": 0,
                                       "click_out": 0, "likes": 0, "comments": 0,
                                       "time_spent_ms": 0, "time_on_blog_ms": 0})
            if ev in count_events or ev == "shares" or ev == "click_out":
                d[ev] = d.get(ev, 0) + 1
            elif ev == "time_spent":
                d["time_spent_ms"] = (d.get("time_spent_ms", 0) or 0) + ms
            elif ev == "time_on_blog":
                d["time_on_blog_ms"] = (d.get("time_on_blog_ms", 0) or 0) + ms

    daily_list = [dict(date=k, **v) for k, v in sorted(daily.items())]
    posts = sorted(per_post.values(), key=lambda r: r["view"], reverse=True)
    return {
        "totals": totals,
        "daily": daily_list,
        "by_method": [{"method": k, "count": v} for k, v in sorted(by_method.items(), key=lambda x: -x[1])],
        "by_platform": [{"platform": k, "count": v} for k, v in sorted(by_platform.items(), key=lambda x: -x[1])],
        "by_country": [{"country": k, "count": len(v)} for k, v in sorted(by_country.items(), key=lambda x: -len(x[1]))],
        "by_region": [{"label": k, "count": len(v)} for k, v in sorted(by_region.items(), key=lambda x: -len(x[1]))],
        "per_post": posts,
        "recent": events[:50],
    }


# --- Social performance (platform-wise) --------------------------------------
# The blog only sees its own traffic; the platforms see their own engagement.
# The refresh route caches the latter on `doc["platform_metrics"]` (see
# src/syndication/socialapi_metrics.py) and these helpers turn that cache plus
# `syndications` into what the dashboard renders.

SOCIAL_METRIC_KEYS = ("likes", "comments", "views")

#: Native adapters whose metrics are read by their own reader rather than
#: SocialAPI's (LinkedIn -> src/syndication/linkedin_metrics.py, the Organization
#: share statistics). A row for one of these is "tracked" only once that reader
#: actually returned numbers; until then it keeps its permalink with a neutral,
#: human-readable hint instead of an error or a bare em dash.
NATIVE_METRIC_PLATFORMS = {"linkedin"}


def _metric(value):
    """An int counter, or None when the platform's number is unknown.

    `None` and `0` must not collapse into each other: "we could not read this"
    renders as an em dash, "the post has no likes yet" renders as 0.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _label(doc):
    """A readable name for a post: its title, else the first text it has."""
    title = (doc.get("title") or "").strip()
    if title:
        return title
    for block in doc.get("blocks") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text = (block.get("content") or "").strip().replace("\n", " ")
            if text:
                return text[:70] + ("\u2026" if len(text) > 70 else "")
    return doc.get("post_id") or "(no title)"


def _platform_row(syn, cached):
    """One `platform` row of the social table: cached metrics, or the reason why not.

    A *native* platform (LinkedIn) reads its own numbers rather than SocialAPI's,
    so it counts as "tracked" only once a read actually returned numbers. When it
    has not - never refreshed, no org URN, or an org-scoped token missing - the row
    still shows the permalink with a neutral, human-readable hint (the reader's own
    reason, when it gave one), never an amber API error.
    """
    platform = (syn.get("platform") or "").strip().lower()
    metrics = cached.get(platform) if isinstance(cached.get(platform), dict) else {}
    native = platform in NATIVE_METRIC_PLATFORMS
    available = bool(metrics.get("available"))
    # Native platforms have no SocialAPI numbers to fall back on, so until their
    # own reader returns something they render as a neutral hint, not an error.
    tracked = available if native else True
    row = {
        "platform": platform,
        "label": syn.get("label") or platform.capitalize() or "Unknown",
        "permalink": metrics.get("permalink") or syn.get("url"),
        "status": metrics.get("status") or syn.get("status") or "",
        "synced_at": metrics.get("synced_at") if tracked else None,
        "available": available and tracked,
        "tracked": tracked,
        # The cached error (why metrics are missing) wins over a publish error,
        # since a stale publish error on a posted platform is noise.
        "error": (metrics.get("error")
                  or (syn.get("error") if syn.get("status") != "posted" else None))
                 if tracked else None,
    }
    if not tracked:
        # A neutral hint: the reader's own reason (e.g. "LinkedIn has no member metrics"),
        # else a generic note. Never the amber API-error treatment.
        row["note"] = (metrics.get("error")
                       or "%s metrics are not tracked." % (row["label"] or platform.capitalize()))
    for key in SOCIAL_METRIC_KEYS:
        row[key] = _metric(metrics.get(key)) if row["available"] else None
    return row


def social_metrics_summary(docs, configured=True):
    """Per-post / per-platform social metrics for the dashboard.

    `docs` are the post documents that carry `syndications` (see the route). The
    result is:

        {
          "posts":   [{post_id, title, type, timestamp, fetched_at, platforms: [row, ...]}],
          "totals":  {likes, comments, views},            # every available number
          "platforms": [{platform, label, likes, comments, views}],  # biggest first
          "by_platform": [{platform: label, count: total engagement}],  # for the bar chart
          "configured": bool,                             # SOCIALAPI_KEY or LinkedIn org+token
          "fetched_at": iso or None,                      # newest cache write
          "errors": [str],                                # anything the refresh recorded
        }

    Only posts that have at least one syndication row appear in `posts`; totals
    count only numbers that were actually read, so a run with no cached metrics
    returns zeros rather than failing.
    """
    posts = []
    platform_totals: dict = {}
    totals = {key: 0 for key in SOCIAL_METRIC_KEYS}
    errors: list = []
    newest: str | None = None

    for doc in docs or []:
        if not hasattr(doc, "get"):
            continue
        syndications = [s for s in (doc.get("syndications") or []) if isinstance(s, dict)]
        cached = doc.get("platform_metrics") if isinstance(doc.get("platform_metrics"), dict) else {}
        if not syndications:
            continue

        rows = []
        for syn in syndications:
            row = _platform_row(syn, cached)
            if not row["platform"]:
                continue
            rows.append(row)
            if not row["available"]:
                continue
            bucket = platform_totals.setdefault(
                row["platform"], {"platform": row["platform"], "label": row["label"],
                                  **{key: 0 for key in SOCIAL_METRIC_KEYS}})
            for key in SOCIAL_METRIC_KEYS:
                if row[key] is None:
                    continue
                totals[key] += row[key]
                bucket[key] += row[key]

        meta = cached.get("_meta") if isinstance(cached.get("_meta"), dict) else {}
        fetched_at = meta.get("fetched_at")
        if fetched_at and (newest is None or fetched_at > newest):
            newest = fetched_at
        for err in meta.get("errors") or []:
            if err not in errors:
                errors.append(err)

        posts.append({
            "post_id": doc.get("post_id"),
            "title": _label(doc),
            "type": doc.get("type"),
            "timestamp": doc.get("timestamp"),
            "fetched_at": fetched_at,
            "refreshed": bool(meta),
            "platforms": rows,
        })

    platforms = sorted(platform_totals.values(),
                       key=lambda r: -(sum(r[key] or 0 for key in SOCIAL_METRIC_KEYS)))
    return {
        "posts": posts,
        "totals": totals,
        "platforms": platforms,
        "by_platform": [{"platform": r["label"],
                         "count": sum(r[key] or 0 for key in SOCIAL_METRIC_KEYS)} for r in platforms],
        "configured": bool(configured),
        "fetched_at": newest,
        "errors": errors,
    }
