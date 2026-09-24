"""Rewrite over-long post text so it fits a platform's character limit.

Trimming loses content: a 401-character post becomes a fragment that stops
mid-thought, and the reader never learns what was cut. Instead the whole text is
handed to an LLM and condensed, so a platform with a tight limit gets a
deliberate short version of the post rather than an amputated one.

The link the caller appends is NOT part of the rewrite - callers pass the room
left *after* reserving the link, so "fits the limit, including the link" holds.

Nothing here is required for publishing: `condense` returns None when no model is
configured or the call fails, and the caller falls back to boundary trimming.
"""
import hashlib
import json
import os
import urllib.error
import urllib.request

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"
DEFAULT_MODEL = "gemini-2.5-flash"
TIMEOUT_S = 45

# (sha1 of the text, room) -> rewrite, so the same post is not re-sent once per
# platform, and a retry does not pay for the same rewrite again.
_cache: "dict[tuple[str, int], str]" = {}

_INSTRUCTIONS = (
    "You are shortening a blog post for a social media platform.\n"
    "Rewrite the post below so it is at most {limit} characters long, including spaces.\n"
    "Rules:\n"
    "- Keep the meaning, the facts and the author's voice.\n"
    "- Drop or merge whole sentences; never clip a word or trail off mid-sentence.\n"
    "- Do not add commentary, hashtags, emoji, quotation marks or a preamble.\n"
    "- Do not include a URL - the caller appends the link separately.\n"
    "Return only the rewritten post text.\n\n"
    "Post:\n{text}"
)


def _api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _model() -> str:
    return os.environ.get("REWRITE_MODEL", "").strip() or DEFAULT_MODEL


def available() -> bool:
    """True when a rewrite model is configured, so the UI can say so."""
    return bool(_api_key())


def _extract(body: dict) -> str:
    candidates = body.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


def condense(text: str, limit: int) -> str | None:
    """Rewrite `text` to fit `limit` characters.

    Returns None when no model is configured or the request fails, so the caller
    can fall back to trimming. A rewrite that still overruns is trimmed at a
    boundary - the condensed wording is kept, only its tail is lost.
    """
    text = (text or "").strip()
    if limit <= 0 or not text or len(text) <= limit:
        return text or None

    key = _api_key()
    if not key:
        return None

    cache_key = (hashlib.sha1(text.encode("utf-8")).hexdigest(), limit)
    if cache_key in _cache:
        return _cache[cache_key]

    prompt = _INSTRUCTIONS.format(limit=limit, text=text)
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2048,
            # Gemini 2.5 Flash spends output tokens on internal reasoning by
            # default. Left on with a small budget, the visible answer came back
            # clipped mid-word, so thinking is switched off for this task.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }).encode("utf-8")

    url = GEMINI_ENDPOINT % (_model(), key)
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            rewritten = _extract(json.loads(resp.read().decode("utf-8")))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as e:
        print("[rewrite] %s model unavailable: %s" % (_model(), e))
        return None

    if not rewritten:
        return None

    # Defensive: the model could still overrun the limit.
    from . import truncate_on_boundary
    if len(rewritten) > limit:
        rewritten = truncate_on_boundary(rewritten, limit)

    _cache[cache_key] = rewritten
    return rewritten
