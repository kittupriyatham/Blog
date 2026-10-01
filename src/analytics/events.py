"""Analytics write path: collect one event from the current request.

Moved here from app.py. Events land in data/analytics.jsonl (JSON Lines) by
default, or in the Mongo `analytics` collection when ANALYTICS_STORE=mongo.
Only a salted sha-256 of the client IP is stored.

The DB collection is resolved *inside* the functions (never at import):
connect_db() runs in app.py, and importing a package must have no side effects.
"""
import hashlib
import json
import os
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from flask import request

from src.config import (
    ANALYTICS_GEO,
    ANALYTICS_IP_SALT,
    ANALYTICS_LOG_FILE,
    ANALYTICS_STORE,
)
from src.db import AnalyticsEvent

# Opt-in visitor geo (country/state). The raw IP is NEVER stored: geolocate_ip
# runs at beacon time (while the IP is in request scope) and only the resolved
# country/region/city plus the salted ip_hash are persisted. Free, no-key
# ip-api.com is used; look-ups are cached per IP for 24h. Behind a tunnel/proxy,
# _client_ip() reads CF-Connecting-IP / X-Forwarded-For (request.remote_addr is
# just the local cloudflared connection and is shared by every visitor).
_GEO_CACHE: dict = {}
_GEO_CACHE_AT: dict = {}
_GEO_TTL = 86400


def _client_ip() -> str:
    """Visitor IP: CF-Connecting-IP / X-Forwarded-For, else request.remote_addr."""
    for h in ("CF-Connecting-IP", "X-Forwarded-For"):
        v = request.headers.get(h, "")
        if v:
            return v.split(",")[0].strip()
    return request.remote_addr or ""


def _ip_hash() -> str:
    ip = _client_ip()
    return hashlib.sha256((ip + ANALYTICS_IP_SALT).encode("utf-8")).hexdigest()[:16]


def geolocate_ip(ip: str) -> dict:
    """Resolve an IP to {country, region, city} via ip-api.com (cached, 24h)."""
    if not ip or ip in ("127.0.0.1", "::1", "0.0.0.0"):
        return {}
    now = datetime.now(timezone.utc).timestamp()
    if ip in _GEO_CACHE and (now - _GEO_CACHE_AT.get(ip, 0)) < _GEO_TTL:
        return _GEO_CACHE[ip]
    result: dict = {}
    try:
        url = "http://ip-api.com/json/%s?fields=status,message,country,regionName,city,query" % urllib.parse.quote(ip, safe="")
        with urllib.request.urlopen(url, timeout=3) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        if data.get("status") == "success":
            result = {
                "country": data.get("country", ""),
                "region": data.get("regionName", ""),
                "city": data.get("city", ""),
            }
    except Exception as e:
        print("[analytics] geo lookup failed:", e)
    _GEO_CACHE[ip] = result
    _GEO_CACHE_AT[ip] = now
    return result


def _is_external(url: str) -> bool:
    if not url:
        return False
    try:
        return urllib.parse.urlparse(url).netloc != request.host
    except Exception:
        return False


def record_analytics(event: dict) -> None:
    """Persist one analytics event (server-side call path)."""
    event = dict(event)
    event.setdefault("event_id", secrets.token_hex(8))
    event.setdefault("ts", datetime.now(timezone.utc).isoformat())
    event.setdefault("ip_hash", _ip_hash())
    event.setdefault("user_agent", (request.headers.get("User-Agent") or "")[:256])
    event.setdefault("session_id", request.cookies.get("__ab_sess", ""))
    event.setdefault("referrer", request.headers.get("Referer") or "")
    if ANALYTICS_GEO:
        _geo = geolocate_ip(_client_ip())
        if _geo:
            event.setdefault("country", _geo.get("country", ""))
            event.setdefault("region", _geo.get("region", ""))
            event.setdefault("city", _geo.get("city", ""))
    try:
        if ANALYTICS_STORE == "mongo":
            AnalyticsEvent._get_collection().insert_one(event)
        else:
            with open(ANALYTICS_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")
    except Exception as e:
        print("[analytics] write failed:", e)
