"""Analytics package: first-party, no third party.

Re-exports the write side (events.py: record_analytics + request/geo helpers) and
the read side (reports.py: analytics_events / analytics_aggregates), so app.py
calls `analytics.record_analytics(...)` and
`analytics.analytics_aggregates(analytics.analytics_events(...))`.

`social_metrics_summary` is the read side of the *social* half of the dashboard:
it joins the cached SocialAPI per-platform metrics (see
src/syndication/socialapi_metrics.py) onto each post's syndications. It is pure
and offline - the refresh route is what talks to SocialAPI.
"""
from .events import (
    _client_ip,
    _ip_hash,
    _is_external,
    geolocate_ip,
    record_analytics,
)
from .reports import analytics_aggregates, analytics_events, social_metrics_summary

__all__ = [
    "record_analytics",
    "geolocate_ip",
    "_client_ip",
    "_ip_hash",
    "_is_external",
    "analytics_events",
    "analytics_aggregates",
    "social_metrics_summary",
]
