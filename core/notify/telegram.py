"""Telegram notification and two-way webhook handler.

Handles:
1. Notifying Telegram on every post/article publication (whether socials are chosen or not).
2. Registering Telegram webhook automatically with zero manual clicks.
3. Handling two-way replies to bot messages, logging user-reported issues into MongoDB.
4. Replying back to the user via Telegram confirming report reception.
"""
import json
import uuid
import urllib.parse
import urllib.request

from core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SITE_URL
from core.content.helpers import now_str
from core.db import Post, IssueReport


def send_message(text, reply_to_message_id=None):
    """Low-level helper to send a message via Telegram Bot API."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return None
    payload_dict = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_to_message_id:
        payload_dict["reply_to_message_id"] = reply_to_message_id

    payload = json.dumps(payload_dict).encode("utf-8")
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % TELEGRAM_BOT_TOKEN,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return data.get("result", {})
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        print(f"[telegram] send_message HTTPError {e.code}: {err_msg}")
        # If replying failed (e.g., message not found), fallback to normal send without reply_to
        if reply_to_message_id:
            return send_message(text, reply_to_message_id=None)
    except Exception as e:
        print("[telegram] send_message error:", e)
    return None


def notify_telegram(doc, results=None, post_url=None):
    """Send publication summary to Telegram on every post/article creation.

    - If socials were checked: sends counts (e.g. 3/3 succeeded) + URLs or errors.
    - If no socials were checked: sends post live URL + local-only confirmation.
    - Saves telegram_message_id on the Post doc so future replies can be tied to it!
    """
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return None

    title = (doc.get("title") or doc.get("content") or "New story").strip()[:120]
    pid = doc.get("post_id")
    ptype = (doc.get("type") or "post").capitalize()
    
    # Construct canonical URL if not passed
    base_site = (SITE_URL or "").rstrip("/")
    if not post_url and base_site and pid:
        post_url = f"{base_site}/article/{pid}" if ptype.lower() == "article" else f"{base_site}/post/{pid}"

    results = results or []
    lines = []

    if results:
        total_tried = len(results)
        succeeded = sum(1 for r in results if r.get("status") == "posted" and r.get("url"))
        failed = total_tried - succeeded

        if failed == 0:
            header = f"🚀 Published & Syndicated: {title}\n📊 Result: {succeeded}/{total_tried} succeeded (100%)"
        else:
            header = f"⚠️ Published with Syndication Warning: {title}\n📊 Result: {succeeded}/{total_tried} succeeded, {failed} failed"

        lines.append(header)
        if post_url:
            lines.append(f"🔗 Live on Blog: {post_url}")
        lines.append("")
        for r in results:
            label = r.get("label") or r.get("platform")
            if r.get("status") == "posted" and r.get("url"):
                lines.append(f"  ✅ {label}: {r['url']}")
            else:
                lines.append(f"  ❌ {label}: FAILED ({str(r.get('error') or 'unknown')[:100]})")
    else:
        header = f"📝 Published on Blog: {title}"
        lines.append(header)
        if post_url:
            lines.append(f"🔗 Live on Blog: {post_url}")
        lines.append("ℹ️ (Local only — no social platforms selected)")

    lines.append("")
    lines.append("💬 Reply to this message anytime to report an issue or flag a correction.")

    result_msg = send_message("\n".join(lines))
    if result_msg and pid:
        msg_id = result_msg.get("message_id")
        try:
            Post._get_collection().update_one(
                {"post_id": pid},
                {"$set": {"telegram_message_id": msg_id}}
            )
        except Exception as e:
            print("[telegram] could not save telegram_message_id on post:", e)

    return result_msg


def handle_webhook_update(update):
    """Process incoming webhook payloads from Telegram.
    
    If the author replies to a bot message, find the referenced post,
    log the issue into IssueReport collection, and confirm receipt.
    """
    message = update.get("message") or update.get("channel_post")
    if not message:
        return {"status": "ignored_no_message"}

    reply_to = message.get("reply_to_message")
    user_text = (message.get("text") or "").strip()
    user_name = message.get("from", {}).get("username") or message.get("from", {}).get("first_name") or "Author"
    incoming_msg_id = message.get("message_id")

    if not user_text:
        return {"status": "ignored_empty_text"}

    posts_coll = Post._get_collection()
    issues_coll = IssueReport._get_collection()

    # Handle bot command: /start or /help
    if user_text in ("/start", "/help"):
        help_text = (
            "👋 Welcome to your Blog Notification & Feedback Bot!\n\n"
            "✨ What you can do:\n"
            "• Reply directly to any post notification to report an issue or typo.\n"
            "• Send /status to check unresolved issues.\n"
            "• Send /resolve [id] or /resolve all to close issues.\n"
            "• When issues are OPEN, cron-job.org alerts you via email."
        )
        send_message(help_text, reply_to_message_id=incoming_msg_id)
        return {"status": "command_handled", "command": user_text}

    # Handle bot command: /status
    if user_text == "/status":
        open_items = list(issues_coll.find({"status": "open"}).sort("created_at", -1))
        if not open_items:
            send_message("✅ All clear! There are currently 0 open issues.", reply_to_message_id=incoming_msg_id)
        else:
            lines = [f"⚠️ {len(open_items)} open issue(s):"]
            for it in open_items[:10]:
                lines.append(f"• #{it.get('report_id')}: \"{it.get('text')}\" (Post: {it.get('post_id')})")
            lines.append("\nTip: Send `/resolve all` or `/resolve <id>` to close.")
            send_message("\n".join(lines), reply_to_message_id=incoming_msg_id)
        return {"status": "command_handled", "command": "/status"}

    # Handle bot command: /resolve
    if user_text.startswith("/resolve"):
        parts = user_text.split()
        now_ts = now_str()
        if len(parts) > 1 and parts[1].lower() == "all":
            result = issues_coll.update_many({"status": "open"}, {"$set": {"status": "resolved", "resolved_at": now_ts}})
            send_message(f"✅ Resolved {result.modified_count} issue(s).", reply_to_message_id=incoming_msg_id)
            return {"status": "command_handled", "resolved_count": result.modified_count}
        elif len(parts) > 1:
            target_id = parts[1].lstrip("#")
            result = issues_coll.update_one({"report_id": target_id}, {"$set": {"status": "resolved", "resolved_at": now_ts}})
            if result.modified_count:
                send_message(f"✅ Issue #{target_id} marked as resolved.", reply_to_message_id=incoming_msg_id)
            else:
                send_message(f"❓ Could not find open issue #{target_id}.", reply_to_message_id=incoming_msg_id)
            return {"status": "command_handled", "target_id": target_id}
        else:
            # If replied to an issue ack or no argument given, resolve latest open issue
            latest_open = issues_coll.find_one({"status": "open"}, sort=[("created_at", -1)])
            if latest_open:
                issues_coll.update_one({"_id": latest_open["_id"]}, {"$set": {"status": "resolved", "resolved_at": now_ts}})
                send_message(f"✅ Resolved latest issue #{latest_open.get('report_id')}.", reply_to_message_id=incoming_msg_id)
            else:
                send_message("✅ No open issues to resolve.", reply_to_message_id=incoming_msg_id)
            return {"status": "command_handled", "command": "/resolve"}

    matched_post = None
    target_post_id = None

    if reply_to:
        replied_msg_id = reply_to.get("message_id")
        # Try matching by saved telegram_message_id
        matched_post = posts_coll.find_one({"telegram_message_id": replied_msg_id})
        if matched_post:
            target_post_id = matched_post.get("post_id")
        else:
            # Fallback search if post_id or title is inside the replied text
            replied_text = reply_to.get("text") or ""
            for doc in posts_coll.find({}, {"post_id": 1, "title": 1}).sort("timestamp", -1).limit(25):
                if doc.get("post_id") and doc.get("post_id") in replied_text:
                    matched_post = doc
                    target_post_id = doc.get("post_id")
                    break
    
    # If not a direct reply, associate with the latest published post
    if not matched_post:
        latest = posts_coll.find({"status": "published"}).sort("timestamp", -1).limit(1)
        latest_list = list(latest)
        if latest_list:
            matched_post = latest_list[0]
            target_post_id = matched_post.get("post_id")

    report_id = "rep_" + uuid.uuid4().hex[:12]
    now_ts = now_str()
    
    issue_doc = {
        "report_id": report_id,
        "post_id": target_post_id,
        "telegram_message_id": reply_to.get("message_id") if reply_to else None,
        "reply_message_id": incoming_msg_id,
        "reporter": user_name,
        "text": user_text,
        "status": "open",
        "created_at": now_ts,
    }
    issues_coll.insert_one(issue_doc)

    post_title = (matched_post.get("title") or target_post_id or "Recent Post") if matched_post else "Recent Post"
    ack_lines = [
        f"🚨 Issue Reported & Logged!",
        f"📌 Target: {post_title}",
        f"📝 Note: \"{user_text}\"",
        f"⚡ Status: Marked as OPEN for cron-job / email escalation.",
        f"🆔 Report ID: {report_id}",
    ]
    send_message("\n".join(ack_lines), reply_to_message_id=incoming_msg_id)
    return {"status": "logged", "report_id": report_id, "post_id": target_post_id}


def auto_register_webhook():
    """Idempotently register Telegram webhook URL on app startup."""
    if not (TELEGRAM_BOT_TOKEN and SITE_URL):
        return
    webhook_target = f"{SITE_URL.rstrip('/')}/api/telegram/webhook"
    
    # Check current webhook info
    try:
        info_req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo")
        with urllib.request.urlopen(info_req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok") and data.get("result", {}).get("url") == webhook_target:
                # Already up to date!
                return
    except Exception as e:
        print("[telegram] webhook check error:", e)

    # Set webhook
    try:
        set_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        payload = json.dumps({"url": webhook_target}).encode("utf-8")
        set_req = urllib.request.Request(
            set_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(set_req, timeout=10) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            if res_data.get("ok"):
                print(f"[telegram] Webhook automatically registered to: {webhook_target}")
    except Exception as e:
        print("[telegram] auto_register_webhook failed:", e)
