"""Analytics read path: raw events + dashboard aggregates.

Moved here from app.py. Reads from whichever store ANALYTICS_STORE selects
(file or mongo) - the collection handle is resolved inside the function, never
at import.
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
