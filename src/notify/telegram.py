"""Telegram notification for a finished syndication run (optional).

Moved here from app.py; implementation lives in telegram.py.
"""
import json
import urllib.request

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def notify_telegram(doc, results):
    """Send a summary of a completed syndication run to Telegram.

    Enabled by TELEGRAM_BOT_TOKEN (from @BotFather) + TELEGRAM_CHAT_ID. Both are
    optional: with either missing this is a silent no-op, so syndication never
    depends on Telegram being configured.
    """
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    title = (doc.get("title") or doc.get("content") or "New post").strip()[:120]
    lines = ["Syndicated: " + title]
    for r in results:
        label = r.get("label") or r.get("platform")
        if r.get("status") == "posted" and r.get("url"):
            lines.append("- %s: %s" % (label, r["url"]))
        else:
            lines.append("- %s: FAILED %s" % (label, (r.get("error") or "unknown")[:120]))
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "\n".join(lines),
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % TELEGRAM_BOT_TOKEN,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except Exception as e:
        # Never let a notification failure break syndication.
        print("[telegram] notify failed:", e)
